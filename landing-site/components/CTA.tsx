import { GithubIcon, WindowsIcon } from "./Icons";
import { siteConfig } from "@/lib/site";

export function CTA() {
  return (
    <section className="py-20 sm:py-24">
      <div className="container-page">
        <div className="glass-card relative overflow-hidden px-6 py-14 text-center sm:px-12 sm:py-16">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-sky-600/15 via-transparent to-violet-600/20"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-0 -z-10 h-40 w-96 -translate-x-1/2 rounded-full bg-violet-500/20 blur-3xl"
          />

          <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight t-strong sm:text-4xl">
            Stop taking notes. Start asking your meetings.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg t-body">
            Download FloatNote for Windows, or clone the repo and run it in
            minutes — free and fully yours.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
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
              Star on GitHub
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
