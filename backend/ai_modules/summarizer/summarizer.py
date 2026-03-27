# backend/ai_modules/summarizer/summarizer.py
# some changes made
import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

DEFAULT_SUMMARIZER_REPO_ID = "facebook/bart-large-cnn"
SUPPORTED_SUMMARIZER_MODELS = {
    "facebook/bart-large-cnn",
    "google/pegasus-xsum",
    "sshleifer/distilbart-cnn-12-6",
}


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
    repo_id = os.getenv("HF_SUMMARIZER_REPO_ID", DEFAULT_SUMMARIZER_REPO_ID)
    meeting_text = build_text(all_data)

    if token:
        try:
            if repo_id not in SUPPORTED_SUMMARIZER_MODELS:
                raise ValueError(
                    f"Unsupported HF_SUMMARIZER_REPO_ID '{repo_id}'. "
                    f"Choose one of: {', '.join(sorted(SUPPORTED_SUMMARIZER_MODELS))}"
                )

            client = InferenceClient(model=repo_id, token=token, timeout=60)
            result = client.summarization(meeting_text)
            summary_text = getattr(result, "summary_text", "").strip()

            if summary_text:
                return f"Summary\n{summary_text}"

            raise ValueError(f"Unexpected Hugging Face response: {result}")
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
