import { siteConfig } from "@/lib/site";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span
        aria-hidden="true"
        className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-sky-500 to-violet-600 text-base shadow-lg shadow-violet-900/40"
      >
        🎙️
      </span>
      <span className="text-lg font-bold tracking-tight t-strong">
        {siteConfig.name}
      </span>
    </span>
  );
}
