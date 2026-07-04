# FloatNote 🎙️

> **Real-time meeting intelligence** — transcription, screen reading, AI summaries, and a chatbot that knows your meeting.

FloatNote is a desktop-first meeting assistant that quietly runs in the background while you work. It captures your microphone, reads your screen during presentations, and turns everything into searchable, queryable meeting memory — powered by local Whisper transcription and HuggingFace LLMs.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎤 **Live Transcription** | Streams audio from your mic through OpenAI Whisper (`base` model) in real-time |
| 🖥️ **Screen OCR** | Captures slide content as it changes, extracting text and keywords automatically |
| 🗣️ **Speaker Diarization** | Labels each utterance by speaker in real time using offline Resemblyzer voice embeddings (`SPEAKER_00`, `SPEAKER_01`, …) |
| 🧠 **AI Summarization** | Generates meeting summaries via Groq's Llama 3.3 70B |
| 💬 **Meeting Chatbot** | Ask questions about any past meeting — answers grounded in a local vector store via RAG (FAISS-backed when enabled) |
| 🗃️ **Persistent Storage** | All transcripts, OCR captures, and action items saved to SQLite via async SQLAlchemy |
| ⚡ **Action Item Extraction** | NLP pipeline (spaCy) detects tasks and assignees from spoken text |
| 🖥️ **Electron Desktop App** | Optional Electron wrapper for a native windowed experience |

---

## 🏗️ Architecture

```
FloatNote/
├── backend/
│   ├── main.py                        # Entrypoint — loads env, starts the server
│   ├── requirements.txt
│   ├── ai_modules/
│   │   ├── stt/
│   │   │   └── whisper_engine.py      # FastAPI app, all routes, WebSocket + Whisper transcription
│   │   ├── ocr/
│   │   │   ├── ocr_processor.py       # Screen capture + Tesseract OCR
│   │   │   └── keyword_filter.py      # Keyword post-processing
│   │   ├── summarizer/
│   │   │   └── summarizer.py          # Groq LLM summarization (Llama 3.3 70B)
│   │   ├── chatbot/
│   │   │   └── chatbot.py             # LangChain RAG chatbot (local vector store + Groq LLM)
│   │   ├── diarization/
│   │   │   └── diarizer.py            # Offline speaker diarization (Resemblyzer)
│   │   └── utils/
│   │       └── nlp_processor.py       # spaCy NLP pipeline
│   └── database/
│       ├── models.py                  # SQLAlchemy models (Meeting, Transcript, ActionItem)
│       ├── crud.py                    # Async database operations
│       └── view_db.py                 # Database viewer utility
├── frontend/
│   ├── react-app/                     # Vite + React 19 + Tailwind CSS UI
│   │   └── src/App.jsx                # Main dashboard (WebSocket client)
│   └── electron/
│       └── main.js                    # Electron wrapper (loads localhost:5173)
└── marketing-site/                    # Next.js promo/landing site (SEO-optimized)
    ├── app/                           # App Router pages, metadata, sitemap, robots
    └── components/                    # Landing sections + light/dark theme toggle
```

---

## 🚀 Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (for screen reading)

### 1. Clone the repo

```bash
git clone https://github.com/ParvTiwari/FloatNote.git
cd FloatNote
```

### 2. Install Python dependencies

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
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
# Required — powers summarization, the chatbot, and keyword filtering (Groq LLM)
GROQ_API_KEY=gsk_...

# Optional — enables Gemini as an alternate keyword-filtering backend
GEMINI_API_KEY=...
```

> 💡 A Groq API key is **required** — summarization and the chatbot raise an error without it, and keyword filtering falls back to simple deduplication.

> 💡 No HuggingFace token is needed: the RAG embedding model (`all-MiniLM-L6-v2`) and diarization weights (Resemblyzer) run locally and download automatically on first use.

### 5. Start the backend

```bash
.\.venv\Scripts\Activate.ps1
python backend/main.py
```

The server starts at `http://localhost:8000`. It doesn't record on launch — start a meeting explicitly from the UI (or `POST /meetings/start`) to begin capturing your microphone.

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

The FastAPI app and all routes are defined in [`whisper_engine.py`](backend/ai_modules/stt/whisper_engine.py). Connecting to the WebSocket **no longer** starts a meeting — recording is controlled explicitly via the `/meetings/*` endpoints.

**Real-time stream**

| Method | Endpoint | Description |
|---|---|---|
| `WS` | `/ws` | Live transcript / OCR / status broadcast channel (max **3** concurrent clients) |

**Meeting control**

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/meetings/start` | `{ "title"?, "capture_speaker"? }` | Start recording — creates a meeting and opens the mic (and speaker) streams |
| `POST` | `/meetings/pause` | — | Pause capture on the active meeting |
| `POST` | `/meetings/resume` | — | Resume a paused meeting |
| `POST` | `/meetings/stop` | — | Stop recording and release audio devices |
| `POST` | `/meetings/mute` | `{ "source": "mic"\|"speaker", "muted": bool }` | Mute a source by releasing its OS audio device |
| `POST` | `/meetings/title` | `{ "title" }` | Set/edit the active meeting title (allowed mid-recording) |

**Speakers**

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `GET` | `/meetings/{id}/speakers` | — | List speaker aliases for a meeting |
| `POST` | `/meetings/{id}/speakers` | `{ "speaker_key", "display_name" }` | Rename a diarized speaker (e.g. `SPEAKER_00` → "Alice") |

**Summaries & chat**

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `GET` | `/meetings/latest/summary` | — | Summarize the most recent meeting |
| `GET` | `/meetings/{id}/summary` | — | Summarize a specific meeting by ID |
| `POST` | `/meetings/latest/chat` | `{ "question" }` | Ask a question about the latest meeting |
| `POST` | `/meetings/{id}/chat` | `{ "question" }` | Ask a question about a specific meeting |

**Debug / export** (dumps captured items, retrieved docs, and model I/O to a JSON file)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/meetings/latest/debug/export` | Export a snapshot of the latest meeting |
| `GET` | `/meetings/{id}/debug/export` | Export a snapshot of a specific meeting |
| `POST` | `/meetings/latest/chat/debug` | Chat + export the full retrieval/answer trace (latest) |
| `POST` | `/meetings/{id}/chat/debug` | Chat + export the full retrieval/answer trace (by ID) |

### Chat request body

```json
{
  "question": "What action items were assigned to me?"
}
```

### WebSocket messages (server → client)

On connect, and after every control change, the server pushes a **status** snapshot:

```json
{
  "type": "status",
  "recording": true,
  "paused": false,
  "meeting_id": 42,
  "title": "Q3 Planning",
  "mic_muted": false,
  "speaker_muted": false,
  "speaker_enabled": true
}
```

During a meeting, transcript/OCR analysis is broadcast as it's produced:

```json
{
  "text": "Let's align on the Q3 roadmap.",
  "keywords": ["roadmap", "Q3"],
  "actions": [{ "task": "Share roadmap draft", "assignee": "MIC" }],
  "ocr": { "text": "Slide: Roadmap Overview", "keywords": ["roadmap"] },
  "meeting_id": 42
}
```

Renaming a speaker broadcasts a `speaker_renamed` event:

```json
{
  "type": "speaker_renamed",
  "meeting_id": 42,
  "speaker_key": "SPEAKER_00",
  "display_name": "Alice"
}
```

---

## 🤖 AI Models

| Component | Default Model | Configurable |
|---|---|---|
| Transcription | `openai/whisper-base` (local) | Change model size in `whisper_engine.py` |
| Summarization | `llama-3.3-70b-versatile` (Groq API) | `GROQ_SUMMARY_MODEL` env var |
| Chatbot LLM | `llama-3.3-70b-versatile` (Groq API) | `GROQ_CHAT_MODEL` env var |
| Keyword Filtering | `llama-3.3-70b-versatile` (Groq API) | Hardcoded in `keyword_filter.py` |
| Diarization | Resemblyzer d-vector (local) | `DIARIZATION_SIMILARITY`, `DIARIZATION_MIN_SAMPLES` env vars |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) | Hardcoded in `chatbot.py` |
| NLP / Action Items | `en_core_web_sm` (spaCy, local) | — |

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
| `GROQ_API_KEY` | — | **Required.** Groq API token for summarization, chatbot, and keyword filtering |
| `GEMINI_API_KEY` | — | Optional. Alternate keyword-filtering backend |
| `GROQ_CHAT_MODEL` | `llama-3.3-70b-versatile` | Chatbot LLM model ID |
| `GROQ_SUMMARY_MODEL` | `llama-3.3-70b-versatile` | Summarizer LLM model ID |
| `CHATBOT_USE_FAISS` | `false` | Use FAISS embeddings for retrieval instead of the simple local vector store |
| `ENABLE_OCR` | `true` | Enable/disable screen capture |
| `OCR_INTERVAL_SECONDS` | `3.0` | How often to poll for screen changes |
| `OCR_CHANGE_THRESHOLD` | `0.02` | Minimum pixel-change ratio to trigger OCR |
| `ENABLE_SPEAKER` | `true` | Enable the separate speaker-audio capture stream |
| `ENABLE_DIARIZATION` | `true` | Label utterances by speaker via Resemblyzer |
| `DIARIZATION_SIMILARITY` | `0.70` | Cosine threshold for matching an utterance to an existing speaker |
| `DIARIZATION_MIN_SAMPLES` | `16000` | Minimum audio samples (~1s) for a stable speaker embedding |
| `VAD_THRESHOLD` | `0.5` | Voice-activity-detection gate for transcription |
| `HOST` | `0.0.0.0` | Backend bind host |
| `PORT` | `8000` | Backend bind port |

---

## 🛠️ Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) — async web server + WebSockets
- [OpenAI Whisper](https://github.com/openai/whisper) — local speech-to-text
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) + [pytesseract](https://github.com/madmaze/pytesseract) — screen reading
- [Resemblyzer](https://github.com/resemble-ai/Resemblyzer) — offline speaker diarization (d-vector voice embeddings)
- [Groq API](https://console.groq.com/) (`llama-3.3-70b-versatile`) — summarization, chatbot, and keyword filtering
- [LangChain](https://www.langchain.com/) + [FAISS](https://faiss.ai/) — RAG chatbot retrieval
- [HuggingFace embeddings](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — local MiniLM embeddings for RAG
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
