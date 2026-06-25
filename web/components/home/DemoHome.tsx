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

export function DemoHome() {
  const { locale, setLocale } = useI18n();
  const copy = homeCopy[locale];

  return (
    <div className="relative min-h-[calc(100vh-4rem)] py-1">
      <div className="pointer-events-none absolute left-[-12rem] top-10 h-[28rem] w-[28rem] rounded-full bg-brand-orchid/10 blur-3xl" />
      <div className="pointer-events-none absolute right-[-10rem] top-0 h-[24rem] w-[24rem] rounded-full bg-brand-olive/18 blur-3xl" />

      <div className="relative mx-auto max-w-6xl">
        <section className="flex justify-end py-1">
          <div className="inline-flex self-start rounded-full bg-white/55 p-1 shadow-[0_14px_34px_rgba(47,38,61,0.08)] backdrop-blur-xl sm:self-auto">
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
                      ? "bg-brand-orchid text-white shadow-[0_10px_24px_rgba(109,40,217,0.24)]"
                      : "text-brand-muted hover:bg-white hover:text-brand-graphite"
                  }`}
                >
                  <FlagIcon locale={option} />
                  <span>{option === "pt-BR" ? "Português" : "English"}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="py-8 text-center lg:py-10">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-brand-orchid">Encontra.ai</p>
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
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-brand-orchid/70">{step.label}</p>
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
    title: "Uma central simples para descobrir e organizar leads B2B.",
    description:
      "Teste um fluxo completo com dados fictícios: encontre empresas por nicho e cidade, salve as melhores opções, revise contatos e exporte uma planilha.",
    primaryAction: "Começar o demo",
    secondaryAction: "Ver leads salvos",
    steps: [
      { label: "01", title: "Busque", description: "Escolha uma busca sugerida para ver empresas coerentes com o nicho e a cidade." },
      { label: "02", title: "Salve", description: "Selecione empresas relevantes e envie para a área de leads." },
      { label: "03", title: "Exporte", description: "Filtre, revise e baixe uma planilha local gerada pelo demo." },
    ],
  },
  en: {
    portugueseHint: "Fluxo guiado para buscas no Brasil.",
    englishHint: "Guided flow for Europe examples.",
    title: "A simple workspace to find and organize B2B leads.",
    description:
      "Try the complete flow with fictional data: find companies by niche and city, save the best matches, review contacts, and export a spreadsheet.",
    primaryAction: "Start demo",
    secondaryAction: "View saved leads",
    steps: [
      { label: "01", title: "Search", description: "Pick a suggested search to see coherent companies for the niche and city." },
      { label: "02", title: "Save", description: "Select relevant companies and move them into the leads workspace." },
      { label: "03", title: "Export", description: "Filter, review, and download a local spreadsheet generated by the demo." },
    ],
  },
} as const;
