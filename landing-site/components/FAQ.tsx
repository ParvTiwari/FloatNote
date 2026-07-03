import { faqs } from "@/lib/content";

export function FAQ() {
  return (
    <section id="faq" className="scroll-mt-20 py-20 sm:py-28">
      <div className="container-page max-w-3xl">
        <div className="text-center">
          <span className="section-eyebrow">FAQ</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight t-strong sm:text-4xl">
            Questions, answered
          </h2>
        </div>

        <div className="mt-12 space-y-3">
          {faqs.map((faq, i) => (
            <details
              key={i}
              className="glass-card group overflow-hidden [&_summary::-webkit-details-marker]:hidden"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 text-left font-medium t-strong transition-colors hover:text-sky-600 dark:hover:text-sky-300">
                {faq.question}
                <span
                  aria-hidden="true"
                  className="shrink-0 t-muted transition-transform duration-200 group-open:rotate-45"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  >
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                </span>
              </summary>
              <p className="px-6 pb-5 text-sm leading-relaxed t-muted">
                {faq.answer}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
