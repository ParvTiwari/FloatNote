from backend.ai_modules.nlp.keyword_extraction import extract_keywords
from backend.ai_modules.nlp.intent_detection import detect_intent

def process_text(text: str):
    return {
        "text": text,
        "keywords": extract_keywords(text),
        "intent": detect_intent(text)
    }