import { useCases } from "@/lib/content";

export function UseCases() {
  return (
    <section id="use-cases" className="scroll-mt-20 py-20 sm:py-28">
      <div className="container-page">
        <div className="mx-auto max-w-2xl text-center">
          <span className="section-eyebrow">Use cases</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight t-strong sm:text-4xl">
            Built for anyone whose work happens in meetings
          </h2>
        </div>

        <div className="mt-14 grid gap-6 sm:grid-cols-2">
          {useCases.map((useCase) => (
            <article
              key={useCase.title}
              className="glass-card relative overflow-hidden p-7 transition-colors duration-300 hover:border-slate-300 dark:hover:border-white/20"
            >
              <span
                aria-hidden="true"
                className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br from-sky-500/10 to-violet-600/10 blur-xl"
              />
              <h3 className="text-xl font-semibold t-strong">
                {useCase.title}
              </h3>
              <p className="mt-3 leading-relaxed t-muted">
                {useCase.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
