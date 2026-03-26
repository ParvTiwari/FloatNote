import spacy
from spacy.matcher import Matcher

nlp = spacy.load("en_core_web_sm")
matcher = Matcher(nlp.vocab)

ACTION_VERBS = {
    "send", "email", "message", "call", "meet", "discuss", "share", "reply",
    "fix", "debug", "code", "write", "test", "deploy", "build", "refactor",
    "implement", "merge", "review", "schedule", "plan", "create", "update",
    "prepare", "finalize", "check", "verify", "complete"
}

patterns = [
    [{"LOWER": "i"}, {"LOWER": "will"}],
    [{"LOWER": "we"}, {"LOWER": "will"}],
    [{"LOWER": "need"}, {"LOWER": "to"}],
    [{"LOWER": "should"}],
    [{"LOWER": "please"}],
]
matcher.add("ACTION_ITEM", patterns)

def process_text(raw_text, speaker="Unknown"):
    doc = nlp(raw_text)

    actions = []

    for sent in doc.sents:
        for token in sent:
            if token.lemma_.lower() in ACTION_VERBS and token.pos_ == "VERB":

                subject = [w.text for w in token.lefts if w.dep_ in ("nsubj", "nsubjpass")]
                obj = [w.text for w in token.rights if w.dep_ in ("dobj", "pobj")]

                assignee = " ".join(subject) if subject else speaker

                if obj:
                    actions.append({
                        "task": f"{token.text} {' '.join(obj)}",
                        "assignee": assignee
                    })

        matches = matcher(sent)
        if matches and not actions:
            actions.append({
                "task": sent.text.strip(),
                "assignee": speaker
            })

    return {
        "text": raw_text,
        "actions": actions
    }