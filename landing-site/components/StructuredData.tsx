import { siteConfig } from "@/lib/site";
import { faqs } from "@/lib/content";

/**
 * JSON-LD structured data for rich results. Emits SoftwareApplication,
 * Organization, WebSite, and FAQPage schemas so search engines can render
 * rich snippets and understand the product.
 */
export function StructuredData() {
  const graph = [
    {
      "@type": "SoftwareApplication",
      "@id": `${siteConfig.url}/#software`,
      name: siteConfig.name,
      applicationCategory: "BusinessApplication",
      operatingSystem: "Windows, macOS, Linux",
      description: siteConfig.description,
      url: siteConfig.url,
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
      },
      featureList: [
        "Real-time Whisper transcription",
        "Screen OCR capture",
        "Offline speaker diarization",
        "AI meeting summarization",
        "RAG meeting chatbot",
        "Action item extraction",
        "Local persistent storage",
      ],
      softwareHelp: siteConfig.repo,
    },
    {
      "@type": "Organization",
      "@id": `${siteConfig.url}/#organization`,
      name: siteConfig.name,
      url: siteConfig.url,
      sameAs: [siteConfig.repo],
    },
    {
      "@type": "WebSite",
      "@id": `${siteConfig.url}/#website`,
      url: siteConfig.url,
      name: siteConfig.name,
      description: siteConfig.description,
      publisher: { "@id": `${siteConfig.url}/#organization` },
    },
    {
      "@type": "FAQPage",
      "@id": `${siteConfig.url}/#faq`,
      mainEntity: faqs.map((f) => ({
        "@type": "Question",
        name: f.question,
        acceptedAnswer: {
          "@type": "Answer",
          text: f.answer,
        },
      })),
    },
  ];

  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": graph,
  };

  return (
    <script
      type="application/ld+json"
      // JSON-LD is trusted, static content generated on the server.
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
