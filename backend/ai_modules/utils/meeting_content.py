import re


UI_CHROME_TERMS = {
    "file",
    "home",
    "insert",
    "draw",
    "design",
    "layout",
    "references",
    "mailings",
    "review",
    "view",
    "help",
    "acrobat",
    "comments",
    "editing",
    "find",
    "paste",
    "font",
    "paragraph",
    "styles",
    "share",
}
SENTENCE_TERMS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "and",
    "from",
}
TRAILING_STOP_TOKENS = {
    "and",
    "or",
    "to",
    "for",
    "with",
    "from",
    "the",
    "a",
    "an",
    "of",
    "in",
    "on",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _sentence_chunks(text: str) -> list[str]:
    chunks = re.split(r"[\n\r]+|(?<=[.!?])\s+", text or "")
    return [normalize_text(chunk) for chunk in chunks if normalize_text(chunk)]


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text or "")


def _tokenize_lower(text: str) -> list[str]:
    return [token.lower() for token in _word_tokens(text)]


def _has_vowel(token: str) -> bool:
    return any(char in "aeiou" for char in token.lower())


def _has_too_many_symbols(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    if not compact:
        return True
    symbol_count = sum(1 for char in compact if not char.isalnum())
    return symbol_count / len(compact) > 0.28


def _looks_like_ui_chrome(line: str) -> bool:
    tokens = [token.lower() for token in _word_tokens(line)]
    if len(tokens) < 3:
        return False
    chrome_hits = sum(1 for token in tokens if token in UI_CHROME_TERMS)
    return chrome_hits >= max(3, int(len(tokens) * 0.6))


def _is_meaningful_line(line: str) -> bool:
    cleaned = normalize_text(line)
    if len(cleaned) < 8:
        return False
    if _has_too_many_symbols(cleaned):
        return False

    tokens = _word_tokens(cleaned)
    if not tokens:
        return False

    short_tokens = sum(1 for token in tokens if len(token) == 1)
    if short_tokens / len(tokens) > 0.35:
        return False

    if _looks_like_ui_chrome(cleaned):
        return False

    vowel_tokens = sum(1 for token in tokens if _has_vowel(token))
    if vowel_tokens / len(tokens) < 0.65:
        return False

    long_tokens = sum(1 for token in tokens if len(token) >= 4)
    if long_tokens == 0 and len(tokens) < 8:
        return False

    if tokens[-1].lower() in TRAILING_STOP_TOKENS:
        return False

    sentence_hits = sum(1 for token in tokens if token.lower() in SENTENCE_TERMS)
    if sentence_hits >= 2:
        return True

    # Keep compact slide lines only when they look structured, not like OCR debris.
    if len(tokens) >= 5 and "," in cleaned and short_tokens == 0 and sentence_hits >= 1:
        return True

    return False


def _has_excessive_repetition(text: str) -> bool:
    tokens = _tokenize_lower(text)
    if len(tokens) < 8:
        return False

    unique_ratio = len(set(tokens)) / len(tokens)
    if unique_ratio < 0.35:
        return True

    token_counts = {}
    for token in tokens:
        token_counts[token] = token_counts.get(token, 0) + 1
    if max(token_counts.values()) / len(tokens) > 0.22:
        return True

    repeated_bigrams = 0
    bigrams = list(zip(tokens, tokens[1:]))
    for i in range(1, len(bigrams)):
        if bigrams[i] == bigrams[i - 1]:
            repeated_bigrams += 1
    if repeated_bigrams >= 2:
        return True

    trigram_counts = {}
    trigrams = list(zip(tokens, tokens[1:], tokens[2:]))
    for trigram in trigrams:
        trigram_counts[trigram] = trigram_counts.get(trigram, 0) + 1
    if trigram_counts and max(trigram_counts.values()) >= 3:
        return True

    phrase_patterns = [
        r"\b(\w+\s+\w+\s+\w+)(?:\s+\1){1,}\b",
        r"\b(\w+\s+\w+)(?:\s+\1){2,}\b",
        r"\b(a\s+little\s+bit\s+of)\b(?:\s+\w+){0,2}\s+\1",
    ]
    lowered = " ".join(tokens)
    return any(re.search(pattern, lowered) for pattern in phrase_patterns)


def is_useful_audio_text(text: str) -> bool:
    normalized = normalize_text(text)
    if len(normalized) < 8:
        return False

    tokens = _tokenize_lower(normalized)
    if len(tokens) < 3:
        return False

    if _has_excessive_repetition(normalized):
        return False

    alpha_chars = sum(1 for char in normalized if char.isalpha())
    return alpha_chars >= 8


def clean_audio_text(text: str) -> str:
    normalized = normalize_text(text)
    if not is_useful_audio_text(normalized):
        return ""
    return normalized


def clean_ocr_text(text: str) -> str:
    lines = []
    for chunk in _sentence_chunks(text or ""):
        if _is_meaningful_line(chunk):
            lines.append(chunk)

    unique_lines = list(dict.fromkeys(lines))
    return "\n".join(unique_lines[:8])


def is_useful_ocr_text(text: str) -> bool:
    cleaned = clean_ocr_text(text)
    if not cleaned:
        return False

    tokens = _word_tokens(cleaned)
    if len(tokens) < 4:
        return False

    alpha_chars = sum(1 for char in cleaned if char.isalpha())
    return alpha_chars >= 12


def clean_meeting_text(text: str, source: str) -> str:
    raw_text = (text or "").strip()
    if not raw_text:
        return ""
    if (source or "").lower() == "ocr":
        return clean_ocr_text(raw_text)
    return clean_audio_text(raw_text)
