import os
import json
import re
from typing import List

from google import genai
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


def build_prompt(input_text: str) -> str:
    return f"""
You are an intelligent meeting assistant.

Task:
Filter and refine keywords.

Rules:
- Return ONLY JSON
- Format: {{"keywords": ["keyword1", "keyword2"]}}
- Remove duplicates
- Keep important short terms like AI, ML, US
- Remove irrelevant or noisy words

Keywords:
{input_text}
"""

def parse_response(content: str, fallback: List[str]) -> List[str]:
    try:
        return list(set(json.loads(content).get("keywords", fallback)))
    except:
        match = re.search(r"\{.*?\}", content, re.DOTALL)
        if not match:
            return fallback
        try:
            return list(set(json.loads(match.group()).get("keywords", fallback)))
        except:
            return fallback

def gemini_filter(input_text: str, fallback: List[str]) -> List[str]:
    if not gemini_client:
        return None

    try:
        response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=build_prompt(input_text),
            config={"temperature": 0},
        )
        print("GEMINI RESPONSE")
        return parse_response(response.text.strip(), fallback)
    except Exception as e:
        print("⚠ Gemini failed:", e)
        return None

def groq_filter(input_text: str, fallback: List[str]) -> List[str]:
    if not groq_client:
        return None

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": build_prompt(input_text)},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content.strip()
        print("GROQ RESPONSE")
        return parse_response(content, fallback)

    except Exception as e:
        print("⚠ Groq failed:", e)
        return None
    
def filter_keywords(keywords: List[str]) -> List[str]:
    if not keywords:
        return []
    
    keywords = list(set([k.strip().lower() for k in keywords if k.strip()]))

    if len(keywords) <= 6:
        return keywords

    input_text = ", ".join(keywords)

    result = gemini_filter(input_text, keywords)
    if result is not None:
        return result
    
    result = groq_filter(input_text, keywords)
    if result is not None:
        return result

    return list(keywords)