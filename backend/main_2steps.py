from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from typing import List, Dict, Optional
import json
import requests
from bs4 import BeautifulSoup
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PERPLEXITY_API_KEY = "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"
SERPER_API_KEY = "87821b459158327ffe7e3dacda3cc9272039e8c4"
GPT4_API_KEY = "YOUR_GPT4_API_KEY"  # 需要添加GPT-4 API密钥

class Query(BaseModel):
    message: str
    preferences: Optional[Dict] = None

class ProductDetail(BaseModel):
    name: str
    buy_links: List[Dict]
    reviews: List[Dict]

class Response(BaseModel):
    response: str
    product_details: List[ProductDetail] = []

async def generate_clarifications(client: OpenAI, user_query: str) -> Dict:
    messages = [
        {"role": "system", "content": "You are a shopping assistant. Determine if more clarifications are needed for the user's query."},
        {"role": "user", "content": f"""
Determine if the following query needs more clarifications before making a product recommendation. 
If needed, generate 3-4 structured questions, covering:
1. Budget (with 3 price ranges as options)
2. Usage scenarios (with 2-3 use case options)
3. Important features (with 3-4 feature options)

Format response as JSON exactly like this example:
{{
    "needs_clarification": true,
    "questions": {{
        "Budget": {{
            "question": "What's your budget range?",
            "options": ["$300", "$600", "$1000"]
        }},
        "Usage": {{
            "question": "Primary use?",
            "options": ["option1", "option2", "option3"]
        }},
        "Features": {{
            "question": "Most important feature?",
            "options": ["feature1", "feature2", "feature3"]
        }}
    }}
}}

User query: {user_query}
"""}
    ]
    response = client.chat.completions.create(model="sonar-pro", messages=messages)
    response_text = response.choices[0].message.content
    json_start = response_text.find('{')
    json_end = response_text.rfind('}') + 1
    return json.loads(response_text[json_start:json_end])

async def generate_natural_language_recommendations(client: OpenAI, query: str) -> str:
    """使用Perplexity生成自然语言推荐"""
    messages = [
        {
            "role": "system",
            "content": "You are a knowledgeable shopping assistant. Provide detailed product recommendations in natural language, including product names, key features, pros and cons, and price ranges."
        },
        {
            "role": "user",
            "content": query
        }
    ]
    
    response = client.chat.completions.create(
        model="sonar-pro",
        messages=messages
    )
    
    return response.choices[0].message.content

class ProductRecommendation(BaseModel):
    name: str
    price: float
    features: list[str]
    pros: list[str]
    cons: list[str]

class RecommendationResponse(BaseModel):
    recommendations: list[ProductRecommendation]

async def convert_to_structured_json(natural_response: str) -> Dict:
    """使用GPT-4将自然语言推荐转换为结构化输出"""
    gpt4_client = OpenAI(api_key=GPT4_API_KEY)
    
    completion = gpt4_client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {
                "role": "system", 
                "content": "Convert the following product recommendations into structured format."
            },
            {
                "role": "user",
                "content": f"Extract product recommendations from this text:\n{natural_response}"
            }
        ],
        response_format=RecommendationResponse
    )
    
    return completion.choices[0].message.parsed.model_dump()

def search_with_serper(query: str, search_type: str) -> Dict:
    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': SERPER_API_KEY,
        'Content-Type': 'application/json'
    }
    
    if search_type == 'buy':
        url = "https://google.serper.dev/shopping"
        payload = {'q': f"{query}"}
    else:
        payload = {
            'q': f"{query} expert review",
            'num': 3
        }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Search Error: {str(e)}")
        return None

def get_review_content(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(['script', 'style']):
            script.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return text[:2000]
    except Exception as e:
        print(f"Review Extraction Error: {str(e)}")
        return ""

@app.post("/api/chat", response_model=Response)
async def chat(query: Query):
    try:
        client = OpenAI(
            api_key=PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai"
        )
        
        # Handle clarification questions
        if not query.preferences:
            try:
                clarification_response = await generate_clarifications(client, query.message)
                return Response(
                    response=json.dumps({
                        "type": "clarification",
                        "questions": clarification_response["questions"]
                    }),
                    product_details=[]
                )
            except Exception as e:
                print(f"Error generating questions: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to generate questions")
            
        # 构建增强查询
        enhanced_query = query.message
        if query.preferences:
            enhanced_query += f" based on user preferences: {json.dumps(query.preferences)}"
        
        print("Sending query to API:", enhanced_query)

        # 第一步：生成自然语言推荐
        natural_recommendations = await generate_natural_language_recommendations(client, enhanced_query)
        print("Natural Language Recommendations:", natural_recommendations)
        
        # 第二步：转换为结构化JSON
        structured_recommendations = await convert_to_structured_json(natural_recommendations)
        print("Structured Recommendations:", json.dumps(structured_recommendations, indent=2))
        
        product_details = []
        
        if 'recommendations' in structured_recommendations:
            for product in structured_recommendations['recommendations']:
                product_name = product['name']
                product_data = {
                    'name': product_name,
                    'buy_links': [],
                    'reviews': []
                }
                
                # Get shopping results
                buy_results = search_with_serper(product_name, 'buy')
                if buy_results and 'shopping' in buy_results:
                    valid_links = 0
                    for item in buy_results['shopping']:
                        price = item.get('price', '')
                        if 'used' not in price.lower():
                            product_data['buy_links'].append({
                                'title': item.get('title', ''),
                                'link': item.get('link', ''),
                                'price': price,
                                'imageUrl': item.get('imageUrl', '')
                            })
                            valid_links += 1
                            if valid_links >= 3:
                                break
                
                # Get review results
                review_results = search_with_serper(product_name, 'review')
                if review_results and 'organic' in review_results:
                    for item in review_results['organic'][:2]:
                        review_url = item.get('link', '')
                        if review_url:
                            review_content = get_review_content(review_url)
                            product_data['reviews'].append({
                                'title': item.get('title', ''),
                                'link': review_url,
                                'snippet': item.get('snippet', ''),
                                'content': review_content
                            })
                product_details.append(product_data)
                time.sleep(1)
        
        # 返回两段式结果
        return Response(
            response=json.dumps({
                "natural_response": natural_recommendations,
                "structured_recommendations": structured_recommendations
            }),
            product_details=product_details
        )
            
    except Exception as e:
        print("General Error:", str(e))
        raise HTTPException(status_code=500, detail=f"General Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)