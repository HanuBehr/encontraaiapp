"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n/client";
import { isDemoMode } from "@/lib/demo/mode";
import { LOCALES, type Locale } from "@/lib/i18n/translations";

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="currentColor">
      <path d="M12 .5A11.5 11.5 0 0 0 8.37 22.9c.58.11.79-.25.79-.56v-2.18c-3.23.7-3.91-1.38-3.91-1.38-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.17.08 1.78 1.2 1.78 1.2 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.58-.29-5.29-1.29-5.29-5.74 0-1.27.45-2.31 1.2-3.12-.12-.29-.52-1.48.11-3.08 0 0 .98-.31 3.17 1.19A10.9 10.9 0 0 1 12 5.86c.98 0 1.96.13 2.89.39 2.2-1.5 3.17-1.19 3.17-1.19.63 1.6.23 2.79.11 3.08.75.81 1.2 1.85 1.2 3.12 0 4.46-2.72 5.44-5.3 5.73.42.36.79 1.07.79 2.16v3.19c0 .31.21.68.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

export function DemoHome() {
  const { locale, setLocale } = useI18n();
  const demoMode = isDemoMode();
  const copy = homeCopy[locale];

  return (
    <div className="space-y-5">
      <section className="ea-card relative overflow-hidden px-4 py-3 sm:px-5">
        <div className="pointer-events-none absolute -right-20 -top-24 h-44 w-44 rounded-full bg-brand-olive/20 blur-3xl" />
        <div className="relative flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-brand-orchid/70">{copy.languageEyebrow}</p>
            <h1 className="mt-1 text-lg font-bold tracking-[-0.03em] text-brand-graphite sm:text-xl">
              {copy.languageTitle}
            </h1>
            <p className="mt-1 text-xs leading-5 text-brand-muted sm:text-sm">{copy.languageDescription}</p>
          </div>

          <div className="inline-flex rounded-full border border-brand-mist/80 bg-white/70 p-1 shadow-[0_14px_34px_rgba(47,38,61,0.08)] backdrop-blur-xl">
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
                  <span className="text-lg leading-none" aria-hidden="true">{option === "pt-BR" ? "🇧🇷" : "🇬🇧"}</span>
                  <span>{option === "pt-BR" ? "Português" : "English"}</span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="ea-card relative overflow-hidden p-6 sm:p-8 lg:p-10">
          <div className="pointer-events-none absolute -right-28 -top-28 h-80 w-80 rounded-full bg-brand-orchid/10 blur-3xl" />
          <div className="pointer-events-none absolute bottom-[-140px] left-[-90px] h-80 w-80 rounded-full bg-brand-olive/20 blur-3xl" />

          <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1fr)_310px] lg:items-center">
            <div>
              <p className="ea-kicker">Encontra.ai</p>
              <h2 className="mt-4 max-w-3xl text-4xl font-bold tracking-[-0.055em] text-brand-graphite sm:text-5xl lg:text-6xl">
                {copy.title}
              </h2>
              <p className="mt-5 max-w-2xl text-base leading-7 text-brand-muted sm:text-lg">
                {copy.description}
              </p>

              <div className="mt-7 flex flex-col gap-3 sm:flex-row">
                <Link href="/discovery" className="ea-button-primary inline-flex items-center justify-center px-5 py-3 text-sm font-bold">
                  {copy.primaryAction}
                </Link>
                <Link href="/leads" className="ea-button-secondary inline-flex items-center justify-center px-5 py-3 text-sm font-bold">
                  {copy.secondaryAction}
                </Link>
              </div>
            </div>

            <div className="rounded-[2rem] border border-white/70 bg-white/65 p-4 shadow-panel backdrop-blur-xl">
              <div className="rounded-[1.5rem] bg-[#2F263D] p-4 text-white shadow-[0_24px_60px_rgba(47,38,61,0.22)]">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-white/55">{copy.previewLabel}</p>
                  <span className="rounded-full bg-emerald-300/18 px-2 py-1 text-[11px] font-bold text-emerald-100">{copy.previewStatus}</span>
                </div>
                <div className="mt-5 space-y-3">
                  {copy.previewRows.map((row) => (
                    <div key={row.name} className="rounded-2xl bg-white/[0.08] p-3 ring-1 ring-white/[0.08]">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold">{row.name}</p>
                          <p className="mt-1 text-xs text-white/58">{row.meta}</p>
                        </div>
                        <span className="rounded-full bg-white/12 px-2 py-1 text-xs font-bold">{row.score}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="relative mt-8 grid gap-3 sm:grid-cols-3">
            {copy.steps.map((step) => (
              <div key={step.title} className="rounded-3xl border border-brand-mist/80 bg-white/65 p-4 shadow-[0_18px_40px_rgba(47,38,61,0.06)]">
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-brand-orchid/70">{step.label}</p>
                <p className="mt-2 text-base font-bold text-brand-graphite">{step.title}</p>
                <p className="mt-2 text-sm leading-6 text-brand-muted">{step.description}</p>
              </div>
            ))}
          </div>
        </section>

        <aside className="space-y-5">
          <section className="ea-card overflow-hidden p-0">
            <div className="bg-[#201A2A] p-5 text-white">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-[#201A2A]">
                  <GitHubIcon className="h-7 w-7" />
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.22em] text-white/55">GitHub</p>
                  <h3 className="text-lg font-bold">{copy.repoTitle}</h3>
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-white/72">{copy.repoDescription}</p>
            </div>
            <div className="space-y-4 p-5">
              <div className="flex flex-wrap gap-2">
                {copy.repoTags.map((tag) => (
                  <span key={tag} className="rounded-full border border-brand-mist/80 bg-white/70 px-3 py-1 text-xs font-bold text-brand-graphite">
                    {tag}
                  </span>
                ))}
              </div>
              <a
                href="https://github.com/HanuBehr/encontraaiapp"
                target="_blank"
                rel="noreferrer"
                className="ea-button-secondary inline-flex w-full items-center justify-center gap-2 px-4 py-3 text-sm font-bold"
              >
                <GitHubIcon className="h-4 w-4" />
                {copy.repoAction}
              </a>
            </div>
          </section>

          <section className="ea-card p-5">
            <p className="text-sm font-bold text-brand-graphite">{demoMode ? copy.demoTitle : copy.fullTitle}</p>
            <p className="mt-2 text-sm leading-6 text-brand-muted">
              {demoMode ? copy.demoDescription : copy.fullDescription}
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}

const homeCopy = {
  "pt-BR": {
    languageEyebrow: "Primeiro passo",
    languageTitle: "Escolha como quer usar a interface",
    languageDescription: "A página muda na hora e sua escolha fica salva neste navegador.",
    portugueseHint: "Fluxo guiado para buscas no Brasil.",
    englishHint: "Guided flow for Europe examples.",
    title: "Uma central simples para descobrir e organizar leads B2B.",
    description:
      "Teste um fluxo completo com dados fictícios: encontre empresas por nicho e cidade, salve as melhores opções, revise contatos e exporte uma planilha.",
    primaryAction: "Começar o demo",
    secondaryAction: "Ver leads salvos",
    demoTitle: "Demo sem backend e sem chaves",
    demoDescription:
      "Esta versão roda só no navegador. As buscas são guiadas e usam empresas fictícias, então você pode explorar sem custo, segredos ou dados reais.",
    fullTitle: "Projeto completo",
    fullDescription: "Quando configurado com backend e chaves privadas, o projeto suporta buscas reais por provedores e persistência em banco.",
    repoTitle: "Código completo",
    repoDescription:
      "Repositório full-stack com frontend Next.js, backend FastAPI, serviços de descoberta, enriquecimento, CNPJ, exportação e documentação de deploy.",
    repoAction: "Abrir no GitHub",
    repoTags: ["Next.js", "FastAPI", "Demo mode", "Deploy docs"],
    previewLabel: "Prévia do workspace",
    previewStatus: "Demo ativo",
    previewRows: [
      { name: "Aurora Dental Studio", meta: "São Paulo • site + WhatsApp", score: "88" },
      { name: "Bistrô Jardim Campinas", meta: "Campinas • email + Instagram", score: "83" },
      { name: "Construminas Savassi", meta: "Belo Horizonte • CNPJ revisado", score: "82" },
    ],
    steps: [
      { label: "01", title: "Busque", description: "Escolha uma busca sugerida para ver empresas coerentes com o nicho e a cidade." },
      { label: "02", title: "Salve", description: "Selecione empresas relevantes e envie para a área de leads." },
      { label: "03", title: "Exporte", description: "Filtre, revise e baixe uma planilha local gerada pelo demo." },
    ],
  },
  en: {
    languageEyebrow: "First step",
    languageTitle: "Choose how you want to use the interface",
    languageDescription: "The page updates immediately and your choice is saved in this browser.",
    portugueseHint: "Fluxo guiado para buscas no Brasil.",
    englishHint: "Guided flow for Europe examples.",
    title: "A simple workspace to find and organize B2B leads.",
    description:
      "Try the complete flow with fictional data: find companies by niche and city, save the best matches, review contacts, and export a spreadsheet.",
    primaryAction: "Start demo",
    secondaryAction: "View saved leads",
    demoTitle: "No backend or keys needed",
    demoDescription:
      "This version runs fully in the browser. Searches are guided and use fictional companies, so you can explore without costs, secrets, or real provider data.",
    fullTitle: "Full project",
    fullDescription: "When configured with backend hosting and private keys, the project supports real provider searches and database persistence.",
    repoTitle: "Full source code",
    repoDescription:
      "Full-stack repository with the Next.js frontend, FastAPI backend, discovery services, enrichment, CNPJ workflows, export pipeline, and deployment docs.",
    repoAction: "Open on GitHub",
    repoTags: ["Next.js", "FastAPI", "Demo mode", "Deploy docs"],
    previewLabel: "Workspace preview",
    previewStatus: "Demo active",
    previewRows: [
      { name: "Alfama Dental Care", meta: "Lisbon • website + email", score: "87" },
      { name: "Rambla Table", meta: "Barcelona • reservations + Instagram", score: "84" },
      { name: "Spree Solar Technik", meta: "Berlin • phone + email", score: "83" },
    ],
    steps: [
      { label: "01", title: "Search", description: "Pick a suggested search to see coherent companies for the niche and city." },
      { label: "02", title: "Save", description: "Select relevant companies and move them into the leads workspace." },
      { label: "03", title: "Export", description: "Filter, review, and download a local spreadsheet generated by the demo." },
    ],
  },
} as const;
