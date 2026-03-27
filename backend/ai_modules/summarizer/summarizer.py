# backend/ai_modules/summarizer/summarizer.py

import os
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEndpoint

load_dotenv()


def build_text(data):
    final_text = ""

    for item in data:
        if item["speaker"]:
            final_text += f"{item['speaker']}: {item['text']}\n"
        else:
            final_text += f"{item['source']}: {item['text']}\n"

        if item["keywords"]:
            final_text += f"Keywords: {', '.join(item['keywords'])}\n"

        if item["actions"]:
            final_text += f"Actions: {', '.join(item['actions'])}\n"

        final_text += "\n"

    return final_text


def summarize_meeting(all_data):
    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    prompt = (
        "Summarize the following meeting into:\n"
        "1. Summary\n"
        "2. Key Points\n"
        "3. Action Items\n\n"
        + build_text(all_data)
    )

    if token:
        try:
            llm = HuggingFaceEndpoint(
                repo_id="google/flan-t5-large",
                temperature=0,
                max_new_tokens=512,
            )

            result = llm.invoke(prompt)
            if isinstance(result, str):
                return result
            return str(result)
        except Exception as exc:
            print(f"Hugging Face summarizer failed: {exc}")
    else:
        print("Hugging Face summarizer skipped: HUGGINGFACEHUB_API_TOKEN is not set.")

    texts = [item["text"] for item in all_data if item.get("text")]
    keywords = []
    actions = []
    for item in all_data:
        keywords.extend(item.get("keywords", []))
        actions.extend(item.get("actions", []))

    unique_keywords = list(dict.fromkeys(keywords))
    unique_actions = list(dict.fromkeys(actions))
    summary_line = " ".join(texts[:2]).strip() or "No meeting text was provided."

    key_points = unique_keywords if unique_keywords else ["No explicit keywords found"]
    action_items = unique_actions if unique_actions else ["No action items found"]

    return (
        f"Summary\n{summary_line}\n\n"
        f"Key Points\n- " + "\n- ".join(key_points) + "\n\n"
        f"Action Items\n- " + "\n- ".join(action_items)
    )
