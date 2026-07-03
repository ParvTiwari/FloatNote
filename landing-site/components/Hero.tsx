import { ArrowIcon, GithubIcon, WindowsIcon } from "./Icons";
import { siteConfig } from "@/lib/site";
import { stats } from "@/lib/content";

function Waveform() {
  const bars = [0.4, 0.7, 1, 0.6, 0.9, 0.5, 0.8, 0.35, 0.75, 0.55];
  return (
    <div className="flex h-8 items-center gap-1" aria-hidden="true">
      {bars.map((h, i) => (
        <span
          key={i}
          className="w-1 rounded-full bg-gradient-to-t from-sky-500 to-violet-400 animate-waveform"
          style={{
            height: `${h * 100}%`,
            animationDelay: `${i * 0.09}s`,
          }}
        />
      ))}
    </div>
  );
}

function TranscriptMock() {
  const lines = [
    { who: "MIC", text: "Let's align on the Q3 roadmap before we ship.", tone: "sky" },
    { who: "OCR", text: "Slide: Roadmap Overview — 3 priorities", tone: "violet" },
    { who: "MIC", text: "Priya will share the draft by Friday.", tone: "sky" },
  ];
  // Kept dark in both themes — it's a screenshot of the FloatNote app UI.
  return (
    <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900/90 p-5 shadow-2xl shadow-violet-950/50 backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
          </span>
          <span className="text-xs font-medium text-slate-300">
            Recording · Live
          </span>
        </div>
        <Waveform />
      </div>

      <ul className="space-y-3">
        {lines.map((line, i) => (
          <li key={i} className="flex gap-3">
            <span
              className={`mt-0.5 shrink-0 rounded-md px-2 py-0.5 text-[10px] font-semibold tracking-wide ${
                line.tone === "sky"
                  ? "bg-sky-500/15 text-sky-300"
                  : "bg-violet-500/15 text-violet-300"
              }`}
            >
              {line.who}
            </span>
            <p className="text-sm leading-relaxed text-slate-200">{line.text}</p>
          </li>
        ))}
      </ul>

      <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/60 p-3">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-teal-300">
          Action item detected
        </p>
        <p className="text-sm text-slate-200">
          Share roadmap draft{" "}
          <span className="text-slate-400">→ assigned to Priya, due Fri</span>
        </p>
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section
      id="top"
      className="relative overflow-hidden pb-16 pt-28 sm:pt-32 lg:pb-24"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-24 -z-10 h-72 w-[42rem] -translate-x-1/2 rounded-full bg-violet-600/20 blur-3xl animate-pulse-glow"
      />

      <div className="container-page grid items-center gap-12 lg:grid-cols-2">
        <div className="animate-fade-up">
          <span className="section-eyebrow">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
            Desktop-first meeting assistant
          </span>

          <h1 className="mt-4 text-4xl font-extrabold leading-[1.08] tracking-tight t-strong sm:text-5xl lg:text-6xl">
            Your meetings, turned into{" "}
            <span className="gradient-text">searchable memory.</span>
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-relaxed t-body">
            {siteConfig.name} runs quietly in the background — capturing your
            mic, reading your screen, and turning every meeting into live
            transcripts, AI summaries, and a chatbot that actually knows what
            was said.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4" id="get-started">
            <a
              href={siteConfig.downloadWindowsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary"
            >
              <WindowsIcon className="h-4 w-4" />
              Download for Windows
            </a>
            <a
              href={siteConfig.repo}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost"
            >
              <GithubIcon className="h-4 w-4" />
              View on GitHub
              <ArrowIcon className="h-4 w-4" />
            </a>
          </div>

          <p className="mt-4 text-sm t-faint">
            Free &amp; open source · Windows 10/11 · Your transcripts stay on your
            machine
          </p>
        </div>

        <div className="flex justify-center lg:justify-end">
          <div className="animate-float">
            <TranscriptMock />
          </div>
        </div>
      </div>

      <dl className="container-page mt-16 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-slate-200 bg-slate-200 dark:border-white/10 dark:bg-white/5 sm:mt-20 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-white px-6 py-6 text-center dark:bg-slate-950/40"
          >
            <dt className="sr-only">{stat.label}</dt>
            <dd>
              <span className="block text-2xl font-bold t-strong sm:text-3xl">
                {stat.value}
              </span>
              <span className="mt-1 block text-xs t-muted">{stat.label}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
