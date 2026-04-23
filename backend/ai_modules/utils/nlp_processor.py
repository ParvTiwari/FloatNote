import spacy
from spacy.matcher import Matcher

nlp = spacy.load("en_core_web_sm")
matcher = Matcher(nlp.vocab)

ACTION_VERBS = {
    "send", "email", "message", "call", "meet", "discuss", "share", "reply",
    "fix", "debug", "code", "write", "test", "deploy", "build", "refactor",
    "extract", "implement", "merge", "commit", "push", "review", "pr",
    "schedule", "plan", "create", "add", "remove", "update", "delete",
    "prepare", "finalize", "draft", "edit", "approve", "sign",
    "follow", "check", "verify", "confirm", "complete", "finish"
}

# More specific patterns for action items
patterns = [
    [{"LOWER": {"IN": ["todo", "task", "action"]}}],
    [{"LOWER": "follow"}, {"LOWER": "up"}],
    [{"LOWER": "next"}, {"LOWER": "step"}],
    [{"LOWER": "assign"}, {"LOWER": "to"}],
]
matcher.add("ACTION_ITEM", patterns)

def process_text(raw_text):
    doc = nlp(raw_text)
    
    entities = [ent.text for ent in doc.ents if ent.label_ in {"PERSON", "ORG", "GPE", "PRODUCT"}]
    
    actions = []
    
    # Extract actions based on action verbs with clear subjects and objects
    for token in doc:
        if token.lemma_.lower() in ACTION_VERBS and token.pos_ == "VERB":
            subject = [w.text for w in token.lefts if w.dep_ in ("nsubj", "nsubjpass")]
            obj = [w.text for w in token.rights if w.dep_ in ("dobj", "pobj", "attr")]
            # Only add if we have both subject and object, or if it's a clear imperative
            if obj or (subject and any(w.dep_ == "aux" for w in token.lefts)):
                action_text = f"{' '.join(subject) if subject else 'Someone'} → {token.text} {' '.join(obj) if obj else ''}".strip()
                if len(action_text.split()) > 2:  # Must have more than just "Someone → verb"
                    actions.append(action_text)

    # Check for explicit action item patterns
    matches = matcher(doc)
    for match_id, start, end in matches:
        span = doc[start:end]
        # Get the sentence containing the match
        sent = span.sent
        # Only add if the sentence is reasonably short and contains action-like language
        sent_text = sent.text.strip()
        if len(sent_text.split()) < 20 and any(word in sent_text.lower() for word in ["todo", "task", "action", "follow up", "next step"]):
            actions.append(f"📌 {sent_text}")

    return {
        "text": raw_text,
        "keywords": list(set(entities)),
        "actions": list(set(actions))
    }