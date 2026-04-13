# backend/ai_modules/summarizer/summarizer.py
# some changes made
import os
import re
from collections import Counter
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from ai_modules.utils.meeting_content import (
    clean_meeting_text,
    is_useful_audio_text,
    is_useful_ocr_text,
)

load_dotenv()

DEFAULT_SUMMARIZER_REPO_ID = "facebook/bart-large-cnn"
SUPPORTED_SUMMARIZER_MODELS = {
    "facebook/bart-large-cnn",
    "google/pegasus-xsum",
    "sshleifer/distilbart-cnn-12-6",
}

def build_text(data):
    lines = []

    for item in data:
        if item.get("source") == "action_item":
            continue
        source = item.get("source", "audio")
        text = clean_meeting_text(item.get("text", ""), source)
        if source == "ocr" and not is_useful_ocr_text(item.get("text", "")):
            continue
        if source != "ocr" and not is_useful_audio_text(item.get("text", "")):
            continue
        if text:
            lines.append(text)

    unique_lines = list(dict.fromkeys(lines))

    return "\n".join(unique_lines[:20])


def _split_sentences(text):
    chunks = re.split(r"(?<=[.!?])\s+", text.strip())
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _fallback_summary(all_data):
    texts = [
        clean_meeting_text(item["text"], item.get("source", "audio"))
        for item in all_data
        if item.get("text", "").strip()
        and item.get("source") != "action_item"
        and (
            (item.get("source") == "ocr" and is_useful_ocr_text(item.get("text", "")))
            or (item.get("source") != "ocr" and is_useful_audio_text(item.get("text", "")))
        )
    ]
    keywords = []
    actions = []

    for item in all_data:
        keywords.extend(item.get("keywords", []))
        actions.extend(item.get("actions", []))

    top_keywords = [
        keyword for keyword, _ in Counter(
            kw.strip() for kw in keywords if str(kw).strip()
        ).most_common(6)
    ]
    unique_actions = list(
        dict.fromkeys(action.strip() for action in actions if str(action).strip())
    )

    sentences = []
    for text in texts:
        for sentence in _split_sentences(text):
            if sentence not in sentences:
                sentences.append(sentence)
            if len(sentences) == 3:
                break
        if len(sentences) == 3:
            break

    if not sentences:
        sentences = ["No meeting text was provided."]

    overview = " ".join(sentences)
    if top_keywords:
        overview += f" Main discussion topics included {', '.join(top_keywords[:4])}."

    parts = [f"Summary\n{overview}"]

    if top_keywords:
        parts.append("Key Points\n- " + "\n- ".join(top_keywords))

    if unique_actions:
        parts.append("Action Items\n- " + "\n- ".join(unique_actions[:8]))
    else:
        parts.append("Action Items\n- No action items found")

    return "\n\n".join(parts)

def summarize_meeting(all_data):
    if not all_data:
        return "Summary\nNo meeting data was provided.\n\nAction Items\n- No action items found"

    token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    repo_id = os.getenv("HF_SUMMARIZER_REPO_ID", DEFAULT_SUMMARIZER_REPO_ID)
    meeting_text = build_text(all_data)

    if not meeting_text.strip():
        return "Summary\nNo meeting text was provided.\n\nAction Items\n- No action items found"

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
                actions = []
                for item in all_data:
                    actions.extend(item.get("actions", []))
                unique_actions = list(
                    dict.fromkeys(action.strip() for action in actions if str(action).strip())
                )
                if unique_actions:
                    return f"Summary\n{summary_text}\n\nAction Items\n- " + "\n- ".join(unique_actions[:8])
                return f"Summary\n{summary_text}"

            raise ValueError(f"Unexpected Hugging Face response: {result}")
        except Exception as exc:
            print(f"Hugging Face summarizer failed: {exc}")
    else:
        print("Hugging Face summarizer skipped: HUGGINGFACEHUB_API_TOKEN is not set.")

    return _fallback_summary(all_data)
