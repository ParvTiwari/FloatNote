import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ai_modules.utils.meeting_content import (
    clean_meeting_text,
    is_useful_audio_text,
    is_useful_ocr_text,
)

BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV_PATH)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_CHAT_MODEL = os.getenv(
    "GROQ_CHAT_MODEL",
    "llama-3.3-70b-versatile",
)
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
USE_FAISS = os.getenv("CHATBOT_USE_FAISS", "false").strip().lower() == "true"
QUESTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "please",
    "show",
    "tell",
    "the",
    "there",
    "these",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def _safe_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_action(action):
    if isinstance(action, dict):
        task = _safe_str(action.get("task"))
        assignee = _safe_str(action.get("assignee"))
        if task and assignee:
            return f"{assignee}: {task}"
        return task
    return _safe_str(action)


def convert_to_documents(all_data):
    docs = []

    for item in all_data:
        source = _safe_str(item.get("source")) or "audio"
        raw_text = _safe_str(item.get("text"))
        cleaned_text = clean_meeting_text(raw_text, source)

        if not cleaned_text:
            continue
        if source == "ocr" and not is_useful_ocr_text(raw_text):
            continue
        if source != "ocr" and not is_useful_audio_text(raw_text):
            continue

        speaker = _safe_str(item.get("speaker"))
        prefix = speaker or ("OCR" if source == "ocr" else "Speaker")
        parts = [f"{prefix}: {cleaned_text}"]

        keywords = [_safe_str(keyword) for keyword in item.get("keywords", []) if _safe_str(keyword)]
        if keywords:
            parts.append("Keywords: " + ", ".join(keywords))

        actions = [_normalize_action(action) for action in (item.get("actions") or item.get("action_items") or [])]
        actions = [action for action in actions if action]
        if actions:
            parts.append("Actions: " + ", ".join(actions))

        docs.append(
            Document(
                page_content="\n".join(parts),
                metadata={
                    "source": source,
                    "speaker": speaker or None,
                },
            )
        )

    return docs


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", _safe_str(text).lower())


def _significant_tokens(text):
    return [
        token
        for token in _tokenize(text)
        if token not in QUESTION_STOPWORDS and len(token) > 1
    ]


class _SimpleRetriever:
    def __init__(self, docs, k=4):
        self.docs = docs
        self.k = k

    def invoke(self, query):
        query_tokens = set(_significant_tokens(query) or _tokenize(query))
        if not query_tokens:
            return self.docs[: self.k]

        scored = []
        for doc in self.docs:
            lowered = doc.page_content.lower()
            doc_tokens = set(_tokenize(doc.page_content))
            overlap = len(query_tokens.intersection(doc_tokens))
            phrase_bonus = sum(2 for token in query_tokens if len(token) >= 4 and token in lowered)
            structure_bonus = 0
            if "keywords:" in lowered:
                structure_bonus += 1
            if "actions:" in lowered:
                structure_bonus += 2
            if lowered.startswith("ocr:") and "screen" in query.lower():
                structure_bonus += 2

            score = overlap * 4 + phrase_bonus + structure_bonus
            if score > 0:
                scored.append((score, doc))

        if not scored:
            return self.docs[: self.k]

        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[: self.k]]


class _SimpleVectorStore:
    def __init__(self, docs):
        self.docs = docs

    def as_retriever(self, search_kwargs=None):
        search_kwargs = search_kwargs or {}
        k = int(search_kwargs.get("k", 4))
        return _SimpleRetriever(self.docs, k=k)


def _split_documents(docs):
    if not docs:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
    )
    return splitter.split_documents(docs)


def create_vector_store(docs):
    chunks = _split_documents(docs)
    if not chunks:
        return _SimpleVectorStore([])

    if not USE_FAISS:
        return _SimpleVectorStore(chunks)

    try:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        return FAISS.from_documents(chunks, embeddings)
    except Exception as exc:
        print(f"FAISS fallback active: {exc}")
        return _SimpleVectorStore(chunks)


def _call_groq(messages, model, temperature=0.1, max_completion_tokens=500):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in backend/.env")

    response = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
        },
        timeout=60,
    )
    if not response.ok:
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        error_info = payload.get("error", {}) if isinstance(payload, dict) else {}
        error_code = _safe_str(error_info.get("code"))
        error_message = _safe_str(error_info.get("message"))

        if error_code == "expired_api_key":
            raise ValueError("Groq API key has expired. Update GROQ_API_KEY in backend/.env.")
        if response.status_code == 401:
            raise ValueError(error_message or "Groq rejected the API key. Check GROQ_API_KEY in backend/.env.")

        response.raise_for_status()

    payload = response.json()
    return (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )


def _extract_evidence_lines(docs, query, limit=6):
    query_tokens = set(_significant_tokens(query) or _tokenize(query))
    scored = []

    for doc_index, doc in enumerate(docs):
        for line_index, raw_line in enumerate(doc.page_content.splitlines()):
            line = raw_line.strip()
            if not line:
                continue

            lowered = line.lower()
            line_tokens = set(_tokenize(line))
            overlap = len(query_tokens.intersection(line_tokens))
            phrase_bonus = sum(2 for token in query_tokens if len(token) >= 4 and token in lowered)
            score = overlap * 4 + phrase_bonus

            if lowered.startswith("actions:"):
                score += 2
            if lowered.startswith("keywords:"):
                score += 1

            if score > 0:
                scored.append((score, doc_index, line_index, line))

    scored.sort(key=lambda item: (item[0], -item[1], -item[2]), reverse=True)

    evidence = []
    seen = set()
    for _, _, _, line in scored:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        evidence.append(line)
        if len(evidence) >= limit:
            break

    return evidence


def _format_context(docs, query):
    evidence = _extract_evidence_lines(docs, query, limit=6)
    if evidence:
        return "\n".join(f"- {line}" for line in evidence)

    blocks = []
    seen = set()
    for doc in docs:
        content = doc.page_content.strip()
        if not content or content in seen:
            continue
        seen.add(content)
        blocks.append(content)
        if len(blocks) >= 4:
            break

    return "\n\n".join(blocks)


def _fallback_answer(query, docs):
    del query
    if not docs:
        return "I could not find anything relevant in the current meeting data."
    return "I could not answer from Groq right now. Please try again in a moment."


def ask_question_debug(query, vector_db):
    clean_query = _safe_str(query)
    if not clean_query:
        return {
            "question": clean_query,
            "answer": "Please ask a question.",
            "model": None,
            "context": "",
            "retrieved_documents": [],
            "used_groq": False,
            "error": None,
        }

    retriever = vector_db.as_retriever(search_kwargs={"k": 5})
    docs = retriever.invoke(clean_query)
    if not docs:
        return {
            "question": clean_query,
            "answer": "I could not find anything relevant in the current meeting data.",
            "model": None,
            "context": "",
            "retrieved_documents": [],
            "used_groq": False,
            "error": None,
        }

    context = _format_context(docs, clean_query)
    if not context:
        return {
            "question": clean_query,
            "answer": "I could not find anything relevant in the current meeting data.",
            "model": None,
            "context": "",
            "retrieved_documents": [doc.page_content for doc in docs],
            "used_groq": False,
            "error": None,
        }

    model = DEFAULT_GROQ_CHAT_MODEL
    messages = [
        {
            "role": "system",
            "content": (
                "You are a meeting assistant built using a simple RAG pipeline: retrieve relevant meeting context, "
                "inject it into the prompt, and answer only from that context. "
                "Teach in a clear, beginner-friendly style similar to an educational explainer. "
                "Do not use outside knowledge. "
                "If the context is missing or insufficient, reply exactly: "
                "'I could not find that in the current meeting data.' "
                "Keep the answer concise, factual, and easy to understand."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Retrieved context from the current meeting:\n{context}\n\n"
                f"Question: {clean_query}\n\n"
                "Answer only from the retrieved context. If useful, synthesize the context into a short explanation."
            ),
        },
    ]

    try:
        answer = _call_groq(messages, model=model)
        return {
            "question": clean_query,
            "answer": answer or "I could not find that in the current meeting data.",
            "model": model,
            "context": context,
            "retrieved_documents": [doc.page_content for doc in docs],
            "used_groq": True,
            "error": None,
        }
    except Exception as exc:
        print(f"Groq chatbot failed: {exc}")
        return {
            "question": clean_query,
            "answer": _fallback_answer(clean_query, docs),
            "model": model,
            "context": context,
            "retrieved_documents": [doc.page_content for doc in docs],
            "used_groq": False,
            "error": str(exc),
        }


def ask_question(query, vector_db):
    return ask_question_debug(query, vector_db)["answer"]
