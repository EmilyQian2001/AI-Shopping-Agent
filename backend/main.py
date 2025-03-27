from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from typing import List, Dict, Optional, Any
import json
import requests
from bs4 import BeautifulSoup
import time
import datetime
import asyncio
import uuid
import re
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Access the API keys
perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
serper_api_key = os.getenv("SERPER_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_model_applied="gpt-4o-2024-11-20"

# Define state machine states
STATES = {
    'INITIAL': 'initial',                # Initial state
    'MODEL_SELECTION': 'model_selection', # Model selection state
    'ANALYZING_QUERY': 'analyzing',      # Analyzing query specificity state
    'CLARIFYING': 'clarifying',          # Getting more user preferences state
    'QUERYING': 'generating',    # Generating enhanced query state
    'RECOMMENDING': 'recommending',      # Generating product recommendations state
    'SEARCHING': 'searching',            # Searching for product information state
    'DETAILING': 'detailing',            # Getting product details state
    'READY': 'ready',                    # Recommendations complete, data ready state
    'ERROR': 'error'                     # Error state
}

# In-memory conversation store
# New structure: {
#   session_id: {
#     query: str,                        # Original query
#     preferences: dict,                 # User preferences
#     previous_recommendations: list,    # Previous recommendations
#     additional_requests: list,         # Additional requests
#     model_choice: str,                 # Model choice
#     state: str,                        # Current state
#     missing_info: list,                # List of missing information
#     confidence: float,                 # Confidence in query specificity
#     last_update: str,                  # Last update time
#     background_task: Task,             # Background task reference
#     clarification_attempts: int,       # Number of clarification attempts
#     clarification_keywords: list,      # Keywords from clarification questions
#     is_clarified: bool                 # Flag indicating if query is clarified
#   }
# }
conversation_store = {}

# WebSocket Management
active_connections: List[WebSocket] = []

# WebSocket Log Handler
class WebSocketLogHandler:
    def __init__(self):
        self.connections = active_connections

    async def log(self, message: str):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_data = {
            "timestamp": timestamp,
            "message": message
        }
        # Broadcast log to all connected clients
        for connection in self.connections:
            try:
                await connection.send_json(log_data)
            except:
                continue

# Create global log handler instance
ws_logger = WebSocketLogHandler()

# Async logging function
async def log(message: str):
    print(message)  # Keep console output
    await ws_logger.log(message)

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await log(f"New WebSocket connection attempt from {websocket.client}")
    try:
        await websocket.accept()
        active_connections.append(websocket)
        await log(f"WebSocket connection accepted")
        
        while True:
            try:
                await websocket.receive_text()
            except Exception as e:
                await log(f"Error in WebSocket connection: {e}")
                break
    except Exception as e:
        await log(f"Error accepting WebSocket connection: {e}")
    finally:
        await log("WebSocket connection closed")
        if websocket in active_connections:
            active_connections.remove(websocket)

# Request/Response Models
class Query(BaseModel):
    message: str
    preferences: Optional[Dict] = None
    session_id: Optional[str] = None
    is_followup: bool = False
    model_choice: Optional[str] = "perplexity"  # Default to perplexity

class ProductDetail(BaseModel):
    name: str
    buy_links: List[Dict]
    reviews: List[Dict]

class Response(BaseModel):
    response: str
    product_details: List[ProductDetail] = []
    session_id: str

# Check if a user message is a potential answer to clarification questions
async def is_clarification_answer(message: str, missing_info: List[str]) -> Dict:
    """
    Determine if a user message is answering clarification questions
    Returns extracted preferences if it is, empty dict if not
    """
    # Convert missing_info to lowercase for easier matching
    missing_info_lower = [item.lower() for item in missing_info]
    message_lower = message.lower()
    
    extracted_prefs = {}
    
    # Common patterns for each category of missing info
    patterns = {
        "color": {
            "regex": r"\b(white|black|blue|red|green|yellow|purple|gray|grey|brown|pink|orange)\b",
            "category": "Color"
        },
        "size": {
            "regex": r"\b(small|medium|large|xl|xxl|xs|s|m|l|extra large|extra small)\b|\b(size\s+\d+(\.\d+)?)\b",
            "category": "Size"
        },
        "budget": {
            "regex": r"\$\d+|\b\d+\s+dollars\b|\bunder\s+\$?\d+\b|\b\d+\s*-\s*\d+\b",
            "category": "Budget"
        },
        "brand": {
            "regex": r"\b(nike|adidas|new balance|asics|brooks|hoka|puma|reebok|saucony|under armour)\b",
            "category": "Brand"
        }
    }
    
    # Check for possible answers
    for category_keyword, pattern_data in patterns.items():
        # See if this category is in missing_info
        if any(category_keyword in item for item in missing_info_lower):
            matches = re.findall(pattern_data["regex"], message_lower)
            if matches:
                # Use the first match
                if isinstance(matches[0], tuple):
                    # Some regex matches return tuples, get the first non-empty item
                    value = next((x for x in matches[0] if x), None)
                else:
                    value = matches[0]
                    
                if value:
                    extracted_prefs[pattern_data["category"]] = value.capitalize()
    
    await log(f"Extracted preferences from user message: {extracted_prefs}")
    return extracted_prefs

# Extract keywords from follow-up questions
async def extract_followup_keywords(followup_text: str, original_query: str,
                               previous_requests: List[str] = None,
                               preferences: Dict = None) -> str:
    """
    Extract relevant keywords from follow-up questions while maintaining complete context
    
    Parameters:
    followup_text (str): Current follow-up question
    original_query (str): Original product search query
    previous_requests (List[str]): List of previous follow-up requests
    preferences (Dict): User's confirmed preferences
    
    Returns:
    str: Comma-separated list of keywords representing complete user context
    """
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Build complete context prompt
    context = f"Original product search: \"{original_query}\"\n"
    
    # Add user preferences
    if preferences and len(preferences) > 0:
        preferences_str = ", ".join([f"{k}: {v}" for k, v in preferences.items()])
        context += f"User preferences: {preferences_str}\n"
    
    # Add previous follow-up questions
    if previous_requests and len(previous_requests) > 0:
        requests_str = ", ".join([f"\"{req}\"" for req in previous_requests])
        context += f"Previous follow-up questions: {requests_str}\n"
    
    # Add current follow-up question
    context += f"Current follow-up question: \"{followup_text}\"\n"
    
    prompt = f"""
    Extract the most important product-related keywords from this follow-up question.
    Consider ALL context provided below, including the original query, existing preferences, and all previous follow-up questions.
    Only include terms that would help refine a product search.
    
    IMPORTANT: DO NOT include brand names or price/budget information in your extracted keywords.
    
    Focus on attributes like color, size, features, use case, material, style, purpose, etc.
    Keywords must comprehensively reflect relevant user requirements, including both current and previously mentioned attributes.
    Format as a comma-separated list of 3-5 key terms.
    
    {context}
    
    Complete keywords (excluding brands and price/budget terms):
    """
    
    try:
        await log(f"Extracting keywords from follow-up with full context: '{followup_text}'")
        
        response = client.chat.completions.create(
            model=openai_model_applied,
            messages=[
                {"role": "system", "content": "You are a keyword extraction specialist who maintains context continuity across multiple follow-up questions. You avoid extracting brand names and price information."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100
        )
        
        keywords = response.choices[0].message.content.strip()
        await log(f"Extracted comprehensive context keywords: {keywords}")
        return keywords
    except Exception as e:
        await log(f"Error extracting follow-up keywords: {str(e)}")
        
        # Improved fallback strategy: attempt to combine known information
        fallback = original_query
        if preferences:
            # Filter out brand and price preferences
            filtered_prefs = {k: v for k, v in preferences.items() 
                             if k.lower() not in ['brand', 'price', 'budget']}
            preferences_values = " ".join([str(v) for v in filtered_prefs.values()])
            fallback += f" {preferences_values}"
        fallback += f" {followup_text}"
        return fallback

# Recommendation structure schema
structure_schema = """
Structure your response as follows:\n

Overview: Give a first-person narrative of your analysis and findings of the products, focusing on the their features, descriptions and rationales why this product is recommended. For example, you could begin with something like: "Great news! I've found several products that satisfy your requirements..."
{
    "overview": string,
    "recommendations": [
        {
            "name": string,
            "price": number,
            "features": string[],
            "pros": string[],
            "cons": string[],
            "description": "string explaining why this product is recommended"
        }
    ]
}"""

# Generate dynamic clarification questions
async def generate_dynamic_questions(query: str, missing_info: List[str], model_choice: str = "perplexity") -> Dict:
    """
    Generate customized questions based on missing information identified during analysis
    """
    missing_info_str = ", ".join(missing_info)
    await log(f"Generating dynamic questions for missing info: {missing_info_str}")
    
    messages = [
        {"role": "system", "content": "You are a shopping assistant that generates clarifying questions."},
        {"role": "user", "content": f"""
For the shopping query: "{query}"

The following information is missing: {missing_info_str}

Generate clarifying questions that specifically address the missing information.
For each category of missing information, create:
1. A clear, concise question
2. 3-4 reasonable options as answers

Only generate questions for the missing information, not for already specified details.
Format your response as a JSON object where each key is a category of missing information.

Example format:
{{
  "Budget": {{
    "question": "What's your budget range for this purchase?",
    "options": ["Under $50", "$50-$100", "Over $100"]
  }},
  "Another Category": {{
    "question": "...",
    "options": ["...", "...", "..."]
  }}
}}
"""}
    ]
    
    # Use appropriate model to generate questions
    try:
        if model_choice == "openai":
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=openai_model_applied,
                messages=messages
            )
        else:
            client = OpenAI(
                api_key=PERPLEXITY_API_KEY,
                base_url="https://api.perplexity.ai"
            )
            response = client.chat.completions.create(
                model="sonar-pro", 
                messages=messages
            )
        
        response_text = response.choices[0].message.content
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        # Validate JSON format
        if json_start == -1 or json_end <= json_start:
            await log(f"Invalid JSON structure in generate_dynamic_questions: {response_text}")
            # Provide a default question as fallback
            result = {
                "Details": {
                    "question": "Could you provide more details about what you're looking for?",
                    "options": ["Budget option", "Mid-range", "Premium", "No preference"]
                }
            }
        else:
            result = json.loads(response_text[json_start:json_end])
        
        await log(f"Generated {len(result)} dynamic questions")
        return result
        
    except Exception as e:
        await log(f"Error generating dynamic questions: {str(e)}")
        # Return simple default questions if generation fails
        return {
            "Details": {
                "question": "Could you provide more details about what you're looking for?",
                "options": ["Budget option", "Mid-range", "Premium", "No preference"]
            }
        }

# Generate recommendations
async def generate_recommendations(query: str, preferences: Dict = None, model_choice: str = "perplexity") -> str:
    """Generate recommendations using the specified model"""
    await log(f"\n Generating recommendations using model: {model_choice}")
    
    # # Build enhanced query with user preferences
    # TODO: REMOVE THIS AS query is already enhanced with preferences
    # enhanced_query = query
    # if preferences and len(preferences) > 0:
    #     enhanced_query += f" based on user preferences: {json.dumps(preferences)}"
    
    # Construct messages for the API
    messages = [
        {
            "role": "system",
            "content": "You are a knowledgeable and engaging shopping assistant, acting as a personal researcher and advisor. Your goal is to analyze and present product recommendations in a clear, insightful, and conversational manner—like a helpful shopping guide reporting findings."
        },
        {
            "role": "user",
            "content": query + structure_schema
        }
    ]
    
    await log(f" Enhanced query: {query}")
    
    try:
        if model_choice == "openai":
            # Use OpenAI for recommendations
            await log(f" Using OpenAI API")
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=openai_model_applied,
                messages=messages
            )
            return response.choices[0].message.content
            
        elif model_choice == "hybrid":
            # Get recommendations from both models and combine them
            await log(f" Using hybrid approach with both models")
            
            # Get Perplexity response
            perplexity_client = OpenAI(
                api_key=PERPLEXITY_API_KEY,
                base_url="https://api.perplexity.ai"
            )
            perplexity_response = perplexity_client.chat.completions.create(
                model="sonar-pro",
                messages=messages
            )
            
            # Get OpenAI response
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
            openai_response = openai_client.chat.completions.create(
                model=openai_model_applied,
                messages=messages
            )
            
            # Combine recommendations
            await log(f" Combining recommendations from both models")
            
            try:
                # Parse responses to get structured data
                perplexity_text = perplexity_response.choices[0].message.content
                openai_text = openai_response.choices[0].message.content
                
                # Extract JSON from both responses
                perplexity_json_start = perplexity_text.find('{')
                perplexity_json_end = perplexity_text.rfind('}') + 1
                
                openai_json_start = openai_text.find('{')
                openai_json_end = openai_text.rfind('}') + 1
                
                # Validate JSON markers
                if perplexity_json_start == -1 or perplexity_json_end <= perplexity_json_start:
                    await log(f" Invalid JSON structure in Perplexity response")
                    return openai_response.choices[0].message.content
                
                if openai_json_start == -1 or openai_json_end <= openai_json_start:
                    await log(f" Invalid JSON structure in OpenAI response")
                    return perplexity_response.choices[0].message.content
                
                perplexity_json = json.loads(perplexity_text[perplexity_json_start:perplexity_json_end])
                openai_json = json.loads(openai_text[openai_json_start:openai_json_end])
                
                # Get recommendations from each model
                perplexity_recommendations = perplexity_json.get("recommendations", [])
                openai_recommendations = openai_json.get("recommendations", [])
                
                # Add source label to each recommendation
                for rec in perplexity_recommendations:
                    rec["source"] = "Perplexity"
                
                for rec in openai_recommendations:
                    rec["source"] = "OpenAI"
                
                # Simply combine all recommendations
                combined_recommendations = openai_recommendations + perplexity_recommendations
                
                # Create a combined overview
                combined_overview = "Based on recommendations from multiple AI models: "
                
                # Use either overview as the base
                if "overview" in openai_json:
                    overview = openai_json["overview"]
                    overview = overview.replace("Great news!", "").replace("I've found", "I found")
                    combined_overview += overview.lstrip()
                elif "overview" in perplexity_json:
                    overview = perplexity_json["overview"]
                    overview = overview.replace("Great news!", "").replace("I've found", "I found")
                    combined_overview += overview.lstrip()
                else:
                    combined_overview += "I've found several products that match your requirements."
                
                # Create the combined result
                combined_json = {
                    "overview": combined_overview,
                    "recommendations": combined_recommendations
                }
                
                # Convert to a string
                combined_text = json.dumps(combined_json)
                return combined_text
                
            except Exception as e:
                # If combination fails, fall back to Perplexity response
                await log(f" Error combining recommendations: {str(e)}")
                await log(f" Falling back to Perplexity response")
                return perplexity_response.choices[0].message.content
            
        else:
            # Default to Perplexity
            await log(f" Using Perplexity API")
            client = OpenAI(
                api_key=PERPLEXITY_API_KEY,
                base_url="https://api.perplexity.ai"
            )
            response = client.chat.completions.create(
                model="sonar-pro",
                messages=messages
            )
            return response.choices[0].message.content
            
    except Exception as e:
        await log(f" Error generating recommendations: {str(e)}")
        raise

# Search products using Serper API
async def search_with_serper(query: str, search_type: str) -> Dict:
    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    # Handle shopping and review searches differently
    if search_type == 'buy':
        url = "https://google.serper.dev/shopping"
        payload = {'q': f"{query}"}
        await log(f"[Serper Shopping API] Making request to {url}")
        await log(f"[Serper Shopping API] Query: {query}")
    else:
        payload = {
            'q': f"{query} expert review",
            'num': 3
        }
        await log(f"[Serper Search] Making request to {url}")
        await log(f"[Serper Search] Query: {query} expert review")
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if search_type == 'buy':
            await log(f"[Serper Shopping API] Found {len(result.get('shopping', []))} shopping results")
        else:
            await log(f"[Serper Search] Found {len(result.get('organic', []))} organic results")
        return result
    except Exception as e:
        await log(f"[Serper API Error] {str(e)}")
        return None


# Check if user input is a direct response to clarification questions
async def check_clarification_response(query: Query, session_data: Dict) -> Optional[Dict]:
    """
    Check if the user's input is a direct response to clarification questions
    Returns preferences dict if it is, None if not
    """
    # Skip if we don't have missing_info or are already clarified
    if session_data.get("is_clarified", False) or not session_data.get("missing_info"):
        return None
    
    # Check if we're in clarifying state
    if session_data.get("state") != STATES["CLARIFYING"]:
        return None
    
    # Try to extract preferences from the user message
    preferences = await is_clarification_answer(
        query.message, 
        session_data.get("missing_info", [])
    )
    
    if preferences:
        await log(f"Identified user message as a clarification response with preferences: {preferences}")
        return preferences
    
    return None

# New: Handle initial queries
async def handle_initial_query(session_id: str, query: Query) -> Response:
    """Handle initial queries using state machine logic"""
    
    # Initialize conversation store with enhanced state fields
    conversation_store[session_id] = {
        'query': query.message,
        'preferences': query.preferences or {},
        'previous_recommendations': [],
        'additional_requests': [],
        'model_choice': query.model_choice,
        'state': STATES["INITIAL"],
        'missing_info': [],
        'confidence': 0.0,
        'last_update': datetime.datetime.now().isoformat(),
        'clarification_attempts': 0,
        'clarification_keywords': [],
        'is_clarified': False
    }
    
    # If preferences are already provided, skip analysis and clarification
    # WARNING: THIS SHOULD BE AN IMPOSSIBLE CASE AS THE PREFERENCES OF INITIAL QUERY SHOULD BE EMPTY
    if query.preferences and len(query.preferences) > 0:
        conversation_store[session_id]['state'] = STATES["QUERYING"]
        conversation_store[session_id]['is_clarified'] = True
        
        # Get recommendations
        response_text = await generate_recommendations(
            query.message, 
            query.preferences, 
            query.model_choice
        )
        
        # Process recommendations
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end <= json_start:
                await log(f"Invalid JSON structure in recommendations response: {response_text}")
                return Response(
                    response=response_text,
                    product_details=[],
                    session_id=session_id
                )
            
            json_str = response_text[json_start:json_end]
            recommendations = json.loads(json_str)
            
            # Store recommendations and update state
            if 'recommendations' in recommendations:
                conversation_store[session_id]['previous_recommendations'] = recommendations['recommendations']
                conversation_store[session_id]['state'] = STATES["RECOMMENDING"]
            
            # Start background details fetching
            background_task = asyncio.create_task(
                fetch_product_details_improved(
                    session_id, 
                    query.message, 
                    recommendations.get('recommendations', []),
                    is_followup=False
                )
            )
            
            # Store background task
            conversation_store[session_id]['background_task'] = background_task
            
            # Update state to "searching"
            conversation_store[session_id]['state'] = STATES["SEARCHING"]
            
            return Response(
                response=response_text,
                product_details=[],
                session_id=session_id
            )
                
        except json.JSONDecodeError as json_error:
            await log("JSON Parsing Error: " + str(json_error))
            conversation_store[session_id]['state'] = STATES["ERROR"]
            return Response(response=response_text, product_details=[], session_id=session_id)
    
    # Need to analyze query - enter analyzing state
    conversation_store[session_id]['state'] = STATES["ANALYZING_QUERY"]
    
    # Analyze query specificity
    analysis_result = await analyze_query_specificity(
        query.message, 
        query.preferences, 
        query.model_choice
    )
    
    # Update session and decide next step
    conversation_store[session_id]['state'] = analysis_result["next_state"]
    conversation_store[session_id]['missing_info'] = analysis_result.get("missing_info", [])
    conversation_store[session_id]['confidence'] = analysis_result.get("confidence", 0.0)
    
    # If clarification needed
    if analysis_result["next_state"] == STATES["CLARIFYING"]:
        # Generate dynamic questions
        questions = await generate_dynamic_questions(
            query.message,
            analysis_result["missing_info"],
            query.model_choice
        )
        
        # Extract keywords from questions to help match user responses later
        # keywords = await extract_clarification_keywords(questions)
        # conversation_store[session_id]["clarification_keywords"] = keywords
        
        # Return clarification questions
        return Response(
            response=json.dumps({
                "type": "clarification",
                "questions": questions,
                "reasoning": analysis_result.get("reasoning", ""),
                "confidence": analysis_result.get("confidence", 0.0)
            }),
            product_details=[],
            session_id=session_id
        )
    
    # If query is already specific enough, go directly to recommendation process
    conversation_store[session_id]['state'] = STATES["QUERYING"]
    conversation_store[session_id]['is_clarified'] = True
    
    # Get recommendations
    response_text = await generate_recommendations(
        query.message, 
        query.preferences, 
        query.model_choice
    )
    
    # Process recommendations
    try:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start == -1 or json_end <= json_start:
            await log(f"Invalid JSON structure in recommendations response: {response_text}")
            return Response(
                response=response_text,
                product_details=[],
                session_id=session_id
            )
        
        json_str = response_text[json_start:json_end]
        recommendations = json.loads(json_str)
        
        # Store recommendations and update state
        if 'recommendations' in recommendations:
            conversation_store[session_id]['previous_recommendations'] = recommendations['recommendations']
            conversation_store[session_id]['state'] = STATES["RECOMMENDING"]
        
        # Start background details fetching
        background_task = asyncio.create_task(
            fetch_product_details_improved(
                session_id, 
                query.message, 
                recommendations.get('recommendations', []),
                is_followup=False
            )
        )
        
        # Store background task
        conversation_store[session_id]['background_task'] = background_task
        
        # Update state to "searching"
        conversation_store[session_id]['state'] = STATES["SEARCHING"]
        
        return Response(
            response=response_text,
            product_details=[],
            session_id=session_id
        )
            
    except json.JSONDecodeError as json_error:
        await log("JSON Parsing Error: " + str(json_error))
        conversation_store[session_id]['state'] = STATES["ERROR"]
        return Response(response=response_text, product_details=[], session_id=session_id)

@app.post("/api/chat", response_model=Response)
async def chat(query: Query):
    await log(f"\nNew request received: {query.message}")
    await log(f"Is followup: {query.is_followup}")
    await log(f"Model choice: {query.model_choice}")
    
    session_id = query.session_id if query.session_id else str(uuid.uuid4())
    await log(f"Using session ID: {session_id}")

    try:
        if session_id in conversation_store:
            # For existing sessions, check if the message might be a clarification response first
            session_data = conversation_store[session_id]
            
            # If in clarifying state, check if this is a direct response to questions
            # TODO: REMOVE THIS AS THIS IS DUPLICATED IN handle_followup_query
            # if session_data.get("state") == STATES["CLARIFYING"] and not session_data.get("is_clarified", False):
            #     # TODO
            #     extracted_prefs = await check_clarification_response(query, session_data)
            #     if extracted_prefs:
            #         await log(f"Interpreting user message as answer to clarification questions")
            #         return await process_clarification_response(session_id, extracted_prefs, query)
            
            # Otherwise, proceed as a follow-up
            if not query.is_followup:
                await log(f"Session context found: treating as follow-up regardless of is_followup flag")
            return await handle_followup_query(session_id, query)
        
        await log(f"New session created: treating as initial query")
        return await handle_initial_query(session_id, query)
            
    except Exception as e:
        await log(f"General Error: {str(e)}")
        if session_id in conversation_store:
            conversation_store[session_id]['state'] = STATES["ERROR"]
        raise HTTPException(status_code=500, detail=f"General Error: {str(e)}")

# Improved background task with concurrent API calls
async def fetch_product_details_improved(session_id: str, query_message: str, recommendations: list, is_followup: bool = False, followup_text: str = ""):
    """
    Improved background task to fetch product details and update state
    Uses concurrent API calls for better performance
    """
    try:
        await log(f"\nStarting background task to fetch product details for session: {session_id}")
        
        # Confirm session exists
        if session_id not in conversation_store:
            await log(f"Session {session_id} not found. Cannot update details.")
            return []
        
        # Update state to "fetching details"
        conversation_store[session_id]['state'] = STATES["DETAILING"]
        conversation_store[session_id]['last_update'] = datetime.datetime.now().isoformat()
        
        # Get context
        original_query = query_message
        followup_keywords = ""
        
        if is_followup and session_id in conversation_store:
            # Get complete conversation context
            original_query = conversation_store[session_id].get('query', query_message)
            previous_requests = conversation_store[session_id].get('additional_requests', [])
            preferences = conversation_store[session_id].get('preferences', {})
            
            # Ensure current request isn't duplicated
            current_requests = previous_requests.copy()
            if followup_text and followup_text not in current_requests:
                current_requests.append(followup_text)
            
            # Extract keywords with full context
            if followup_text:
                followup_keywords = await extract_followup_keywords(
                    followup_text,
                    original_query,
                    current_requests[:-1] if current_requests else None,  # Exclude current request from previous
                    preferences
                )
            else:
                # Build a comprehensive query including all requests
                enhanced_query = f"{original_query} {' '.join(current_requests)}"
                followup_keywords = enhanced_query
        
        # Define async functions for concurrent execution
        async def fetch_product_data(product):
            product_name = product['name']
            product_data = {
                'name': product_name,
                'buy_links': [],
                'reviews': None  # Will hold combined review data
            }
            
            # Create focused search context based on query type
            if is_followup and followup_keywords:
                # For follow-ups, use product name + extracted keywords (now includes all context)
                search_context = f"{product_name} {followup_keywords}"
                await log(f"Using comprehensive search context for follow-up: {search_context}")
            else:
                # For initial queries, use original approach
                search_context = f"{product_name} ({original_query})"
                await log(f"Using standard search context: {search_context}")
            
            # Fetch shopping links and reviews concurrently
            buy_task = get_shopping_links(search_context, product_name)
            review_task = get_product_reviews(search_context, product_name, product)
            
            # Wait for both tasks to complete
            buy_links, reviews = await asyncio.gather(buy_task, review_task)
            
            product_data['buy_links'] = buy_links
            product_data['reviews'] = reviews  # This now contains combined review data
            
            return product_data
        
        # Helper function to get shopping links
        async def get_shopping_links(search_context, product_name):
            await log(f"[Shopping Search] Searching for: {search_context}")
            buy_results = await search_with_serper(search_context, 'buy')
            
            buy_links = []
            if buy_results and 'shopping' in buy_results:
                await log(f"[Shopping Results] Found {len(buy_results['shopping'])} total results")
                valid_links = 0
                for item in buy_results['shopping']:
                    price = item.get('price', '')
                    # Filter out used items
                    if 'used' not in price.lower():
                        buy_links.append({
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'price': price,
                            'imageUrl': item.get('imageUrl', '')
                        })
                        valid_links += 1
                        if valid_links >= 3:
                            break
                await log(f"Buy links for {product_name}: {json.dumps(buy_links, indent=2)}")
            
            return buy_links
        
        # Helper function to get product reviews
        async def get_product_reviews(search_context, product_name, product):
            review_context = search_context
            await log(f"[Review Search] Searching for reviews: {review_context}")
            review_results = await search_with_serper(review_context, 'review')
            
            review_items = []
            review_contents = []
            
            if review_results and 'organic' in review_results:
                # Create tasks for each review to fetch content concurrently
                review_tasks = []
                for item in review_results['organic'][:2]:
                    review_url = item.get('link', '')
                    if review_url:
                        # Just store the metadata and create a task to fetch the content
                        review_items.append(item)
                        review_task = get_review_content(review_url)
                        review_tasks.append(review_task)
                
                # Execute all review content fetching tasks concurrently
                if review_tasks:
                    review_contents = await asyncio.gather(*review_tasks)
                    # Filter out empty contents
                    review_contents = [content for content in review_contents if content]
            
            # Return the combined data - we'll process them together later
            return {
                'items': review_items[:len(review_contents)],  # Only keep items with valid content
                'contents': review_contents,
                'pros': product.get('pros', []),
                'cons': product.get('cons', [])
            }
        
        # Function to combine reviews and create a consolidated summary for a product
        async def create_consolidated_review(review_items, review_contents, pros, cons):
            try:
                # Combine all review content
                combined_content = "\n\n".join(review_contents)
                
                # Create individual review objects without summary
                individual_reviews = []
                for i, item in enumerate(review_items):
                    if i < len(review_contents):  # Make sure we have content
                        individual_reviews.append({
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'content': review_contents[i]
                        })
                
                # We'll create a consolidated review with all content
                consolidated_review = {
                    'title': "Consolidated Product Review",
                    'link': individual_reviews[0]['link'] if individual_reviews else "",
                    'individual_reviews': individual_reviews,
                    'combined_content': combined_content,
                    'summary': "",  # Will be populated later
                    'summary_params': {
                        'review_content': combined_content,
                        'pros': pros,
                        'cons': cons
                    }
                }
                
                return consolidated_review
            except Exception as e:
                await log(f"Error creating consolidated review: {str(e)}")
                return None
        
        # Process all products concurrently
        product_tasks = [fetch_product_data(product) for product in recommendations]
        product_data_results = await asyncio.gather(*product_tasks)
        
        # Process the reviews for each product and create consolidated reviews
        consolidated_review_tasks = []
        for product_index, product_data in enumerate(product_data_results):
            review_data = product_data['reviews']
            if review_data and 'items' in review_data and 'contents' in review_data:
                task = create_consolidated_review(
                    review_data['items'],
                    review_data['contents'],
                    review_data['pros'],
                    review_data['cons']
                )
                consolidated_review_tasks.append((product_index, task))
        
        # Get all consolidated reviews
        consolidated_reviews = {}
        for product_index, task in consolidated_review_tasks:
            review = await task
            if review:
                consolidated_reviews[product_index] = review
        
        # Collect all summary tasks for consolidated reviews
        all_summary_tasks = []
        for product_index, review in consolidated_reviews.items():
            # Schedule the summary generation
            task = (product_index, summarize_product_info(
                review['summary_params']['review_content'],
                review['summary_params']['pros'],
                review['summary_params']['cons']
            ))
            all_summary_tasks.append(task)
        
        # Process all summaries in parallel in batches to avoid rate limits
        batch_size = 5
        all_summaries = {}
        
        for i in range(0, len(all_summary_tasks), batch_size):
            batch = all_summary_tasks[i:i+batch_size]
            batch_locations = [loc for loc, _ in batch]
            batch_coros = [coro for _, coro in batch]
            
            # Run this batch in parallel
            batch_results = await asyncio.gather(*batch_coros, return_exceptions=True)
            
            # Store results by their location
            for j, (location, _) in enumerate(batch):
                result = batch_results[j]
                if not isinstance(result, Exception):
                    all_summaries[location] = result
                else:
                    await log(f"Error generating summary: {str(result)}")
                    all_summaries[location] = "Unable to generate summary."
        
        # Now populate all the summaries back into our product details structure
        product_details = []
        for product_index, product_data in enumerate(product_data_results):
            product_detail = {
                'name': product_data['name'],
                'buy_links': product_data['buy_links'],
                'reviews': []
            }
            
            # Add the consolidated review with summary
            if product_index in consolidated_reviews:
                review = consolidated_reviews[product_index]
                # Add the summary
                if product_index in all_summaries:
                    review['summary'] = all_summaries[product_index]
                
                # Create a single review with the consolidated information
                product_detail['reviews'].append({
                    'title': review['title'],
                    'link': review['link'],
                    'snippet': "Consolidated from multiple sources",
                    'content': review['combined_content'],
                    'summary': review['summary'],
                    'individual_reviews': review.get('individual_reviews', [])
                })
            
            product_details.append(product_detail)
        
        # Store product details in conversation store
        if session_id in conversation_store:
            conversation_store[session_id]['product_details'] = product_details
            conversation_store[session_id]['state'] = STATES["READY"]
            conversation_store[session_id]['last_update'] = datetime.datetime.now().isoformat()
            
        await log(f"Completed background task for session: {session_id}, fetched details for {len(product_details)} products")
        return product_details
    except Exception as e:
        await log(f"Error in background task: {str(e)}")
        # Update state to error
        if session_id in conversation_store:
            conversation_store[session_id]['state'] = STATES["ERROR"]
            conversation_store[session_id]['last_update'] = datetime.datetime.now().isoformat()
        return []

# Additional optimization for review content fetching
async def get_review_content(url: str) -> str:
    """
    Optimized function to fetch and extract review content with timeout handling
    """
    await log(f"[Review Scraper] Attempting to fetch content from: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        # Use aiohttp instead of requests for proper async operation
        # Since the existing code uses requests, we'll create a wrapper that's compatible
        # with the existing synchronous code by using asyncio.to_thread
        
        async def fetch_with_timeout():
            try:
                # Using asyncio.to_thread to make the synchronous requests call non-blocking
                response = await asyncio.to_thread(
                    requests.get, url, headers=headers, timeout=10
                )
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for script in soup(['script', 'style']):
                        script.decompose()
                    text = soup.get_text(separator=' ', strip=True)
                    return text
                else:
                    await log(f"[Review Scraper] Failed to fetch content. Status code: {response.status_code}")
                    return ""
            except Exception as e:
                await log(f"[Review Scraper] Error in fetch_with_timeout: {str(e)}")
                return ""
        
        # Set a timeout for the whole operation
        return await asyncio.wait_for(fetch_with_timeout(), timeout=15)
    except asyncio.TimeoutError:
        await log(f"[Review Scraper] Timeout fetching content from: {url}")
        return ""
    except Exception as e:
        await log(f"[Review Scraper Error] {str(e)} for URL: {url}")
        return ""

# # Updated review content fetching using Serper Scrape API
# async def get_review_content(url: str) -> str:
#     """
#     Fetch and extract review content using the Serper Scrape API
#     """
#     await log(f"[Review Scraper] Attempting to fetch content from: {url}")
#     try:
#         # Serper Scrape API endpoint
#         serper_scrape_url = "https://scrape.serper.dev"
        
#         # API headers
#         headers = {
#             'X-API-KEY': SERPER_API_KEY,  # Using the same API key defined at the top
#             'Content-Type': 'application/json'
#         }
        
#         # Request payload
#         payload = json.dumps({
#             "url": url
#         })
        
#         # Make the API request asynchronously
#         async def fetch_with_serper():
#             try:
#                 # Using asyncio.to_thread to make the synchronous requests call non-blocking
#                 response = await asyncio.to_thread(
#                     requests.request,
#                     "POST", 
#                     serper_scrape_url, 
#                     headers=headers, 
#                     data=payload,
#                     timeout=15
#                 )
                
#                 if response.status_code == 200:
#                     # try:
#                     #     result = response.json()
#                     #     # Extract the content from the response
#                     #     if 'content' in result:
#                     #         return result['content']
#                     #     elif 'html' in result:
#                     #         # If only HTML is returned, parse it to extract text
#                     #         soup = BeautifulSoup(result['html'], 'html.parser')
#                     #         for script in soup(['script', 'style']):
#                     #             script.decompose()
#                     #         return soup.get_text(separator=' ', strip=True)
#                     #     else:
#                     #         await log(f"[Review Scraper] No content found in Serper response")
#                     #         return ""
#                     # except json.JSONDecodeError:
#                     #     await log(f"[Review Scraper] Failed to parse JSON response")
#                     print(response.text)
#                     return response.text  # Return raw text if JSON parsing fails
#                 else:
#                     await log(f"[Review Scraper] Failed with status code: {response.status_code}")
#                     return ""
#             except Exception as e:
#                 await log(f"[Review Scraper] Error in fetch_with_serper: {str(e)}")
#                 return ""
        
#         # Set a timeout for the whole operation
#         return await asyncio.wait_for(fetch_with_serper(), timeout=20)
#     except asyncio.TimeoutError:
#         await log(f"[Review Scraper] Timeout fetching content from: {url}")
#         return ""
#     except Exception as e:
#         await log(f"[Review Scraper Error] {str(e)} for URL: {url}")
#         return ""

# Product details endpoint - state-aware
@app.get("/api/product-details/{session_id}")
async def get_product_details(session_id: str):
    """Get product details with current state feedback"""
    if session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_data = conversation_store[session_id]
    current_state = session_data.get('state', STATES["ERROR"])
    
    # Check if background task exists and is still running
    background_task = session_data.get('background_task')
    if background_task and not background_task.done():
        # Task is still running
        return {
            "status": "processing",
            "state": current_state,
            "message": "Product details are still being fetched",
            "product_details": []
        }
    
    # If task is complete
    if current_state in [STATES["SEARCHING"], STATES["DETAILING"]]:
        # Update state to "ready"
        conversation_store[session_id]['state'] = STATES["READY"]
        conversation_store[session_id]['last_update'] = datetime.datetime.now().isoformat()
        current_state = STATES["READY"]
    
    # Return product details
    product_details = session_data.get('product_details', [])
    return {
        "status": "completed", 
        "state": current_state,
        "message": "Product details successfully retrieved",
        "product_details": product_details
    }

# Summarize product information
async def summarize_product_info(review_content: str, pros: list, cons: list) -> str:
    """Summarize review content and pros/cons into a concise paragraph"""
    await log("[Review Summarization] Start to summarize review content and pros/cons")
    client = OpenAI(
        api_key=PERPLEXITY_API_KEY,
        base_url="https://api.perplexity.ai"
    )
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a product review summarizer. Create a concise, balanced summary that combines the review content with the pros and cons."
            },
            {
                "role": "user",
                "content": f"""
Please summarize the following product information into a single paragraph (max 100 words), Don't include any citation number annotations:

Review Content: {review_content}

Pros: {', '.join(pros)}
Cons: {', '.join(cons)}

Focus on the most important points and maintain a balanced perspective."""
            }
        ]

        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=openai_model_applied,
            messages=messages,
            temperature=0.1
        )
        
        return response.choices[0].message.content.strip()
        # return ""
    except Exception as e:
        await log(f"Error summarizing product info: {str(e)}")
        return "Unable to generate summary."

# Switch model endpoint
@app.post("/api/switch-model/{session_id}")
async def switch_model(session_id: str, data: Dict):
    """Switch AI model for an existing conversation"""
    if session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")
    
    new_model = data.get("model_choice")
    if not new_model or new_model not in ["perplexity", "openai", "hybrid"]:
        raise HTTPException(status_code=400, detail="Invalid model choice. Must be 'perplexity', 'openai', or 'hybrid'")
    
    # Update model choice in the conversation store
    conversation_store[session_id]['model_choice'] = new_model
    conversation_store[session_id]['last_update'] = datetime.datetime.now().isoformat()
    
    await log(f"Model switched to {new_model} for session {session_id}")
    
    return {
        "status": "success",
        "message": f"Model switched to {new_model}",
        "session_id": session_id
    }

async def analyze_query_specificity(query: str, preferences: Dict = None, model_choice: str = "perplexity") -> Dict:
    """
    Use GPT-3.5-turbo to analyze if a query is specific enough for product recommendations
    
    Returns:
        Dict: {
            "is_specific": bool,       # Whether the query is specific enough
            "missing_info": List[str],  # Categories of missing information
            "confidence": float,        # Confidence level (0-1)
            "next_state": str,          # Next recommended state
            "reasoning": str            # Reasoning behind the analysis
        }
    """
    # Build enhanced query with any existing preferences
    enhanced_query = query
    if preferences and len(preferences) > 0:
        enhanced_query += f" with preferences: {json.dumps(preferences)}"
    
    await log(f"Analyzing query specificity: '{enhanced_query}'")
    
    # Prepare the prompt
    messages = [
        {"role": "system", "content": "You are an AI that determines if shopping queries need clarification."},
        {"role": "user", "content": f"""
Analyze this shopping query: "{enhanced_query}"

Determine:
1. Is this query specific enough to recommend products? (yes/no)
2. What crucial information is missing? (list specific missing details)
3. Your confidence in understanding the user's needs (0.0-1.0)

Format response as JSON:
{{
  "is_specific": true/false,
  "missing_info": ["budget", "use case", etc],
  "confidence": 0.75,
  "reasoning": "brief explanation of your analysis"
}}
"""}
    ]
    
    # Use GPT-3.5-turbo for analysis for consistent results
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=openai_model_applied,
            messages=messages,
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content
        
        # Extract JSON portion
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response_text[json_start:json_end])
            else:
                await log(f"Invalid JSON structure in response: {response_text}")
                result = {
                    "is_specific": False,
                    "missing_info": ["details"],
                    "confidence": 0.5,
                    "reasoning": "Could not extract specific information needs"
                }
        except json.JSONDecodeError as e:
            await log(f"JSON parsing error: {str(e)}")
            result = {
                "is_specific": False,
                "missing_info": ["details"],
                "confidence": 0.5,
                "reasoning": "Could not parse response"
            }
        
        # Add next state determination
        if result.get("is_specific", False):
            result["next_state"] = STATES["QUERYING"]
        else:
            result["next_state"] = STATES["CLARIFYING"]
        
        await log(f"Query analysis complete: {json.dumps(result)}")
        return result
        
    except Exception as e:
        await log(f"Error analyzing query: {str(e)}")
        # Fallback to clarification if analysis fails
        return {
            "is_specific": False,
            "missing_info": ["details"],
            "confidence": 0.0,
            "next_state": STATES["CLARIFYING"],
            "error": str(e)
        }

async def extract_preferences_from_answer(message: str, missing_info: List[str], model_choice: str = "openai") -> Dict:
    """Use LLM to extract preferences from user answers to clarification questions"""
    
    prompt = f"""
    Extract product preferences from this user message. 
    
    The user is shopping for products and was asked about these details: {', '.join(missing_info)}
    
    User message: "{message}"
    
    Extract ONLY clearly expressed preferences in the user message.
    Return a JSON object with category-value pairs. Use standard category names like Color, Size, Brand, Budget, etc.
    If no preferences are found, return an empty object.
    
    Example response format:
    {{
      "Color": "White",
      "Brand": "Nike"
    }}
    """
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    try:
        response = client.chat.completions.create(
            model=openai_model_applied,
            messages=[
                {"role": "system", "content": "You extract product preferences from user messages"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        response_text = response.choices[0].message.content
        
        # Extract JSON
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                extracted_prefs = json.loads(response_text[json_start:json_end])
                await log(f"Extracted preferences from answer: {extracted_prefs}")
                return extracted_prefs
            else:
                await log("No valid JSON found in extraction response")
                return {}
        except json.JSONDecodeError as e:
            await log(f"JSON parsing error in preference extraction: {str(e)}")
            return {}
            
    except Exception as e:
        await log(f"Error extracting preferences: {str(e)}")
        return {}

async def is_query_specific_enough(query: str, preferences: Dict = None) -> bool:
    """
    Use GPT-3.5-turbo to determine if a query with preferences is specific enough
    Returns boolean indicating if query is ready for recommendations
    """
    # Build enhanced query
    enhanced_query = query
    if preferences and len(preferences) > 0:
        enhanced_query += f" with preferences: {json.dumps(preferences)}"
    
    prompt = f"""
    Is this shopping query specific enough to provide good product recommendations?
    Query: "{enhanced_query}"
    
    Answer only with YES or NO.
    """
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    try:
        response = client.chat.completions.create(
            model=openai_model_applied,
            messages=[
                {"role": "system", "content": "You determine if shopping queries are specific enough"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=5
        )
        
        result = response.choices[0].message.content.strip().lower()
        is_specific = "yes" in result
        
        await log(f"Query specificity check: '{enhanced_query}' -> {is_specific}")
        return is_specific
    except Exception as e:
        await log(f"Error checking query specificity: {str(e)}")
        # Default to true in case of errors to avoid blocking the flow
        return True

async def handle_followup_query(session_id: str, query: Query) -> Response:
    """Handle follow-up queries with improved specificity checking"""
    # Get context
    context = conversation_store[session_id]
    await log(f"Retrieved conversation context for session: {session_id}")
    
    # Check if in clarification state
    if context.get("state") == STATES["CLARIFYING"]:
        # Try to extract preferences from the message
        extracted_prefs = await extract_preferences_from_answer(
            query.message, 
            context.get("missing_info", []),
            query.model_choice
        )
        
        if extracted_prefs:
            await log(f"Identified clarification response with preferences: {extracted_prefs}")
            return await process_clarification_response(session_id, extracted_prefs, query)
    
    # Process as a regular follow-up query
    original_query = context.get('query', '')
    previous_preferences = context.get('preferences', {})
    previous_recommendations = context.get('previous_recommendations', [])
    additional_requests = context.get('additional_requests', [])
    model_choice = query.model_choice or context.get('model_choice', 'perplexity')
    
    # Add new request and update state
    additional_requests.append(query.message)
    conversation_store[session_id]['additional_requests'] = additional_requests
    conversation_store[session_id]['model_choice'] = model_choice
    conversation_store[session_id]['last_update'] = datetime.datetime.now().isoformat()
    
    # Combine all requests into enhanced query
    enhanced_query = f"Original request: {original_query}. "
    if previous_preferences:
        enhanced_query += f"Preferences: {json.dumps(previous_preferences)}. "
    enhanced_query += f"Additional requests: {'. '.join(additional_requests)}"
    
    await log(f"Enhanced query for follow-up: {enhanced_query}")
    
    # Use one of these approaches to determine if query is specific enough:
    
    # Option 1: Check if we have preferences or recommendations already
    has_preferences_or_recommendations = len(previous_preferences) > 0 or len(previous_recommendations) > 0
    
    # Option 2: Let the LLM determine if the query is specific enough
    # is_specific = await is_query_specific_enough(enhanced_query, previous_preferences)
    
    # Choose which approach to use (using Option 1 for efficiency)
    is_clarified = has_preferences_or_recommendations
    conversation_store[session_id]['is_clarified'] = is_clarified
    
    if not is_clarified:
        # Only analyze if we haven't established specificity yet
        await log(f"No previous preferences or recommendations, analyzing follow-up specificity")
        conversation_store[session_id]['state'] = STATES["ANALYZING_QUERY"]
        
        analysis_result = await analyze_query_specificity(
            enhanced_query, 
            previous_preferences, 
            model_choice
        )
        
        conversation_store[session_id]['state'] = analysis_result["next_state"]
        conversation_store[session_id]['missing_info'] = analysis_result.get("missing_info", [])
        conversation_store[session_id]['confidence'] = analysis_result.get("confidence", 0.0)
        
        if analysis_result["next_state"] == STATES["CLARIFYING"]:
            questions = await generate_dynamic_questions(
                enhanced_query,
                analysis_result["missing_info"],
                model_choice
            )
            
            return Response(
                response=json.dumps({
                    "type": "clarification",
                    "questions": questions,
                    "reasoning": analysis_result.get("reasoning", ""),
                    "confidence": analysis_result.get("confidence", 0.0)
                }),
                product_details=[],
                session_id=session_id
            )
    
    # Proceed to recommendations
    conversation_store[session_id]['state'] = STATES["QUERYING"]
    conversation_store[session_id]['state'] = STATES["RECOMMENDING"]
    
    # Get recommendations using the specified model
    response_text = await generate_recommendations(enhanced_query, previous_preferences, model_choice)
    
    # Process recommendations and return response
    try:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start == -1 or json_end <= json_start:
            await log(f"Invalid JSON structure in recommendations response")
            return Response(
                response=response_text,
                product_details=[],
                session_id=session_id
            )
        
        json_str = response_text[json_start:json_end]
        recommendations = json.loads(json_str)
        
        # Store recommendations
        if 'recommendations' in recommendations:
            conversation_store[session_id]['previous_recommendations'] = recommendations['recommendations']
        
        # Start background details fetching
        background_task = asyncio.create_task(
            fetch_product_details_improved(
                session_id, 
                query.message, 
                recommendations.get('recommendations', []), 
                is_followup=True,
                followup_text=query.message
            )
        )
        
        # Store background task
        conversation_store[session_id]['background_task'] = background_task
        
        # Update state to "searching"
        conversation_store[session_id]['state'] = STATES["SEARCHING"]
        
        return Response(
            response=response_text,
            product_details=[],
            session_id=session_id
        )
            
    except json.JSONDecodeError as json_error:
        await log(f"JSON Parsing Error: {str(json_error)}")
        conversation_store[session_id]['state'] = STATES["ERROR"]
        return Response(response=response_text, product_details=[], session_id=session_id)

async def process_clarification_response(session_id: str, extracted_preferences: Dict, query: Query) -> Response:
    """Process user response to clarification questions"""
    session_data = conversation_store[session_id]
    
    # Update preferences
    current_preferences = session_data.get("preferences", {})
    updated_preferences = {**current_preferences, **extracted_preferences}
    conversation_store[session_id]["preferences"] = updated_preferences
    
    # Increment clarification attempts
    clarification_attempts = session_data.get("clarification_attempts", 0) + 1
    conversation_store[session_id]["clarification_attempts"] = clarification_attempts
    
    # Update last update timestamp
    conversation_store[session_id]["last_update"] = datetime.datetime.now().isoformat()
    
    # Get session data
    original_query = session_data.get("query", "")
    model_choice = query.model_choice or session_data.get("model_choice", "perplexity")
    
    # Use LLM to check if we have enough information now
    is_specific = await is_query_specific_enough(original_query, updated_preferences)
    
    # Skip further clarification if:
    # 1. LLM says we have enough info, or
    # 2. We've had 3+ clarification attempts, or
    # 3. We have preferences for at least 2 categories
    skip_further_clarification = (
        is_specific or
        clarification_attempts >= 3 or 
        len(updated_preferences) >= 2
    )
    
    if skip_further_clarification:
        # Force progress to recommendations
        await log(f"Proceeding to recommendations after {clarification_attempts} clarification attempts")
        conversation_store[session_id]["state"] = STATES["QUERYING"]
        conversation_store[session_id]["is_clarified"] = True
        
        # Generate enhanced query
        enhanced_query = original_query
        if updated_preferences:
            enhanced_query += f" with preferences: {json.dumps(updated_preferences)}"
        
        # Generate recommendations
        conversation_store[session_id]["state"] = STATES["RECOMMENDING"]
        response_text = await generate_recommendations(
            enhanced_query,
            updated_preferences,
            model_choice
        )
        
        # Process recommendations
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                recommendations = json.loads(json_str)
                
                # Store recommendations
                if 'recommendations' in recommendations:
                    conversation_store[session_id]['previous_recommendations'] = recommendations['recommendations']
                
                # Start background details fetching
                background_task = asyncio.create_task(
                    fetch_product_details_improved(
                        session_id, 
                        original_query, 
                        recommendations.get('recommendations', []), 
                        is_followup=False
                    )
                )
                
                # Store background task
                conversation_store[session_id]['background_task'] = background_task
                
                # Update state to "searching"
                conversation_store[session_id]['state'] = STATES["SEARCHING"]
        except Exception as e:
            await log(f"Error processing recommendations after clarification: {str(e)}")
        
        return Response(
            response=response_text,
            product_details=[],
            session_id=session_id
        )
    else:
        # Continue with analysis to decide next step
        analysis_result = await analyze_query_specificity(
            original_query, 
            updated_preferences, 
            model_choice
        )
        
        conversation_store[session_id]["state"] = analysis_result["next_state"]
        conversation_store[session_id]["missing_info"] = analysis_result.get("missing_info", [])
        conversation_store[session_id]["confidence"] = analysis_result.get("confidence", 0.0)
        
        if analysis_result["next_state"] == STATES["CLARIFYING"]:
            # Still need clarification
            questions = await generate_dynamic_questions(
                original_query,
                analysis_result["missing_info"],
                model_choice
            )
            
            return Response(
                response=json.dumps({
                    "type": "clarification",
                    "questions": questions,
                    "reasoning": analysis_result.get("reasoning", ""),
                    "confidence": analysis_result.get("confidence", 0.0)
                }),
                product_details=[],
                session_id=session_id
            )
        else:
            # Query is now specific enough
            conversation_store[session_id]["state"] = STATES["QUERYING"]
            conversation_store[session_id]["is_clarified"] = True
            
            # Generate enhanced query and proceed with recommendations
            # (similar to skip_further_clarification block above)
            enhanced_query = original_query
            if updated_preferences:
                enhanced_query += f" with preferences: {json.dumps(updated_preferences)}"
            
            # Generate recommendations
            conversation_store[session_id]["state"] = STATES["RECOMMENDING"]
            response_text = await generate_recommendations(
                enhanced_query,
                updated_preferences,
                model_choice
            )
            
            # Process recommendations (same as above)
            try:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    recommendations = json.loads(json_str)
                    
                    # Store recommendations
                    if 'recommendations' in recommendations:
                        conversation_store[session_id]['previous_recommendations'] = recommendations['recommendations']
                    
                    # Start background details fetching
                    background_task = asyncio.create_task(
                        fetch_product_details_improved(
                            session_id, 
                            original_query, 
                            recommendations.get('recommendations', []), 
                            is_followup=False
                        )
                    )
                    
                    # Store background task
                    conversation_store[session_id]['background_task'] = background_task
                    
                    # Update state to "searching"
                    conversation_store[session_id]['state'] = STATES["SEARCHING"]
            except Exception as e:
                await log(f"Error processing recommendations after clarification: {str(e)}")
            
            return Response(
                response=response_text,
                product_details=[],
                session_id=session_id
            )

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        ws_ping_interval=30,
        ws_ping_timeout=30,
    )