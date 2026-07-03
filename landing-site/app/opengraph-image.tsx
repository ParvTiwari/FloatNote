import { ImageResponse } from "next/og";
import { siteConfig } from "@/lib/site";

export const alt = `${siteConfig.name} — ${siteConfig.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#020617",
          backgroundImage:
            "radial-gradient(900px 900px at 85% -10%, rgba(124,58,237,0.45), transparent 60%), radial-gradient(700px 700px at 0% 20%, rgba(14,165,233,0.35), transparent 55%)",
          padding: "80px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 72,
              height: 72,
              borderRadius: 20,
              background: "linear-gradient(135deg, #0ea5e9, #7c3aed)",
              fontSize: 40,
            }}
          >
            🎙️
          </div>
          <div style={{ color: "white", fontSize: 40, fontWeight: 700 }}>
            {siteConfig.name}
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div
            style={{
              color: "white",
              fontSize: 82,
              fontWeight: 800,
              lineHeight: 1.05,
              maxWidth: 900,
              letterSpacing: "-0.03em",
            }}
          >
            Real-time meeting intelligence.
          </div>
          <div style={{ color: "#94a3b8", fontSize: 34, maxWidth: 880 }}>
            Live transcription, screen OCR, AI summaries, and a chatbot that
            knows your meeting.
          </div>
        </div>

        <div style={{ display: "flex", gap: 16 }}>
          {["Transcribe", "Summarize", "Ask anything"].map((chip) => (
            <div
              key={chip}
              style={{
                color: "#e2e8f0",
                fontSize: 26,
                padding: "10px 24px",
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.15)",
                background: "rgba(255,255,255,0.04)",
              }}
            >
              {chip}
            </div>
          ))}
        </div>
      </div>
    ),
    { ...size },
  );
}
