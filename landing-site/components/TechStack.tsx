import { techStack } from "@/lib/content";

export function TechStack() {
  return (
    <section
      id="tech"
      className="section-alt scroll-mt-20 py-20 sm:py-28"
    >
      <div className="container-page">
        <div className="grid gap-12 lg:grid-cols-[1fr_1.2fr] lg:items-center">
          <div>
            <span className="section-eyebrow">Under the hood</span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight t-strong sm:text-4xl">
              Local-first AI, wired together
            </h2>
            <p className="mt-4 text-lg leading-relaxed t-body">
              Transcription runs on your machine with Whisper. Slides are read
              with Tesseract OCR. A LangChain + FAISS pipeline turns it all into
              a queryable vector store — so the chatbot answers from what
              actually happened, not a guess.
            </p>
            <p className="mt-4 text-sm t-faint">
              Fully open source and configurable — bring your own models and API
              keys.
            </p>
          </div>

          <ul className="grid gap-3 sm:grid-cols-2">
            {techStack.map((tech) => (
              <li
                key={tech.name}
                className="glass-card flex items-center gap-3 p-4"
              >
                <span
                  aria-hidden="true"
                  className="h-2 w-2 shrink-0 rounded-full bg-gradient-to-r from-sky-400 to-violet-400"
                />
                <div>
                  <p className="text-sm font-semibold t-strong">{tech.name}</p>
                  <p className="text-xs t-muted">{tech.role}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
