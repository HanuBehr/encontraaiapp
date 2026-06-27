"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n/client";
import { LOCALES, type Locale } from "@/lib/i18n/translations";

function FlagIcon({ locale }: { locale: Locale }) {
  if (locale === "pt-BR") {
    return (
      <svg viewBox="0 0 28 20" aria-hidden="true" className="h-4 w-6 overflow-hidden rounded-[4px] shadow-[inset_0_0_0_1px_rgba(0,0,0,0.12)]">
        <rect width="28" height="20" fill="#229E45" />
        <path d="M14 3 24 10 14 17 4 10Z" fill="#F8E04E" />
        <circle cx="14" cy="10" r="4.2" fill="#2B4EA2" />
        <path d="M10.1 8.9c2.8-.6 5.3-.2 7.8 1.5" stroke="#FFFFFF" strokeWidth="1" fill="none" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 28 20" aria-hidden="true" className="h-4 w-6 overflow-hidden rounded-[4px] shadow-[inset_0_0_0_1px_rgba(0,0,0,0.12)]">
      <rect width="28" height="20" fill="#1F3D8F" />
      <path d="M0 0 28 20M28 0 0 20" stroke="#FFFFFF" strokeWidth="4" />
      <path d="M0 0 28 20M28 0 0 20" stroke="#C8102E" strokeWidth="2" />
      <path d="M14 0v20M0 10h28" stroke="#FFFFFF" strokeWidth="6" />
      <path d="M14 0v20M0 10h28" stroke="#C8102E" strokeWidth="3.5" />
    </svg>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="currentColor">
      <path d="M12 .5A11.5 11.5 0 0 0 8.36 22.9c.58.1.8-.25.8-.56v-2.03c-3.25.7-3.94-1.38-3.94-1.38-.53-1.34-1.3-1.7-1.3-1.7-1.06-.72.08-.7.08-.7 1.17.08 1.79 1.2 1.79 1.2 1.04 1.77 2.73 1.26 3.4.96.1-.75.4-1.26.73-1.55-2.6-.29-5.33-1.3-5.33-5.75 0-1.27.45-2.31 1.2-3.13-.12-.29-.52-1.48.11-3.09 0 0 .98-.31 3.19 1.2A11.1 11.1 0 0 1 12 5.98c.99 0 1.98.13 2.91.39 2.2-1.51 3.18-1.2 3.18-1.2.63 1.61.23 2.8.11 3.09.75.82 1.2 1.86 1.2 3.13 0 4.46-2.73 5.45-5.34 5.74.42.36.8 1.08.8 2.17v3.04c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

export function DemoHome() {
  const { locale, setLocale } = useI18n();
  const copy = homeCopy[locale];

  return (
    <div className="relative min-h-[calc(100vh-4rem)] py-1">
      <div className="pointer-events-none absolute left-[-12rem] top-10 h-[28rem] w-[28rem] rounded-full bg-brand-orchid/10 blur-3xl" />
      <div className="pointer-events-none absolute right-[-10rem] top-0 h-[24rem] w-[24rem] rounded-full bg-brand-olive/18 blur-3xl" />

      <div className="relative mx-auto max-w-6xl">
        <section className="flex justify-end py-1">
          <div className="inline-flex items-center rounded-full border border-brand-orchid/14 bg-[linear-gradient(135deg,rgba(255,255,255,0.56),rgba(237,233,254,0.42))] p-1.5 shadow-[0_18px_46px_rgba(47,38,61,0.10),inset_0_1px_0_rgba(255,255,255,0.72)] backdrop-blur-2xl">
            <div className="inline-flex self-start rounded-full sm:self-auto">
              {LOCALES.map((option) => {
                const active = option === locale;
                return (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setLocale(option as Locale)}
                    aria-pressed={active}
                    className={`inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-bold transition focus:outline-none focus:ring-2 focus:ring-brand-orchid/35 sm:px-4 motion-reduce:transition-none ${
                      active
                        ? "bg-[linear-gradient(135deg,#6d28d9,#8b5cf6)] text-white shadow-[0_11px_26px_rgba(109,40,217,0.27),inset_0_1px_0_rgba(255,255,255,0.34)] backdrop-blur-xl"
                        : "text-brand-muted hover:bg-brand-orchid/[0.07] hover:text-brand-graphite"
                    }`}
                  >
                    <FlagIcon locale={option} />
                    <span>{option === "pt-BR" ? "Português" : "English"}</span>
                  </button>
                );
              })}
            </div>
            <span className="mx-1.5 h-6 w-px bg-brand-orchid/10" aria-hidden="true" />
            <a
              href="https://github.com/HanuBehr/encontraaiapp"
              target="_blank"
              rel="noreferrer"
              title={copy.sourceTitle}
              aria-label={copy.sourceTitle}
              className="group inline-flex h-10 w-10 items-center justify-center rounded-full text-brand-graphite transition hover:bg-brand-graphite/90 hover:text-white hover:shadow-[0_14px_30px_rgba(29,22,48,0.18)] focus:outline-none focus:ring-2 focus:ring-brand-orchid/35 motion-reduce:transition-none"
            >
              <GitHubIcon className="h-[1.15rem] w-[1.15rem] transition-transform group-hover:-translate-y-0.5 motion-reduce:transition-none" />
            </a>
          </div>
        </section>

        <section className="py-8 text-center lg:py-10">
          <p className="text-[0.8rem] font-extrabold uppercase tracking-[0.26em] text-brand-orchid drop-shadow-[0_8px_18px_rgba(109,40,217,0.12)]">
            Encontra.ai
          </p>
          <h2 className="mx-auto mt-3 max-w-5xl text-4xl font-bold tracking-[-0.055em] text-brand-graphite sm:text-5xl lg:text-[4.6rem] lg:leading-[0.96]">
            {copy.title}
          </h2>
          <p className="mx-auto mt-4 max-w-3xl text-base leading-7 text-brand-muted sm:text-lg">
            {copy.description}
          </p>

          <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/discovery" className="ea-button-primary inline-flex items-center justify-center px-5 py-3 text-sm font-bold">
              {copy.primaryAction}
            </Link>
            <Link href="/leads" className="ea-button-secondary inline-flex items-center justify-center px-5 py-3 text-sm font-bold">
              {copy.secondaryAction}
            </Link>
          </div>

          <div className="mx-auto mt-9 grid max-w-5xl gap-5 border-t border-brand-mist/70 pt-5 text-left sm:grid-cols-3">
            {copy.steps.map((step) => (
              <div key={step.title} className="relative pr-4">
                <p className="ea-kicker">{step.label}</p>
                <p className="mt-2 text-base font-bold text-brand-graphite">{step.title}</p>
                <p className="mt-1.5 max-w-[18rem] text-sm leading-6 text-brand-muted">{step.description}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

const homeCopy = {
  "pt-BR": {
    portugueseHint: "Fluxo guiado para buscas no Brasil.",
    englishHint: "Guided flow for Europe examples.",
    title: "O motor de IA que transforma mercados em listas de leads.",
    description:
      "Encontre empresas por nicho e localização, organize os melhores resultados, enriqueça contatos e exporte listas prontas para prospecção B2B.",
    primaryAction: "Começar o demo",
    secondaryAction: "Ver leads salvos",
    sourceTitle: "Ver código no GitHub",
    steps: [
      { label: "01", title: "Busque", description: "Comece com um nicho, cidade ou mercado que você quer prospectar." },
      { label: "02", title: "Estruture", description: "Visualize resultados, remova ruído e monte uma lista limpa de leads." },
      { label: "03", title: "Ative", description: "Enriqueça contatos, revise a lista e exporte leads prontos para abordagem." },
    ],
  },
  en: {
    portugueseHint: "Fluxo guiado para buscas no Brasil.",
    englishHint: "Guided flow for Europe examples.",
    title: "The AI engine that turns markets into lead lists.",
    description:
      "Find companies by niche and location, organize the best matches, enrich contacts, and export lists ready for B2B prospecting.",
    primaryAction: "Start demo",
    secondaryAction: "View saved leads",
    sourceTitle: "View source on GitHub",
    steps: [
      { label: "01", title: "Search", description: "Start with a niche, city, or market you want to sell into." },
      { label: "02", title: "Structure", description: "Preview matches, remove noise, and build a clean lead list." },
      { label: "03", title: "Activate", description: "Enrich contacts, review the list, and export leads ready for outreach." },
    ],
  },
} as const;
