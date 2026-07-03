import { features } from "@/lib/content";
import { featureIconMap, type FeatureIconKey } from "./Icons";

export function Features() {
  return (
    <section id="features" className="scroll-mt-20 py-20 sm:py-28">
      <div className="container-page">
        <div className="mx-auto max-w-2xl text-center">
          <span className="section-eyebrow">Features</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight t-strong sm:text-4xl">
            Everything a meeting leaves behind — captured
          </h2>
          <p className="mt-4 text-lg t-body">
            Seven systems working together, from the moment audio hits your mic to
            the question you ask three weeks later.
          </p>
        </div>

        <ul className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => {
            const Icon = featureIconMap[feature.icon as FeatureIconKey];
            return (
              <li
                key={feature.title}
                className="glass-card group p-6 transition-colors duration-300 hover:border-slate-300 dark:hover:border-white/20 dark:hover:bg-white/[0.05]"
              >
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/15 to-violet-600/15 text-sky-600 ring-1 ring-inset ring-slate-200 transition-transform duration-300 group-hover:scale-110 dark:from-sky-500/20 dark:to-violet-600/20 dark:text-sky-300 dark:ring-white/10">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-lg font-semibold t-strong">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed t-muted">
                  {feature.description}
                </p>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
