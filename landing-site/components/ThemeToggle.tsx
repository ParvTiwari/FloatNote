"use client";

import { SunIcon, MoonIcon } from "./Icons";

/**
 * Light/dark toggle. The current theme lives as a `.dark` class on <html>
 * (set pre-paint by the inline script in the layout), so we read/flip that
 * class directly and persist the choice. Icons are shown via CSS `dark:`
 * variants, which keeps server and client markup identical — no hydration
 * mismatch and no flash.
 */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const toggle = () => {
    const el = document.documentElement;
    const next = el.classList.contains("dark") ? "light" : "dark";
    el.classList.toggle("dark", next === "dark");
    el.style.colorScheme = next;
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* storage may be unavailable (private mode) — theme still applies */
    }
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Toggle light and dark mode"
      title="Toggle theme"
      className={`inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-300 text-slate-600 transition-colors hover:bg-slate-100 dark:border-white/10 dark:text-slate-200 dark:hover:bg-white/5 ${className}`}
    >
      <SunIcon className="hidden h-5 w-5 dark:block" />
      <MoonIcon className="h-5 w-5 dark:hidden" />
    </button>
  );
}
