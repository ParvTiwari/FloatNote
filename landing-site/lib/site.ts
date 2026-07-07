/**
 * Central site configuration. Update these values for your deployment —
 * `url` in particular drives canonical links, sitemap, and Open Graph tags.
 */
export const siteConfig = {
  name: "FloatNote",
  shortName: "FloatNote",
  tagline: "Real-time meeting intelligence",
  description:
    "FloatNote is a desktop-first meeting assistant that runs quietly in the background — live Whisper transcription, screen OCR, AI summaries, and a chatbot that actually knows your meeting.",
  // Change this to your production domain before deploying.
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "https://parv-tiwari-floatnote.vercel.app",
  ogImage: "/opengraph-image",
  keywords: [
    "meeting assistant",
    "real-time transcription",
    "AI meeting notes",
    "Whisper transcription",
    "meeting summary AI",
    "meeting chatbot",
    "screen OCR",
    "speaker diarization",
    "action item extraction",
    "RAG meeting search",
    "desktop meeting recorder",
    "FloatNote",
  ],
  author: "FloatNote",
  twitter: "@floatnote",
  repo: "https://github.com/ParvTiwari/FloatNote",
  // Windows installer / release download. Points at GitHub releases by default —
  // swap for a direct .exe URL once you publish an installer.
  downloadWindowsUrl:
    "https://github.com/ParvTiwari/FloatNote/releases/latest",
  locale: "en_US",
} as const;

export type NavLink = { label: string; href: string };

export const navLinks: NavLink[] = [
  { label: "Features", href: "#features" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Use cases", href: "#use-cases" },
  { label: "Tech", href: "#tech" },
  { label: "FAQ", href: "#faq" },
];
