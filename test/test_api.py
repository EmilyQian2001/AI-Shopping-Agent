import requests
from pydantic import BaseModel

class AnswerFormat(BaseModel):
    first_name: str
    last_name: str
    year_of_birth: int
    num_seasons_in_nba: int

url = "https://api.perplexity.ai/chat/completions"
headers = {"Authorization": "Bearer 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"}
payload = {
    "model": "sonar",
    "messages": [
        {"role": "system", "content": "Be precise and concise."},
        {"role": "user", "content": (
            "Tell me about Michael Jordan. "
        )},
    ],
    "response_format": {
		    "type": "json_schema",
        "json_schema": {"schema": AnswerFormat.model_json_schema()},
    },
}
response = requests.post(url, headers=headers, json=payload).json()
print(response["choices"][0]["message"]["content"])
