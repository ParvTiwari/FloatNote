import { useEffect, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_BASE_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

function App() {
  const [meetingId, setMeetingId] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [keywords, setKeywords] = useState([]);
  const [actions, setActions] = useState([]);
  const [ocr, setOcr] = useState({ text: "", keywords: [] });
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [summary, setSummary] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const wsRef = useRef(null);
  const transcriptRef = useRef(null);
  const chatRef = useRef(null);
  const summaryRequestInFlightRef = useRef(false);

  useEffect(() => {
    if (transcriptRef.current) {
      const container = transcriptRef.current;
      container.scrollTo({
        top: container.scrollHeight - container.clientHeight + 100,
        behavior: "smooth",
      });
    }
  }, [transcript]);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTo({
        top: chatRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [chatHistory, chatLoading]);

  useEffect(() => {
    let reconnectTimer = null;
    let isUnmounted = false;

    const connect = () => {
      const ws = new WebSocket(WS_BASE_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus("🟢 Connected");
        console.log("✅ Connected - waiting handshake");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "connected") {
            setMeetingId(data.meeting_id ?? null);
            setConnectionStatus("🟢 Connected");
            return;
          }

          if (data.type === "ocr") {
            const incoming = data.ocr;
            if (incoming?.text?.trim().length > 0) {
              setOcr({
                text: incoming.text,
                keywords: incoming.keywords || [],
                _everReceived: true,
              });
            } else {
              setOcr((prev) => ({ ...prev, _everReceived: true }));
            }
            return;
          }

          const analysis = data;

          if (analysis.meeting_id) {
            setMeetingId(analysis.meeting_id);
          }

          if (analysis.text?.trim()) {
            setTranscript((prev) => [
              ...prev,
              { text: analysis.text, source: analysis.source || "MIC" },
            ]);
          }

          setKeywords((prev) => {
            const allKeywords = [...prev, ...(analysis.keywords || [])];
            return [...new Set(allKeywords)].slice(0, 20);
          });

          if (analysis.actions && analysis.actions.length > 0) {
            setActions((prev) => {
              const normalizedExisting = prev.map((item) => item.toLowerCase());
              const nextActions = analysis.actions.filter((action) => {
                const normalizedAction = String(action).toLowerCase();
                return !normalizedExisting.includes(normalizedAction);
              });
              return [...prev, ...nextActions];
            });
          }

          if (analysis.ocr) {
            const incoming = analysis.ocr;
            if (incoming.text && incoming.text.trim().length > 0) {
              setOcr({
                text: incoming.text,
                keywords: incoming.keywords || [],
                _everReceived: true,
              });
            }
          }
        } catch {
          console.log("Terminal text:", event.data);
        }
      };

      ws.onclose = () => {
        if (isUnmounted) return;
        setConnectionStatus("🔴 Disconnected");
        reconnectTimer = setTimeout(() => {
          console.log("🔄 Reconnecting...");
          connect();
        }, 2000);
      };

      ws.onerror = (error) => {
        setConnectionStatus("❌ Error");
        console.error("WebSocket error:", error);
      };
    };

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  async function fetchSummary() {
    if (summaryRequestInFlightRef.current) {
      return;
    }

    summaryRequestInFlightRef.current = true;
    setSummaryLoading(true);
    setSummaryError("");

    try {
      const endpoint = meetingId
        ? `${API_BASE_URL}/meetings/${meetingId}/summary`
        : `${API_BASE_URL}/meetings/latest/summary`;
      const response = await fetch(endpoint);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to generate summary.");
      }

      setSummary(data.summary || "");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected summary error.";
      setSummary("");
      setSummaryError(message);
      console.error("Summary error:", message);
    } finally {
      summaryRequestInFlightRef.current = false;
      setSummaryLoading(false);
    }
  }

  async function handleGenerateSummary() {
    await fetchSummary();
  }

  async function handleAskChatbot(event) {
    event.preventDefault();

    const question = chatQuestion.trim();
    if (!question) {
      setChatError("Type a question first.");
      return;
    }

    setChatLoading(true);
    setChatError("");

    const nextMessage = { role: "user", text: question };
    setChatHistory((prev) => [...prev, nextMessage]);
    setChatQuestion("");

    try {
      const endpoint = meetingId
        ? `${API_BASE_URL}/meetings/${meetingId}/chat`
        : `${API_BASE_URL}/meetings/latest/chat`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Failed to get chatbot response.");
      }

      setChatHistory((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.answer || "No answer returned.",
        },
      ]);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected chatbot error.";
      setChatError(message);
      setChatHistory((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Error: ${message}`,
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  // Enter sends the question, Shift+Enter inserts a newline.
  function handleChatKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleAskChatbot(event);
    }
  }

  const clearAll = () => {
    setTranscript([]);
    setKeywords([]);
    setActions([]);
    setOcr({ text: "", keywords: [], _everReceived: false });
    setSummary("");
    setSummaryError("");
    setChatQuestion("");
    setChatError("");
    setChatHistory([]);
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#fef3c7_0%,_#fff7ed_28%,_#e0f2fe_64%,_#dbeafe_100%)] p-6 md:p-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 rounded-[2rem] border border-white/70 bg-white/70 p-6 shadow-[0_25px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="mb-3 text-sm font-semibold uppercase tracking-[0.35em] text-sky-700">
                Real-Time AI-Based Meeting Assistance System
              </p>
              <h1 className="font-serif text-4xl font-black tracking-tight text-slate-900 md:text-5xl">
                FloatNote AI
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
                Live transcript, OCR capture, meeting summary, and grounded
                chatbot answers from the same saved meeting stream.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl bg-slate-950 px-4 py-3 text-left text-white shadow-lg">
                <p className="text-xs uppercase tracking-[0.25em] text-slate-400">
                  Connection
                </p>
                <p className="mt-2 text-sm font-semibold">{connectionStatus}</p>
              </div>
              <div className="rounded-2xl bg-amber-100/80 px-4 py-3 text-left text-amber-950 shadow-lg">
                <p className="text-xs uppercase tracking-[0.25em] text-amber-700">
                  Meeting
                </p>
                <p className="mt-2 text-sm font-semibold">
                  {meetingId ? `#${meetingId}` : "Waiting for first handshake"}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-8 xl:grid-cols-[1.5fr_0.9fr]">
          <div className="space-y-8">
            <section className="rounded-[2rem] border border-white/70 bg-white/75 p-7 shadow-[0_24px_70px_rgba(15,23,42,0.12)] backdrop-blur-xl">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="text-2xl font-bold text-slate-900">
                  📝 Live Transcript
                </h2>
                <span className="rounded-full bg-sky-100 px-4 py-1 text-sm font-semibold text-sky-700">
                  LIVE STREAM
                </span>
              </div>

              <div
                ref={transcriptRef}
                className="h-[360px] space-y-3 overflow-y-auto pr-2"
              >
                {transcript.map((entry, index) => {
                  const isSpeaker = entry.source === "SPEAKER";
                  return (
                    <div
                      key={`${entry.text}-${index}`}
                      className={`rounded-[1.5rem] border-l-4 p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${
                        isSpeaker
                          ? "border-violet-300 bg-gradient-to-r from-slate-50 to-violet-50"
                          : "border-sky-300 bg-gradient-to-r from-slate-50 to-sky-50"
                      }`}
                    >
                      <span
                        className={`mb-2 inline-flex items-center gap-1 rounded-full px-3 py-0.5 text-xs font-semibold uppercase tracking-wide ${
                          isSpeaker
                            ? "bg-violet-100 text-violet-700"
                            : "bg-sky-100 text-sky-700"
                        }`}
                      >
                        {isSpeaker ? "🔊 Participant" : "🎤 You"}
                      </span>
                      <p className="text-left leading-7 text-slate-700">
                        {entry.text}
                      </p>
                    </div>
                  );
                })}

                {transcript.length === 0 && (
                  <div className="flex h-full items-center justify-center text-slate-400">
                    <div className="text-center">
                      <div className="mx-auto mb-4 h-16 w-16 animate-spin rounded-full border-4 border-dashed border-slate-300" />
                      <p className="text-lg font-medium">
                        Listening for live speech...
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </section>

            <section className="grid grid-cols-1 gap-8 lg:grid-cols-2">
              <div className="rounded-[2rem] border border-white/70 bg-white/75 p-7 shadow-[0_24px_70px_rgba(15,23,42,0.12)] backdrop-blur-xl">
                <div className="mb-5 flex items-center justify-between">
                  <h2 className="text-2xl font-bold text-slate-900">
                    🖥️ Screen Reader
                  </h2>
                  <span
                    className={`rounded-full px-4 py-1 text-sm font-semibold ${
                      ocr.text
                        ? "bg-emerald-100 text-emerald-700"
                        : ocr._everReceived
                          ? "bg-amber-100 text-amber-700"
                          : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {ocr.text ? "ACTIVE" : ocr._everReceived ? "IDLE" : "DISABLED"}
                  </span>
                </div>

                <div className="mb-4 h-[180px] overflow-y-auto rounded-[1.5rem] bg-slate-950 p-4 font-mono text-sm">
                  {ocr.text ? (
                    <pre className="whitespace-pre-wrap leading-7 text-emerald-400">
                      {ocr.text}
                    </pre>
                  ) : (
                    <p className="italic text-slate-500">
                      No screen content detected. Keep a slide or visible content
                      on screen while OCR is enabled.
                    </p>
                  )}
                </div>

                {ocr.keywords.length > 0 && (
                  <div>
                    <p className="mb-3 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">
                      Slide keywords
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {ocr.keywords.map((keyword, index) => (
                        <span
                          key={`${keyword}-${index}`}
                          className="rounded-xl bg-gradient-to-r from-emerald-100 to-teal-100 px-3 py-1 text-sm font-semibold text-teal-800"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="rounded-[2rem] border border-white/70 bg-white/75 p-7 shadow-[0_24px_70px_rgba(15,23,42,0.12)] backdrop-blur-xl">
                <div className="mb-5 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-2xl font-bold text-slate-900">
                      🧠 Meeting Summary
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={handleGenerateSummary}
                    disabled={summaryLoading}
                    className="rounded-2xl bg-gradient-to-r from-sky-600 to-cyan-600 px-5 py-3 text-sm font-semibold text-white shadow-lg transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {summaryLoading ? "Generating..." : "Generate Summary"}
                  </button>
                </div>

                <div className="h-[220px] overflow-y-auto rounded-[1.5rem] border border-slate-200 bg-white p-5 text-left shadow-inner">
                  {summaryError ? (
                    <p className="font-medium text-rose-600">⚠️ {summaryError}</p>
                  ) : summary ? (
                    <pre className="whitespace-pre-wrap font-sans leading-7 text-slate-700">
                      {summary}
                    </pre>
                  ) : (
                    <p className="text-slate-400">
                      Generate a meeting summary after real transcript data has
                      been saved.
                    </p>
                  )}
                </div>
              </div>
            </section>
          </div>

          <div className="space-y-8">
            <section className="rounded-[2rem] border border-white/70 bg-white/75 p-6 shadow-[0_24px_70px_rgba(15,23,42,0.12)] backdrop-blur-xl">
              <h3 className="mb-4 text-xl font-bold text-slate-900">
                🗝️ Keywords ({keywords.length})
              </h3>
              <div className="flex flex-wrap gap-2">
                {keywords.map((keyword, index) => (
                  <span
                    key={`${keyword}-${index}`}
                    className="rounded-2xl bg-gradient-to-r from-sky-100 to-blue-200 px-4 py-2 text-sm font-semibold text-sky-900"
                  >
                    {keyword}
                  </span>
                ))}
                {keywords.length === 0 && (
                  <p className="italic text-slate-400">No keywords detected yet.</p>
                )}
              </div>
            </section>

            <section className="rounded-[2rem] border border-white/70 bg-white/75 p-6 shadow-[0_24px_70px_rgba(15,23,42,0.12)] backdrop-blur-xl">
              <h3 className="mb-4 text-xl font-bold text-slate-900">
                ✅ Action Items ({actions.length})
              </h3>
              <div className="max-h-72 space-y-3 overflow-y-auto">
                {actions.map((action, index) => (
                  <div
                    key={`${action}-${index}`}
                    className="rounded-[1.4rem] border-l-4 border-orange-400 bg-gradient-to-r from-orange-50 to-amber-50 p-4"
                  >
                    <div className="text-left font-semibold text-slate-800">
                      {action}
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-sm text-slate-500">
                      <div className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
                      <span>AI extracted</span>
                    </div>
                  </div>
                ))}
                {actions.length === 0 && (
                  <div className="py-10 text-center text-slate-400">
                    <div className="mb-4 text-4xl">🎯</div>
                    <p className="font-medium">No actions detected yet</p>
                    <p className="text-sm">
                      Try saying "Sarah needs to review the proposal”.
                    </p>
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-[2rem] border border-white/70 bg-slate-950 p-6 text-white shadow-[0_24px_70px_rgba(15,23,42,0.18)]">
              <div className="mb-5">
                <h3 className="text-2xl font-bold">💬 Meeting Chatbot</h3>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  Ask questions against the latest saved meeting transcript,
                  OCR text, and action items from the current meeting.
                </p>
              </div>

              <div
                ref={chatRef}
                className="mb-4 h-[360px] space-y-3 overflow-y-auto rounded-[1.5rem] bg-white/5 p-4"
              >
                {chatHistory.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    className={`max-w-[92%] rounded-[1.4rem] px-4 py-3 text-left leading-7 shadow-sm ${
                      message.role === "user"
                        ? "ml-auto bg-sky-500 text-white"
                        : "bg-white/10 text-slate-100"
                    }`}
                  >
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] opacity-70">
                      {message.role === "user" ? "You" : "FloatNote"}
                    </p>
                    <p>{message.text}</p>
                  </div>
                ))}

                {chatHistory.length === 0 && !chatLoading && (
                  <div className="flex h-full items-center justify-center text-center text-slate-400">
                    <div>
                      <div className="mb-3 text-4xl">🧭</div>
                      <p className="font-medium">
                        Ask about decisions, deadlines, or OCR content.
                      </p>
                    </div>
                  </div>
                )}

                {chatLoading && (
                  <div className="max-w-[92%] rounded-[1.4rem] bg-white/10 px-4 py-3 text-left text-slate-200">
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] opacity-70">
                      FloatNote
                    </p>
                    <p>Thinking through the saved meeting context...</p>
                  </div>
                )}
              </div>

              <form onSubmit={handleAskChatbot} className="space-y-3">
                <textarea
                  value={chatQuestion}
                  onChange={(event) => setChatQuestion(event.target.value)}
                  onKeyDown={handleChatKeyDown}
                  placeholder="Ask something like: What were the main blockers discussed? (Enter to send, Shift+Enter for a new line)"
                  className="min-h-[110px] w-full rounded-[1.4rem] border border-white/10 bg-white/10 px-4 py-3 text-white placeholder:text-slate-400 focus:border-cyan-400 focus:outline-none"
                />

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-sm text-slate-300">
                    {chatError ? (
                      <span className="text-rose-300">{chatError}</span>
                    ) : (
                      <span>
                        Using{" "}
                        {meetingId ? `meeting #${meetingId}` : "the latest saved meeting"}.
                      </span>
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={chatLoading}
                    className="rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 px-6 py-3 font-semibold text-slate-950 shadow-lg transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {chatLoading ? "Asking..." : "Ask Chatbot"}
                  </button>
                </div>
              </form>
            </section>
          </div>
        </div>

        <div className="mt-10 rounded-[2rem] border border-white/70 bg-white/60 p-6 shadow-[0_24px_70px_rgba(15,23,42,0.12)] backdrop-blur-xl">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-2 text-sm text-slate-600 md:flex-row md:flex-wrap md:gap-6">
              <span>{connectionStatus}</span>
              <span>📝 Transcript lines: {transcript.length}</span>
              <span>🗝️ Keywords: {keywords.length}</span>
              <span>✅ Actions: {actions.length}</span>
            </div>
            <button
              onClick={clearAll}
              className="rounded-2xl bg-gradient-to-r from-rose-500 to-rose-600 px-8 py-3 font-semibold text-white shadow-lg transition-all hover:-translate-y-0.5 hover:shadow-xl"
            >
              🗑️ Clear Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
