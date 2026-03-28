import os
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings, ChatHuggingFace

load_dotenv()

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
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vector_db = FAISS.from_documents(docs, embeddings)

    return vector_db

def get_llm():
    import os
    from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace

    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")

    if not token:
        raise ValueError("❌ HuggingFace token missing in .env")

    base_llm = HuggingFaceEndpoint(
        repo_id="HuggingFaceH4/zephyr-7b-beta",
        task="conversational",
        temperature=0,
        max_new_tokens=30,
        huggingfacehub_api_token=token,
    )

    llm = ChatHuggingFace(llm=base_llm)

    return llm

def ask_question(query, vector_db):
    retriever = vector_db.as_retriever()

    docs = retriever.invoke(query)

    context = "\n".join([doc.page_content for doc in docs])

    prompt = f"""
    You are a meeting assistant.

    Answer ONLY the given question using the context.

    STRICT RULES:
    - Do NOT generate extra questions
    - Do NOT continue conversation
    - Give ONLY final answer
    - Keep answer short and precise

    Context:
    {context}

    Question:
    {query}

    Final Answer:
    """

    llm = get_llm()

    response = llm.invoke(prompt)
    return response.content