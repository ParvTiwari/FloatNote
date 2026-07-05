import { Logo } from "./Logo";
import { GithubIcon } from "./Icons";
import { navLinks, siteConfig } from "@/lib/site";

export function Footer() {
  return (
    <footer className="border-t border-hair py-12">
      <div className="container-page">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-4 text-sm leading-relaxed t-muted">
              {siteConfig.tagline}. Real-time transcription, screen OCR, AI
              summaries, and a chatbot that knows your meeting — running quietly
              on your desktop.
            </p>
          </div>

          <nav aria-label="Footer" className="flex gap-16">
            <div>
              <h2 className="text-sm font-semibold t-strong">Product</h2>
              <ul className="mt-4 space-y-2">
                {navLinks.map((link) => (
                  <li key={link.href}>
                    <a
                      href={link.href}
                      className="text-sm t-muted transition-colors hover:text-slate-900 dark:hover:text-white"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="text-sm font-semibold t-strong">Resources</h2>
              <ul className="mt-4 space-y-2">
                <li>
                  <a
                    href={siteConfig.repo}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-sm t-muted transition-colors hover:text-slate-900 dark:hover:text-white"
                  >
                    <GithubIcon className="h-4 w-4" />
                    GitHub
                  </a>
                </li>
                <li>
                  <a
                    href={`${siteConfig.repo}#-setup--installation`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm t-muted transition-colors hover:text-slate-900 dark:hover:text-white"
                  >
                    Documentation
                  </a>
                </li>
              </ul>
            </div>
          </nav>
        </div>

        <div className="mt-10 flex flex-col items-center justify-between gap-4 border-t border-hair pt-6 sm:flex-row">
          <p className="text-xs t-faint">
            © {new Date().getFullYear()} {siteConfig.name}. Open source, built
            for better meetings.
          </p>
          <p className="text-xs t-faint">
            Powered by Whisper · LangChain · FastAPI
          </p>
          <p className="text-xs t-muted">
            Built by{" "}
            <a
              href="https://parv-tiwari-portfolio.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium t-strong underline decoration-slate-300 underline-offset-2 transition-colors hover:text-slate-900 dark:decoration-slate-600 dark:hover:text-white"
            >
              Parv Tiwari
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
