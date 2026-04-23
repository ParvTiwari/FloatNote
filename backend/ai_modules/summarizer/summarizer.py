import os
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

from ai_modules.utils.meeting_content import (
    clean_meeting_text,
    is_useful_audio_text,
    is_useful_ocr_text,
)

BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(BACKEND_ENV_PATH)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_SUMMARY_MODEL = os.getenv(
    "GROQ_SUMMARY_MODEL",
    "llama-3.3-70b-versatile",
)
SUMMARY_CONTEXT_CHAR_LIMIT = 9000


def _normalize_action(action):
    if isinstance(action, dict):
        task = str(action.get("task", "")).strip()
        assignee = str(action.get("assignee", "")).strip()
        if task and assignee:
            return f"{assignee}: {task}"
        return task
    return str(action or "").strip()


def _collect_summary_inputs(all_data):
    context_lines = []
    keywords = []
    actions = []

    for item in all_data:
        source = item.get("source", "audio")
        raw_text = item.get("text", "")
        cleaned_text = clean_meeting_text(raw_text, source)

        if source == "ocr":
            if not (cleaned_text and is_useful_ocr_text(raw_text)):
                continue
            prefix = "OCR"
        else:
            if not (cleaned_text and is_useful_audio_text(raw_text)):
                continue
            speaker = str(item.get("speaker", "")).strip()
            prefix = speaker or "Speaker"

        for line in cleaned_text.splitlines():
            normalized = line.strip()
            if normalized:
                context_lines.append(f"{prefix}: {normalized}")

        keywords.extend(item.get("keywords", []) or [])
        for action in item.get("actions", []) or []:
            normalized_action = _normalize_action(action)
            if normalized_action:
                actions.append(normalized_action)

    deduped_lines = list(dict.fromkeys(context_lines))
    deduped_actions = list(dict.fromkeys(actions))
    top_keywords = [
        keyword
        for keyword, _ in Counter(
            str(keyword).strip() for keyword in keywords if str(keyword).strip()
        ).most_common(8)
    ]
    return deduped_lines, top_keywords, deduped_actions


def _build_summary_context(lines):
    selected = []
    current_size = 0

    for line in lines:
        projected = current_size + len(line) + 1
        if projected > SUMMARY_CONTEXT_CHAR_LIMIT:
            break
        selected.append(line)
        current_size = projected

    return "\n".join(selected)


def _fallback_summary(lines, keywords, actions):
    if not lines:
        return "Summary\nNo meeting text was provided.\n\nAction Items\n- No action items found"

    overview = " ".join(line.split(": ", 1)[-1] for line in lines[:3])
    parts = [f"Summary\n{overview}"]

    if keywords:
        parts.append("Key Points\n- " + "\n- ".join(keywords[:6]))

    if actions:
        parts.append("Action Items\n- " + "\n- ".join(actions[:8]))
    else:
        parts.append("Action Items\n- No action items found")

    return "\n\n".join(parts)


def _call_groq(messages, model, temperature=0.2, max_completion_tokens=700):
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
        error_code = str(error_info.get("code", "")).strip()
        error_message = str(error_info.get("message", "")).strip()

        if error_code == "expired_api_key":
            raise ValueError(
                "Groq API key has expired. Update GROQ_API_KEY in backend/.env."
            )
        if response.status_code == 401:
            raise ValueError(
                error_message or "Groq rejected the API key. Check GROQ_API_KEY in backend/.env."
            )

        response.raise_for_status()

    payload = response.json()
    return (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )


def summarize_meeting_result(all_data):
    if not all_data:
        summary = "Summary\nNo meeting data was provided.\n\nAction Items\n- No action items found"
        return {
            "summary": summary,
            "source": "empty",
            "model": None,
            "used_groq": False,
            "used_huggingface": False,
            "error": None,
        }

    lines, keywords, actions = _collect_summary_inputs(all_data)
    if not lines:
        summary = "Summary\nNo meeting text was provided.\n\nAction Items\n- No action items found"
        return {
            "summary": summary,
            "source": "empty",
            "model": None,
            "used_groq": False,
            "used_huggingface": False,
            "error": None,
        }

    model = DEFAULT_GROQ_SUMMARY_MODEL
    context = _build_summary_context(lines)
    action_seed = "\n".join(f"- {action}" for action in actions[:10]) or "- No action items found"
    keyword_seed = ", ".join(keywords[:8]) or "None"

    messages = [
        {
            "role": "system",
            "content": (
                "You are a meeting summarizer. "
                "Summarize only from the provided meeting context. "
                "Do not invent details. "
                "Return plain text in exactly this format:\n"
                "Summary\n"
                "<2 to 4 sentences>\n\n"
                "Key Points\n"
                "- <point>\n"
                "- <point>\n\n"
                "Action Items\n"
                "- <action>\n"
                "If no action item exists, write exactly '- No action items found'."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Meeting context:\n{context}\n\n"
                f"Helpful extracted keywords: {keyword_seed}\n\n"
                f"Helpful extracted action items:\n{action_seed}\n\n"
                "Create a crisp meeting summary."
            ),
        },
    ]

    try:
        summary_text = _call_groq(messages, model=model)
        if not summary_text:
            raise ValueError("Groq returned an empty summary.")
        return {
            "summary": summary_text,
            "source": "groq",
            "model": model,
            "used_groq": True,
            "used_huggingface": False,
            "error": None,
        }
    except Exception as exc:
        print(f"Groq summarizer failed: {exc}")
        fallback_summary = _fallback_summary(lines, keywords, actions)
        return {
            "summary": fallback_summary,
            "source": "fallback",
            "model": model,
            "used_groq": False,
            "used_huggingface": False,
            "error": str(exc),
        }


def summarize_meeting(all_data):
    return summarize_meeting_result(all_data)["summary"]
