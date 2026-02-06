def detect_intent(text: str):
    text = text.lower()

    if text.endswith("?") or text.startswith(("what", "why", "how", "can", "do")):
        return "question"

    if any(x in text for x in ["we should", "let's", "i will", "action item"]):
        return "action_item"

    if any(x in text for x in ["decided", "finalized", "agreed"]):
        return "decision"

    return "statement"