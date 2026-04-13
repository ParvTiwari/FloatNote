import os
import re
from collections import Counter

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from ai_modules.utils.meeting_content import (
    clean_meeting_text,
    is_useful_audio_text,
    is_useful_ocr_text,
)

load_dotenv()

DEFAULT_CHAT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
USE_FAISS = os.getenv("CHATBOT_USE_FAISS", "false").strip().lower() == "true"
USE_HF_LLM = os.getenv("CHATBOT_USE_HF_LLM", "false").strip().lower() == "true"
OCR_QUERY_TERMS = {"ocr", "screen", "slide", "document", "page", "table", "tables", "screen text"}
SUMMARY_QUERY_TERMS = {"summary", "summarize", "little summary", "brief", "overview", "short summary"}

import warnings
warnings.filterwarnings(
    "ignore",
    message="`resume_download` is deprecated"
)

def convert_to_documents(all_data):
    docs = []

    for item in all_data:
        content = ""
        speaker = item.get("speaker")
        source = item.get("source", "unknown")
        raw_text = item.get("text", "").strip()
        text = clean_meeting_text(raw_text, source)

        if not text:
            continue
        if source == "ocr" and not is_useful_ocr_text(raw_text):
            continue
        if source != "ocr" and not is_useful_audio_text(raw_text):
            continue

        if speaker:
            content += f"{speaker}: "
        else:
            content += f"{source}: "

        content += text

        if item.get("keywords"):
            content += f"\nKeywords: {', '.join(item['keywords'])}"

        actions = item.get("actions") or item.get("action_items") or []
        if actions:
            formatted_actions = []
            for action in actions:
                if isinstance(action, dict):
                    task = action.get("task", "Unknown Task")
                    assignee = action.get("assignee")
                    formatted_actions.append(
                        f"{task} ({assignee})" if assignee else task
                    )
                else:
                    formatted_actions.append(str(action))
            content += f"\nActions: {', '.join(formatted_actions)}"

        docs.append(Document(page_content=content))

    return docs


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


class _SimpleRetriever:
    def __init__(self, docs, k=4):
        self.docs = docs
        self.k = k

    def invoke(self, query):
        query_tokens = set(_tokenize(query))
        query_lower = query.lower()
        wants_ocr = any(term in query_lower for term in OCR_QUERY_TERMS)
        if not query_tokens:
            return self.docs[: self.k]

        scored = []
        for doc in self.docs:
            doc_tokens = set(_tokenize(doc.page_content))
            overlap = len(query_tokens.intersection(doc_tokens))
            if overlap > 0:
                source_bonus = 0
                lowered = doc.page_content.lower()
                if lowered.startswith("ocr:"):
                    source_bonus = 2 if wants_ocr else -1
                else:
                    source_bonus = 2

                action_bonus = 1 if "actions:" in lowered and any(
                    word in query_lower for word in ("action", "task", "todo", "follow up")
                ) else 0
                scored.append((overlap + source_bonus + action_bonus, doc))

        if scored:
            scored.sort(key=lambda pair: pair[0], reverse=True)
            return [doc for _, doc in scored[: self.k]]
        return self.docs[: self.k]


class _SimpleVectorStore:
    def __init__(self, docs):
        self.docs = docs

    def as_retriever(self, search_kwargs=None):
        search_kwargs = search_kwargs or {}
        k = int(search_kwargs.get("k", 4))
        return _SimpleRetriever(self.docs, k=k)


def create_vector_store(docs):
    if not docs:
        return _SimpleVectorStore([])
    if not USE_FAISS:
        return _SimpleVectorStore(docs)
    try:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        return FAISS.from_documents(docs, embeddings)
    except Exception as exc:
        print(f"Chatbot retrieval fallback active (embedding error): {exc}")
        return _SimpleVectorStore(docs)


def get_llm():
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

    if not USE_HF_LLM:
        raise ValueError("CHATBOT_USE_HF_LLM is disabled.")

    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    model_name = os.getenv("HUGGINGFACE_CHAT_MODEL", DEFAULT_CHAT_MODEL)

    if not token:
        raise ValueError("HUGGINGFACEHUB_API_TOKEN is missing in backend/.env")

    endpoint = HuggingFaceEndpoint(
        repo_id=model_name,
        task="text-generation",
        huggingfacehub_api_token=token,
        max_new_tokens=256,
        temperature=0.2,
        top_p=0.9,
        do_sample=False,
        return_full_text=False,
        timeout=120,
    )

    return ChatHuggingFace(llm=endpoint)


def _extract_actions(docs):
    actions = []
    for doc in docs:
        for line in doc.page_content.splitlines():
            if line.lower().startswith("actions:"):
                for action in line.split(":", 1)[1].split(","):
                    cleaned = action.strip(" -")
                    if cleaned:
                        actions.append(cleaned)
    return list(dict.fromkeys(actions))


def _extract_keywords(docs):
    keywords = []
    for doc in docs:
        for line in doc.page_content.splitlines():
            if line.lower().startswith("keywords:"):
                for keyword in line.split(":", 1)[1].split(","):
                    cleaned = keyword.strip(" -")
                    if cleaned:
                        keywords.append(cleaned)
    return [kw for kw, _ in Counter(keywords).most_common(6)]


def _fallback_answer(clean_query, docs):
    if not docs:
        return "I could not find anything relevant in the meeting data."

    query_lower = clean_query.lower()
    actions = _extract_actions(docs)

    if any(term in query_lower for term in SUMMARY_QUERY_TERMS):
        summary_lines = []
        for doc in docs:
            first_line = doc.page_content.splitlines()[0].strip()
            if first_line.lower().startswith("ocr:"):
                continue
            if first_line and first_line not in summary_lines:
                summary_lines.append(first_line)
            if len(summary_lines) == 2:
                break

        if not summary_lines:
            for doc in docs:
                first_line = doc.page_content.splitlines()[0].strip()
                if first_line and first_line not in summary_lines:
                    summary_lines.append(first_line)
                if len(summary_lines) == 2:
                    break

        if summary_lines:
            cleaned = []
            for line in summary_lines:
                cleaned.append(re.sub(r"^[A-Za-z0-9_ ]+:\s*", "", line).strip())
            return "Short summary: " + " ".join(cleaned[:2])

    if any(word in query_lower for word in ("action", "task", "todo", "follow up")) and actions:
        return "Here are the action items I found:\n- " + "\n- ".join(actions[:6])

    if any(word in query_lower for word in ("keyword", "topic", "theme")):
        keywords = _extract_keywords(docs)
        if keywords:
            return "Main topics mentioned were: " + ", ".join(keywords) + "."

    if any(word in query_lower for word in OCR_QUERY_TERMS):
        ocr_lines = []
        for doc in docs:
            if doc.page_content.lower().startswith("ocr:"):
                first_line = doc.page_content.splitlines()[0].replace("ocr:", "", 1).strip()
                if first_line and first_line not in ocr_lines:
                    ocr_lines.append(first_line)
        if ocr_lines:
            return "From the captured screen content, I found:\n- " + "\n- ".join(ocr_lines[:4])
        # Fall through to general meeting context if OCR is unavailable but transcript text still matches.

    top_lines = []
    for doc in docs[:3]:
        line = doc.page_content.splitlines()[0].strip()
        if line and line not in top_lines:
            top_lines.append(line)

    if not top_lines:
        return "I found related meeting context, but it was too sparse to answer confidently."

    return "Based on the meeting notes:\n- " + "\n- ".join(top_lines)


def ask_question(query, vector_db):
    clean_query = query.strip()
    if not clean_query:
        return "Please ask a question."

    retriever = vector_db.as_retriever(search_kwargs={"k": 4})
    docs = retriever.invoke(clean_query)

    if not docs:
        return "I could not find anything relevant in the meeting data."

    context = "\n\n".join(doc.page_content for doc in docs)
    messages = [
        SystemMessage(
            content=(
                "You are a meeting assistant. "
                "Answer only from the provided context. "
                "If the answer is not in the context, say that clearly. "
                "Do not invent facts, do not ask follow-up questions, and keep the answer concise."
            )
        ),
        HumanMessage(
            content=(
                f"Context:\n{context}\n\n"
                f"Question: {clean_query}\n\n"
                "Answer in 2 to 4 sentences."
            )
        ),
    ]

    try:
        llm = get_llm()
        response = llm.invoke(messages)
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = " ".join(
                chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                for chunk in content
            )
        final = str(content).strip()
        if final:
            return final
    except Exception as exc:
        print(f"Chatbot generation fallback active (LLM error): {exc}")

    return _fallback_answer(clean_query, docs)
