# FloatNote 🎙️

> **Real-time meeting intelligence** — transcription, screen reading, AI summaries, and a chatbot that knows your meeting.

FloatNote is a desktop-first meeting assistant that quietly runs in the background while you work. It captures your microphone, reads your screen during presentations, and turns everything into searchable, queryable meeting memory — powered by local Whisper transcription and HuggingFace LLMs.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎤 **Live Transcription** | Streams audio from your mic through OpenAI Whisper (`base` model) in real-time |
| 🖥️ **Screen OCR** | Captures slide content as it changes, extracting text and keywords automatically |
| 🧠 **AI Summarization** | Generates meeting summaries via BART/Pegasus on HuggingFace Inference API (or local fallback) |
| 💬 **Meeting Chatbot** | Ask questions about any past meeting — answers grounded in a FAISS vector store via RAG |
| 🗃️ **Persistent Storage** | All transcripts, OCR captures, and action items saved to SQLite via async SQLAlchemy |
| ⚡ **Action Item Extraction** | NLP pipeline (spaCy) detects tasks and assignees from spoken text |
| 🖥️ **Electron Desktop App** | Optional Electron wrapper for a native windowed experience |

---

## 🏗️ Architecture

```
FloatNote/
├── backend/
│   ├── main.py                        # FastAPI app + WebSocket server
│   ├── requirements.txt
│   ├── ai_modules/
│   │   ├── stt/
│   │   │   └── whisper_engine.py      # Audio capture + Whisper transcription
│   │   ├── ocr/
│   │   │   ├── ocr_processor.py       # Screen capture + Tesseract OCR
│   │   │   └── keyword_filter.py      # Keyword post-processing
│   │   ├── summarizer/
│   │   │   └── summarizer.py          # HuggingFace summarization (BART/Pegasus)
│   │   ├── chatbot/
│   │   │   └── chatbot.py             # LangChain RAG chatbot (FAISS + Qwen LLM)
│   │   └── utils/
│   │       └── nlp_processor.py       # spaCy NLP pipeline
│   └── database/
│       ├── models.py                  # SQLAlchemy models (Meeting, Transcript, ActionItem)
│       ├── crud.py                    # Async database operations
│       └── view_db.py                 # Database viewer utility
└── frontend/
    ├── react-app/                     # Vite + React 19 + Tailwind CSS UI
    │   └── src/App.jsx                # Main dashboard (WebSocket client)
    └── electron/
        └── main.js                    # Electron wrapper (loads localhost:5173)
```

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (for screen reading)

### 1. Clone the repo

```bash
git clone https://github.com/Parth-Gupta-github/FloatNote.git
cd FloatNote
```

### 2. Install Python dependencies

```bash
pip install -r backend/requirements.txt
```

> ⚠️ First run downloads the Whisper `base` model (~150MB) and the spaCy `en_core_web_sm` model automatically.

### 3. Install Tesseract OCR
**Windows:**

Download the installer from the [Tesseract at UB Mannheim wiki](https://github.com/UB-Mannheim/tesseract/wiki), then install via winget:
```bash
winget install UB-Mannheim.TesseractOCR
```

Then verify the path in `backend/ai_modules/ocr/ocr_processor.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 4. Configure environment variables

Create a `.env` file inside `backend/`:

```env
# Required for AI summarization and chatbot
HUGGINGFACEHUB_API_TOKEN=hf_...

# Required for keyword filtering (Groq LLM)
GROQ_API_KEY=gsk_...
```

> 💡 A HuggingFace API token is **required** for summarization and the chatbot. Get one free at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

> 💡 A Groq API key is **required** for LLM-powered keyword filtering. Without it, keywords fall back to simple deduplication.

### 5. Start the backend

```bash
python backend/main.py
```

The server starts at `http://localhost:8000` and immediately begins listening to your microphone.

### 6. Start the frontend

```bash
cd frontend/react-app
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 7. (Optional) Run as Electron desktop app

```bash
cd frontend/electron
npm install
npm start
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `WS` | `/ws` | Real-time audio + OCR stream (connects and starts a meeting) |
| `GET` | `/meetings/latest/summary` | Summarize the most recent meeting |
| `GET` | `/meetings/{id}/summary` | Summarize a specific meeting by ID |
| `POST` | `/meetings/latest/chat` | Ask a question about the latest meeting |
| `POST` | `/meetings/{id}/chat` | Ask a question about a specific meeting |

### Chat request body

```json
{
  "question": "What action items were assigned to me?"
}
```

### WebSocket message format (incoming)

```json
{
  "type": "connected",
  "meeting_id": 42
}
```

```json
{
  "text": "Let's align on the Q3 roadmap.",
  "keywords": ["roadmap", "Q3"],
  "actions": [{ "task": "Share roadmap draft", "assignee": "MIC" }],
  "ocr": { "text": "Slide: Roadmap Overview", "keywords": ["roadmap"] },
  "meeting_id": 42
}
```

---

## 🤖 AI Models

| Component | Default Model | Configurable |
|---|---|---|
| Transcription | `openai/whisper-base` (local) | Change model size in `whisper_engine.py` |
| Summarization | `facebook/bart-large-cnn` (HF API) | `HF_SUMMARIZER_REPO_ID` env var |
| Chatbot LLM | `Qwen/Qwen2.5-7B-Instruct` (HF API) | `HUGGINGFACE_CHAT_MODEL` env var |
| Keyword Filtering | `llama-3.3-70b-versatile` (Groq API) | Hardcoded in `keyword_filter.py` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) | Hardcoded in `chatbot.py` |
| NLP / Action Items | `en_core_web_sm` (spaCy, local) | — |

**Supported summarizer models:**
- `facebook/bart-large-cnn`
- `google/pegasus-xsum`
- `sshleifer/distilbart-cnn-12-6`

---

## 🗄️ Database Schema

FloatNote uses **SQLite** (`backend/database/meeting_assistant.db`) with async SQLAlchemy.

```
meetings
  id, title, start_time, summary

transcripts
  id, meeting_id → meetings.id, timestamp, text, keywords, source (MIC / OCR / SPEAKER_xx)

action_items
  id, meeting_id → meetings.id, description, assignee, status
```

To inspect the database directly:
```bash
python backend/database/view_db.py
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `HUGGINGFACEHUB_API_TOKEN` | — | **Required.** HF API token |
| `GROQ_API_KEY` | — | **Required.** Groq API token for keyword filtering |
| `HUGGINGFACE_CHAT_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | Chat LLM repo ID |
| `HF_SUMMARIZER_REPO_ID` | `facebook/bart-large-cnn` | Summarizer model repo ID |
| `ENABLE_OCR` | `true` | Enable/disable screen capture |
| `OCR_INTERVAL_SECONDS` | `3.0` | How often to poll for screen changes |
| `OCR_CHANGE_THRESHOLD` | `0.02` | Minimum pixel-change ratio to trigger OCR |
| `HOST` | `0.0.0.0` | Backend bind host |
| `PORT` | `8000` | Backend bind port |

---

## 🛠️ Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) — async web server + WebSockets
- [OpenAI Whisper](https://github.com/openai/whisper) — local speech-to-text
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) + [pytesseract](https://github.com/madmaze/pytesseract) — screen reading
- [Groq API](https://console.groq.com/) (`llama-3.3-70b-versatile`) — LLM-powered keyword filtering
- [LangChain](https://www.langchain.com/) + [FAISS](https://faiss.ai/) — RAG chatbot
- [HuggingFace Inference API](https://huggingface.co/inference-api) — summarization + chat LLM
- [spaCy](https://spacy.io/) — action item extraction + NLP
- [SQLAlchemy (async)](https://docs.sqlalchemy.org/) + [SQLite](https://sqlite.org/) — database

**Frontend**
- [React 19](https://react.dev/) + [Vite](https://vitejs.dev/) — UI framework
- [Tailwind CSS](https://tailwindcss.com/) — styling
- [Electron](https://www.electronjs.org/) — optional desktop wrapper

---

## 🐛 Known Issues & Limitations

- **Windows-only OCR path** — the Tesseract path in `ocr_processor.py` defaults to a Windows path. Linux/macOS users must update it or ensure `tesseract` is on `PATH`.
- **Single monitor** — OCR captures monitor index `1` by default. Adjust `monitor_index` in `OCRProcessor` for multi-monitor setups.
- **Max 3 WebSocket clients** — concurrent client connections are capped to prevent resource exhaustion.
- **HF API latency** — summarization and chat responses depend on HuggingFace Inference API availability and may be slow on free tier.