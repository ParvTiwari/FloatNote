/**
 * Marketing content, kept out of the components so copy is easy to tune
 * and can also feed structured data (FAQ schema) from a single source.
 */

export const features = [
  {
    icon: "mic",
    title: "Live transcription",
    description:
      "Streams audio from your mic through OpenAI Whisper in real time — every word captured as it's spoken, no cloud upload required.",
  },
  {
    icon: "screen",
    title: "Screen OCR",
    description:
      "Reads slides and shared screens as they change, extracting on-screen text and keywords so your notes include what was shown, not just said.",
  },
  {
    icon: "sparkles",
    title: "AI summarization",
    description:
      "Turns hours of conversation into a tight summary with Groq's Llama 3.3 70B — the decisions, the context, the outcome.",
  },
  {
    icon: "chat",
    title: "Meeting chatbot",
    description:
      "Ask questions about any past meeting. Answers are grounded in a local vector store via retrieval-augmented generation — no hallucinated recaps.",
  },
  {
    icon: "speakers",
    title: "Speaker diarization",
    description:
      "Runs fully offline — Resemblyzer voice embeddings cluster each utterance in real time, so the transcript is labelled by who said what across the meeting.",
  },
  {
    icon: "check",
    title: "Action item extraction",
    description:
      "An NLP pipeline detects tasks and who they're assigned to, straight from spoken language — so nothing agreed on gets lost.",
  },
  {
    icon: "database",
    title: "Persistent memory",
    description:
      "Transcripts, OCR captures, and action items are saved locally to SQLite — searchable, queryable meeting memory that stays on your machine.",
  },
] as const;

export const steps = [
  {
    number: "01",
    title: "It runs in the background",
    description:
      "Launch FloatNote and it quietly listens to your mic and watches your screen. No bot joins the call, no awkward 'recording started' banner.",
  },
  {
    number: "02",
    title: "Everything becomes memory",
    description:
      "Speech becomes transcript, slides become text, and both are indexed into a local vector store as the meeting happens.",
  },
  {
    number: "03",
    title: "Ask it anything, after",
    description:
      "Get an instant AI summary, pull the action items, or chat with the meeting — 'What did we decide about the Q3 roadmap?' — and get grounded answers.",
  },
] as const;

export const useCases = [
  {
    title: "Product & engineering",
    description:
      "Capture roadmap debates and design decisions with the slides that drove them. Query 'why did we pick Postgres?' six weeks later.",
  },
  {
    title: "Sales & customer calls",
    description:
      "Never scribble notes mid-call again. Get the summary, the commitments, and the follow-ups extracted automatically.",
  },
  {
    title: "Research & interviews",
    description:
      "Transcribe user interviews verbatim, then chat across every session to find patterns without re-watching recordings.",
  },
  {
    title: "Students & lectures",
    description:
      "Record lectures with the on-screen slides captured via OCR, then ask the chatbot to explain any concept from class.",
  },
] as const;

export const techStack = [
  { name: "FastAPI", role: "Async server + WebSockets" },
  { name: "OpenAI Whisper", role: "Local speech-to-text" },
  { name: "Tesseract OCR", role: "Screen reading" },
  { name: "Resemblyzer", role: "Offline speaker diarization" },
  { name: "Groq Llama 3.3 70B", role: "Summaries, chat & keywords" },
  { name: "LangChain + FAISS", role: "RAG retrieval pipeline" },
  { name: "spaCy", role: "Action item extraction" },
  { name: "React 19 + Vite", role: "Dashboard UI" },
  { name: "Electron", role: "Desktop wrapper" },
] as const;

export const faqs = [
  {
    question: "Does my audio get sent to the cloud?",
    answer:
      "Transcription, speaker diarization, and the RAG embeddings all run locally on your machine, and your transcripts are stored in a local SQLite database. Only summarization and the chatbot reach out — they call the Groq API, so just the text you choose to summarize or query ever leaves your device.",
  },
  {
    question: "Do I have to invite a bot to my meeting?",
    answer:
      "No. FloatNote captures your microphone and reads your screen directly from your desktop. There's no meeting bot, no join link, and no participant to explain — it runs quietly in the background.",
  },
  {
    question: "What can the meeting chatbot actually answer?",
    answer:
      "Anything grounded in the meeting. It uses retrieval-augmented generation over a local vector store of your transcript and OCR captures (FAISS-backed when enabled), so it can surface decisions, action items, and context — with answers tied to what was actually said or shown.",
  },
  {
    question: "Which platforms does it run on?",
    answer:
      "FloatNote is desktop-first, built with a FastAPI backend and a React dashboard, with an optional Electron wrapper for a native window. Screen OCR currently defaults to a Windows Tesseract path; macOS and Linux users point it at their local Tesseract install.",
  },
  {
    question: "Is it free and open source?",
    answer:
      "Yes. FloatNote is open source — you run it yourself with your own Groq API key for the AI summaries and chatbot. The full source, setup guide, and configuration reference are on GitHub.",
  },
] as const;

export const stats = [
  { value: "Real-time", label: "Live transcription latency" },
  { value: "100%", label: "Transcripts stored locally" },
  { value: "0", label: "Meeting bots to invite" },
  { value: "Open", label: "Source, self-hosted" },
] as const;
