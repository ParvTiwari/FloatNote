# FloatNote — Marketing Site

A promotional single-page website for **FloatNote**, built with **Next.js 15 (App Router)**, **React 19**, **TypeScript**, and **Tailwind CSS**, with heavy SEO optimization.

This is a standalone project — it lives in its own folder and is independent of the FloatNote app in `../frontend` and `../backend`.

## Quick start

```bash
cd marketing-site
npm install
npm run dev      # http://localhost:3000
```

Production:

```bash
npm run build
npm run start
```

## What's inside

A single, smooth-scroll landing page composed of focused sections:

| Section | File |
|---|---|
| Sticky nav + mobile menu | `components/Navbar.tsx` |
| Hero with live-transcript mockup | `components/Hero.tsx` |
| Feature grid | `components/Features.tsx` |
| How it works | `components/HowItWorks.tsx` |
| Use cases | `components/UseCases.tsx` |
| Tech stack | `components/TechStack.tsx` |
| FAQ (accessible `<details>`) | `components/FAQ.tsx` |
| Call to action | `components/CTA.tsx` |
| Footer | `components/Footer.tsx` |

All copy lives in `lib/content.ts` and site-wide config in `lib/site.ts`, so text and links are easy to tune in one place.

### Download button & light/dark mode

- **Download for Windows** buttons appear in the nav, hero, and closing CTA. They point at `siteConfig.downloadWindowsUrl` (GitHub releases by default) — set it to a direct `.exe` URL once you publish an installer.
- **Light / dark theme toggle** lives in the navbar (`components/ThemeToggle.tsx`). The theme is a `.dark` class on `<html>`, applied **before first paint** by an inline script in `app/layout.tsx` (no flash), persisted to `localStorage`, and defaulting to the visitor's system preference. Colors are driven by theme-aware tokens (`t-strong`, `t-body`, `t-muted`, `.glass-card`, etc.) defined in `app/globals.css`.

## SEO features

- **Metadata API** (`app/layout.tsx`) — title template, description, keywords, canonical, `metadataBase`.
- **Open Graph + Twitter cards** — including a **dynamically generated OG image** (`app/opengraph-image.tsx`, 1200×630).
- **JSON-LD structured data** (`components/StructuredData.tsx`) — `SoftwareApplication`, `Organization`, `WebSite`, and `FAQPage` schemas for rich results.
- **`sitemap.xml`** (`app/sitemap.ts`) and **`robots.txt`** (`app/robots.ts`), generated at build time.
- **PWA manifest** (`app/manifest.ts`) + SVG favicon (`public/icon.svg`).
- Semantic HTML, correct heading hierarchy, skip-to-content link, `aria` labels, and `prefers-reduced-motion` support.
- Security response headers (`next.config.mjs`).
- Fully static — every route prerenders (`○ Static`), so it deploys anywhere and loads fast.

## Before deploying

Set your production domain so canonical URLs, the sitemap, and OG tags are correct:

```bash
# .env
NEXT_PUBLIC_SITE_URL=https://your-domain.com
```

(or edit the `url` fallback in `lib/site.ts`). Also update the `repo` / `twitter` handles in the same file.

## Deploy

Works out of the box on **Vercel** (recommended for Next.js), or any Node host via `npm run build && npm run start`. For a fully static export you can also add `output: "export"` to `next.config.mjs`.

## Design

Matches the FloatNote app's palette — a **sky → violet** accent gradient on a **slate-950** dark background, glassmorphism cards, and subtle motion (animated waveform, floating mockup, glow).
