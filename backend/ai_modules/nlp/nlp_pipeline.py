import asyncio
import websockets
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

patterns = [
    [{"LOWER": "i"}, {"LOWER": "will"}],
    [{"LOWER": "have"}, {"LOWER": "to"}],
    [{"LOWER": "need"}, {"LOWER": "to"}],
    [{"LOWER": "remember"}, {"LOWER": "to"}],
    [{"LOWER": "please"}],
    [{"LOWER": {"IN": ["todo", "task"]}}],
    [{"LOWER": "gotta"}],
    [{"LOWER": "let"}, {"LOWER": "me"}],
    [{"LOWER": "we"}, {"LOWER": "should"}],
    [{"LOWER": {"IN": ["tomorrow", "today"]}}]
]
matcher.add("ACTION_ITEM", patterns)

def process_text(raw_text):
    doc = nlp(raw_text)
    
    entities = [ent.text for ent in doc.ents if ent.label_ in {"PERSON", "ORG", "GPE", "PRODUCT"}]
    
    actions = []
    
    for token in doc:
        if token.lemma_.lower() in ACTION_VERBS and token.pos_ == "VERB":
            subject = [w.text for w in token.lefts if w.dep_ in ("nsubj", "nsubjpass")]
            obj = [w.text for w in token.rights if w.dep_ in ("dobj", "pobj")]
            if obj:
                actions.append(f"{' '.join(subject) if subject else 'Someone'} → {token.text} {' '.join(obj)}")

    matches = matcher(doc)
    if matches and not actions:
        for sent in doc.sents:
            actions.append(f"📌 Task identified: {sent.text.strip()}")

    return {
        "text": raw_text,
        "keywords": list(set(entities)),
        "actions": list(set(actions))
    }

async def main():
    uri = "ws://localhost:8000/ws"
    print("🛰️ Connecting to STT Server...")
    while True:
        try:
            async with websockets.connect(uri) as ws:
                print("✅ Connected. Listening for speech...")
                while True:
                    transcript = await ws.recv()
                    analysis = process_text(transcript)

                    print("\n" + "="*50)
                    print(f"🎤 TRANSCRIPT: {analysis['text']}")
                    if analysis['keywords']:
                        print(f"🔑 KEYWORDS:   {', '.join(analysis['keywords'])}")
                    if analysis['actions']:
                        for act in analysis['actions']:
                            print(f"✅ ACTION:     {act}")
                    else:
                        print("ℹ️  No actions detected")

                    print("="*50)

        except Exception as e:
            print(f"🔄 Reconnecting in 2s... {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())