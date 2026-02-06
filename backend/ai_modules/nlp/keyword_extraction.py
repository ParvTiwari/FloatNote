import spacy

nlp = spacy.load("en_core_web_sm")

def extract_keywords(text: str, top_k: int = 5):
    doc = nlp(text)
    keywords = set()

    for chunk in doc.noun_chunks:
        if len(chunk.text.split()) <= 4:
            keywords.add(chunk.text.lower())

    return list(keywords)[:top_k]