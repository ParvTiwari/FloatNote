import { steps } from "@/lib/content";

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="section-alt scroll-mt-20 py-20 sm:py-28"
    >
      <div className="container-page">
        <div className="mx-auto max-w-2xl text-center">
          <span className="section-eyebrow">How it works</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight t-strong sm:text-4xl">
            No bot to invite. No workflow to change.
          </h2>
          <p className="mt-4 text-lg t-body">
            FloatNote sits on your desktop and does the remembering for you.
          </p>
        </div>

        <ol className="mt-14 grid gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <li key={step.number} className="relative">
              {i < steps.length - 1 && (
                <span
                  aria-hidden="true"
                  className="absolute left-6 top-14 hidden h-px w-full bg-gradient-to-r from-slate-300 to-transparent dark:from-white/20 md:block"
                />
              )}
              <div className="glass-card relative h-full p-6">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-violet-600 text-lg font-bold text-white shadow-lg shadow-violet-900/40">
                  {step.number}
                </span>
                <h3 className="mt-5 text-lg font-semibold t-strong">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed t-muted">
                  {step.description}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
