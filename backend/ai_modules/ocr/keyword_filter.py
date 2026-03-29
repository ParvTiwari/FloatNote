import os
import json
import re
from typing import List
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("Add GROQ_API_KEY to .env")
    client = None
else: 
    client = Groq(api_key=GROQ_API_KEY)

def filter_keywords(keywords: List[str]) -> List[str]:
    if not keywords:
        return []
    
    if client is None:
        return list(set(keywords))

    input_text = ", ".join(keywords)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an intelligent meeting assistant. Your job is to filter and refine keywords. Remove duplicates, irrelevant words, and noise. Keep only meaningful, important keywords."},
                {
                    "role": "user", "content": f"""
    Filter the following keywords.

    Rules:
    - Return ONLY JSON
    - Format: {{"keywords": ["keyword1", "keyword2"]}}
    - Remove duplicates
    - Keep important short terms like AI, ML, US
    - Remove irrelevant or noisy words

    Keywords:
    {input_text}
    """,
                },
            ],
            temperature=0.3,
            max_completion_tokens=1024,
        )

        content = response.choices[0].message.content.strip()
        cleaned = re.search(r"\{.*\}", content, re.DOTALL)

        if not cleaned:
            return list(set(keywords))
        
        parsed = json.loads(cleaned.group())
        if "keywords" in parsed:
            return list(set(parsed["keywords"]))
        
    except Exception as e:
        print("⚠ LLM failed:", e)
    
    return list(set(keywords))