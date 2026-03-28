import os

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

DEFAULT_CHAT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

import warnings
warnings.filterwarnings(
    "ignore",
    message="`resume_download` is deprecated"
)

def convert_to_documents(all_data):
    docs = []

    for item in all_data:
        content = ""

        if item["speaker"]:
            content += f"{item['speaker']}: "
        else:
            content += f"{item['source']}: "

        content += item["text"]

        if item.get("keywords"):
            content += f"\nKeywords: {', '.join(item['keywords'])}"

        if item.get("actions"):
            content += f"\nActions: {', '.join(item['actions'])}"

        docs.append(Document(page_content=content))

    return docs


def create_vector_store(docs):
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return FAISS.from_documents(docs, embeddings)


def get_llm():
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

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

    llm = get_llm()
    response = llm.invoke(messages)
    return response.content.strip()
