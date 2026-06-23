"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n/client";
import { isDemoMode } from "@/lib/demo/mode";
import { LOCALE_LABELS, LOCALES, type Locale } from "@/lib/i18n/translations";

export function DemoHome() {
  const { locale, setLocale } = useI18n();
  const demoMode = isDemoMode();
  const copy = homeCopy[locale];

  return (
    <div className="grid min-h-[calc(100vh-5rem)] gap-5 lg:grid-cols-[minmax(0,1fr)_430px] lg:items-stretch">
      <section className="ea-card relative overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-brand-orchid/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-[-120px] left-[-80px] h-72 w-72 rounded-full bg-brand-olive/20 blur-3xl" />

        <div className="relative max-w-3xl">
          <p className="ea-kicker">Encontra.ai</p>
          <h1 className="mt-4 max-w-2xl text-4xl font-bold tracking-[-0.055em] text-brand-graphite sm:text-5xl lg:text-6xl">
            {copy.title}
          </h1>
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

          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            {copy.steps.map((step) => (
              <div key={step.title} className="rounded-2xl border border-brand-mist/80 bg-white/60 p-4">
                <p className="text-sm font-bold text-brand-graphite">{step.title}</p>
                <p className="mt-2 text-sm leading-6 text-brand-muted">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <aside className="space-y-5">
        <section className="ea-card p-5">
          <p className="text-sm font-bold text-brand-graphite">{copy.languageTitle}</p>
          <p className="mt-2 text-sm leading-6 text-brand-muted">{copy.languageDescription}</p>
          <label className="mt-4 block">
            <span className="text-xs font-medium text-brand-muted">{copy.languageLabel}</span>
            <select
              value={locale}
              onChange={(event) => setLocale(event.target.value as Locale)}
              className="ea-input mt-1 w-full px-3 py-2 text-sm"
            >
              {LOCALES.map((option) => (
                <option key={option} value={option}>
                  {LOCALE_LABELS[option]}
                </option>
              ))}
            </select>
          </label>
        </section>

        <section className="ea-card p-5">
          <p className="text-sm font-bold text-brand-graphite">{demoMode ? copy.demoTitle : copy.fullTitle}</p>
          <p className="mt-2 text-sm leading-6 text-brand-muted">
            {demoMode ? copy.demoDescription : copy.fullDescription}
          </p>
        </section>

        <section className="ea-card p-5">
          <p className="text-sm font-bold text-brand-graphite">{copy.repoTitle}</p>
          <p className="mt-2 text-sm leading-6 text-brand-muted">{copy.repoDescription}</p>
          <a
            href="https://github.com/HanuBehr/encontraaiapp"
            target="_blank"
            rel="noreferrer"
            className="ea-button-secondary mt-4 inline-flex px-4 py-2 text-sm font-bold"
          >
            {copy.repoAction}
          </a>
        </section>
      </aside>
    </div>
  );
}

const homeCopy = {
  "pt-BR": {
    title: "Descubra, revise e organize leads B2B em um fluxo só.",
    description:
      "Explore um demo guiado com dados fictícios. Busque empresas, salve leads, revise contatos e exporte uma lista como se fosse uma operação real.",
    primaryAction: "Começar pela descoberta",
    secondaryAction: "Ver leads do demo",
    languageTitle: "Escolha o idioma",
    languageDescription: "A interface muda imediatamente e sua preferência fica salva neste navegador.",
    languageLabel: "Idioma da interface",
    demoTitle: "Demo seguro para recrutadores",
    demoDescription:
      "Esta versão roda sem backend e sem chaves de API. As buscas são guiadas e usam empresas fictícias para evitar custos, segredos e dados reais.",
    fullTitle: "Projeto completo",
    fullDescription: "Quando configurado com backend e chaves privadas, o projeto suporta buscas reais por provedores e persistência em banco.",
    repoTitle: "Código completo no GitHub",
    repoDescription:
      "O repositório inclui o frontend, backend FastAPI, modelos, serviços de descoberta, enriquecimento, CNPJ, exportação e documentação de deploy.",
    repoAction: "Abrir repositório",
    steps: [
      { title: "1. Busque", description: "Use uma busca guiada em português ou inglês para gerar uma prévia coerente." },
      { title: "2. Salve", description: "Selecione empresas, simule importação e veja os leads aparecerem no workspace." },
      { title: "3. Exporte", description: "Filtre, revise e baixe uma planilha local gerada pelo demo." },
    ],
  },
  en: {
    title: "Discover, review, and organize B2B leads in one workflow.",
    description:
      "Explore a guided demo with fictional data. Search companies, save leads, review contacts, and export a list like a real lead operation.",
    primaryAction: "Start with discovery",
    secondaryAction: "View demo leads",
    languageTitle: "Choose language",
    languageDescription: "The interface updates immediately and your preference is saved in this browser.",
    languageLabel: "Interface language",
    demoTitle: "Recruiter-safe demo",
    demoDescription:
      "This version runs without a backend or API keys. Searches are guided and use fictional companies to avoid costs, secrets, and real provider data.",
    fullTitle: "Full project",
    fullDescription: "When configured with backend hosting and private keys, the project supports real provider searches and database persistence.",
    repoTitle: "Full code on GitHub",
    repoDescription:
      "The repository includes the frontend, FastAPI backend, models, discovery services, enrichment, CNPJ workflows, export pipeline, and deployment docs.",
    repoAction: "Open repository",
    steps: [
      { title: "1. Search", description: "Use a guided English or Portuguese query to generate coherent preview results." },
      { title: "2. Save", description: "Select companies, simulate import, and see leads appear in the workspace." },
      { title: "3. Export", description: "Filter, review, and download a local spreadsheet generated by the demo." },
    ],
  },
} as const;
