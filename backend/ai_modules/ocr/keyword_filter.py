import re
from typing import List


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "have",
    "will",
    "about",
    "there",
    "their",
    "while",
    "where",
    "which",
    "when",
    "were",
    "been",
    "being",
    "also",
    "just",
    "more",
    "some",
    "such",
    "than",
    "then",
    "them",
    "they",
    "over",
    "under",
    "very",
    "much",
    "into",
    "onto",
}


def _normalize_keyword(keyword: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(keyword or "")).strip(" -_,.;:()[]{}")
    return cleaned


def _is_useful_keyword(keyword: str) -> bool:
    lowered = keyword.lower()
    if not lowered:
        return False
    if lowered in STOPWORDS:
        return False
    if len(lowered) <= 2 and not keyword.isupper():
        return False
    if not re.search(r"[a-zA-Z]", keyword):
        return False
    if len(set(re.findall(r"[a-zA-Z]", lowered))) == 1 and len(lowered) > 3:
        return False
    return True


def filter_keywords(keywords: List[str]) -> List[str]:
    if not keywords:
        return []

    filtered = []
    seen = set()

    for keyword in keywords:
        cleaned = _normalize_keyword(keyword)
        key = cleaned.lower()
        if not _is_useful_keyword(cleaned):
            continue
        if key in seen:
            continue
        seen.add(key)
        filtered.append(cleaned)

    return filtered
