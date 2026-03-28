import os
import warnings

warnings.filterwarnings(
    "ignore",
    message="TypedStorage is deprecated"
)

from ai_modules.stt.whisper_engine import run_server
from ai_modules.summarizer.summarizer import summarize_meeting
from ai_modules.chatbot.chatbot import (
    convert_to_documents,
    create_vector_store,
    ask_question,
)


def build_demo_data():
    return [
        {
            "source": "audio",
            "speaker": "Speaker_Unknown",
            "text": "Good morning everyone, today we will discuss the progress of the project and the upcoming deadline.",
            "keywords": ["project", "deadline"],
            "actions": ["Discuss progress"],
        },
        {
            "source": "diarization",
            "speaker": "SPEAKER_00",
            "text": "The frontend module is almost complete, we just need to fix some UI bugs and improve responsiveness.",
            "keywords": [],
            "actions": ["Fix UI bugs", "Improve responsiveness"],
        },
        {
            "source": "diarization",
            "speaker": "SPEAKER_01",
            "text": "Backend APIs are working fine but we need to optimize database queries for better performance.",
            "keywords": ["backend", "database"],
            "actions": ["Optimize queries"],
        },
        {
            "source": "audio",
            "speaker": "Speaker_Unknown",
            "text": "We also need to integrate the OCR module and test it with real-time data.",
            "keywords": ["OCR", "integration"],
            "actions": ["Integrate OCR"],
        },
        {
            "source": "ocr",
            "speaker": None,
            "text": "Final deadline is 30th March. Testing phase starts from 25th March.",
            "keywords": ["deadline", "testing"],
            "actions": [],
        },
        {
            "source": "diarization",
            "speaker": "SPEAKER_00",
            "text": "We should assign tasks clearly so that each team member knows their responsibilities.",
            "keywords": [],
            "actions": ["Assign tasks"],
        },
        {
            "source": "audio",
            "speaker": "Speaker_Unknown",
            "text": "Let's make sure all modules are integrated before the final review meeting.",
            "keywords": ["integration", "review"],
            "actions": ["Complete integration"],
        },
        {
            "source": "diarization",
            "speaker": "SPEAKER_01",
            "text": "Testing should include both unit testing and integration testing to avoid last-minute issues.",
            "keywords": ["testing"],
            "actions": ["Perform unit testing", "Perform integration testing"],
        },
        {
            "source": "ocr",
            "speaker": None,
            "text": "Review meeting scheduled on 29th March at 10 AM.",
            "keywords": ["meeting", "schedule"],
            "actions": [],
        },
    ]


if __name__ == "__main__":

    if os.getenv("RUN_CHATBOT_DEMO", "").strip().lower() in {"1", "true", "yes"}:
        print("🚀 Chatbot Mode\n")

        data = build_demo_data()
        docs = convert_to_documents(data)
        vector_db = create_vector_store(docs)

        print("✅ Chatbot Ready! Type 'exit' to quit.\n")

        while True:
            query = input("Ask: ")

            if query.lower() in {"exit", "quit"}:
                print("👋 Exiting chatbot...")
                break

            answer = ask_question(query, vector_db)
            print("\n🤖 Answer:\n", answer, "\n")

    elif os.getenv("RUN_SUMMARY_DEMO", "").strip().lower() in {"1", "true", "yes"}:
        print("📝 Summary Mode\n")
        print(summarize_meeting(build_demo_data()))

    else:
        print("🌐 Running Server...\n")
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        run_server(host=host, port=port)
