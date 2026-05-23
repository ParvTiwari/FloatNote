import json
import os
import re
from typing import List

from dotenv import load_dotenv
from google import genai
from groq import Groq

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "have",
    "will",
    "about",
    "there",
    "their",
    "while",
    "where",
    "which",
    "when",
    "were",
    "been",
    "being",
    "also",
    "just",
    "more",
    "some",
    "such",
    "than",
    "then",
    "them",
    "they",
    "over",
    "under",
    "very",
    "much",
    "onto",
}


def _normalize_keyword(keyword: str) -> str:
    return re.sub(r"\s+", " ", str(keyword or "")).strip(" -_,.;:()[]{}")


def _is_useful_keyword(keyword: str) -> bool:
    lowered = keyword.lower()
    if not lowered:
        return False
    if lowered in STOPWORDS:
        return False
    if len(lowered) <= 2 and not keyword.isupper():
        return False
    if not re.search(r"[a-zA-Z]", keyword):
        return False
    if len(set(re.findall(r"[a-zA-Z]", lowered))) == 1 and len(lowered) > 3:
        return False
    return True


def _local_filter(keywords: List[str]) -> List[str]:
    filtered = []
    seen = set()

    for keyword in keywords:
        cleaned = _normalize_keyword(keyword)
        key = cleaned.lower()
        if not _is_useful_keyword(cleaned):
            continue
        if key in seen:
            continue
        seen.add(key)
        filtered.append(cleaned)

    return filtered


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
    except Exception:
        match = re.search(r"\{.*?\}", content, re.DOTALL)
        if not match:
            return fallback
        try:
            return list(set(json.loads(match.group()).get("keywords", fallback)))
        except Exception:
            return fallback


def gemini_filter(input_text: str, fallback: List[str]) -> List[str] | None:
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
        print("Gemini failed:", e)
        return None


def groq_filter(input_text: str, fallback: List[str]) -> List[str] | None:
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
        print("Groq failed:", e)
        return None


def filter_keywords(keywords: List[str]) -> List[str]:
    if not keywords:
        return []

    fallback = _local_filter(keywords)
    input_text = "\n".join(fallback)

    result = gemini_filter(input_text, fallback)
    if result is not None:
        return _local_filter(result)

    result = groq_filter(input_text, fallback)
    if result is not None:
        return _local_filter(result)

    return fallback
