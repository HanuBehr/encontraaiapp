"use client";

import { useI18n } from "@/lib/i18n/client";
import { GlassSelect } from "@/components/ui/GlassSelect";
import { LOCALE_LABELS, LOCALES, type Locale } from "@/lib/i18n/translations";

export function SettingsWorkspace() {
  const { locale, setLocale, t } = useI18n();
  const emailHref = "mailto:hanu.behr@gmail.com?subject=Encontra.ai%20full%20workflow&body=Hi%20Hanu%2C%20I%27d%20like%20to%20see%20the%20full%20Encontra.ai%20workflow.";

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-1.5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="ea-kicker">{t("settings.kicker")}</p>
          <h1 className="mt-1 text-3xl font-bold tracking-[-0.045em] text-brand-graphite sm:text-[2.35rem]">
            {t("settings.title")}
          </h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-brand-muted">
            {t("settings.description")}
          </p>
        </div>
      </div>

      <div className="max-w-3xl space-y-5">
        <section className="ea-card p-5">
          <div>
            <p className="text-base font-semibold text-brand-graphite">{t("settings.languageTitle")}</p>
            <p className="mt-1 text-sm leading-6 text-brand-muted">{t("settings.languageDescription")}</p>
          </div>

          <div className="mt-5 block max-w-sm">
            <span className="text-xs font-medium text-brand-muted">{t("settings.languageLabel")}</span>
            <GlassSelect
              value={locale}
              options={LOCALES.map((option) => ({ value: option, label: LOCALE_LABELS[option] }))}
              ariaLabel={t("settings.languageLabel")}
              className="mt-1"
              onChange={(value) => setLocale(value as Locale)}
            />
          </div>

          <p className="mt-3 text-xs text-brand-muted">{t("settings.updated")}</p>
        </section>

        <EmailAccessCard
          kicker={t("settings.emailKicker")}
          title={t("settings.emailTitle")}
          description={t("settings.emailDescription")}
          href={emailHref}
          cta={t("settings.emailAction")}
          identityLabel={t("settings.emailIdentityLabel")}
          identityMeta={t("settings.emailIdentityMeta")}
        />
        <SourceAccessCard
          kicker={t("settings.githubKicker")}
          title={t("settings.githubTitle")}
          description={t("settings.githubDescription")}
          href="https://github.com/HanuBehr/encontraaiapp"
          cta={t("settings.githubAction")}
          stackKicker={t("settings.stackKicker")}
          stackTitle={t("settings.stackTitle")}
          signalTyped={t("settings.stackSignalTyped")}
          signalApi={t("settings.stackSignalApi")}
          signalDemo={t("settings.stackSignalDemo")}
          sourceMeta={t("settings.githubSourceMeta")}
          repositoryLabel={t("settings.sourceRepositoryLabel")}
          frontendLabel={t("settings.sourceFrontendLabel")}
          frontendValue={t("settings.sourceFrontendValue")}
          backendLabel={t("settings.sourceBackendLabel")}
          backendValue={t("settings.sourceBackendValue")}
          productLabel={t("settings.sourceProductLabel")}
          productValue={t("settings.sourceProductValue")}
        />
      </div>
    </div>
  );
}

function SourceAccessCard({
  kicker,
  title,
  description,
  href,
  cta,
  stackKicker,
  stackTitle,
  signalTyped,
  signalApi,
  signalDemo,
  sourceMeta,
  repositoryLabel,
  frontendLabel,
  frontendValue,
  backendLabel,
  backendValue,
  productLabel,
  productValue,
}: {
  kicker: string;
  title: string;
  description: string;
  href: string;
  cta: string;
  stackKicker: string;
  stackTitle: string;
  signalTyped: string;
  signalApi: string;
  signalDemo: string;
  sourceMeta: string;
  repositoryLabel: string;
  frontendLabel: string;
  frontendValue: string;
  backendLabel: string;
  backendValue: string;
  productLabel: string;
  productValue: string;
}) {
  const architectureRows = [
    { label: frontendLabel, value: frontendValue },
    { label: backendLabel, value: backendValue },
    { label: productLabel, value: productValue },
  ];

  return (
    <section className="relative overflow-hidden rounded-[1.35rem] border border-white/10 bg-[#17131f] p-5 text-white shadow-[0_18px_44px_rgba(23,19,31,0.18),inset_0_1px_0_rgba(255,255,255,0.06)]">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start">
        <div>
          <div>
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[0.9rem] border border-white/10 bg-white/[0.07] text-white/82 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                <GitHubIcon className="h-5 w-5" />
              </div>
              <p className="text-[0.68rem] font-bold uppercase tracking-[0.18em] text-violet-300">{kicker}</p>
            </div>
            <h3 className="mt-4 text-xl font-bold tracking-[-0.035em] text-white">{title}</h3>
          </div>

          <p className="mt-2 max-w-xl text-sm leading-6 text-white/[0.62]">{description}</p>

          <div className="mt-5 rounded-[1rem] border border-white/10 bg-white/[0.045] px-3.5 py-3">
            <p className="text-[0.66rem] font-bold uppercase tracking-[0.16em] text-white/[0.38]">{repositoryLabel}</p>
            <p className="mt-1 font-mono text-sm font-semibold text-white/[0.82]">HanuBehr/encontraaiapp</p>
          </div>

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center rounded-[0.85rem] border border-white/[0.14] bg-white/[0.075] px-4 py-2.5 text-sm font-bold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition hover:-translate-y-0.5 hover:bg-white/[0.11] motion-reduce:transition-none"
            >
              {cta}
            </a>
            <span className="font-mono text-[0.72rem] font-semibold text-white/[0.42]">{sourceMeta}</span>
          </div>
        </div>

        <div className="rounded-[1.1rem] border border-white/10 bg-white/[0.045] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <div>
            <p className="text-[0.66rem] font-bold uppercase tracking-[0.18em] text-white/[0.38]">{stackKicker}</p>
            <p className="mt-1 text-sm font-bold text-white">{stackTitle}</p>
          </div>
          <div className="mt-4 rounded-[0.9rem] border border-white/10 bg-black/10 px-3 py-2 font-mono text-[0.72rem] text-white/[0.68]">
            <span className="text-emerald-300">{signalTyped}</span>
            <span className="mx-2 text-white/[0.28]">/</span>
            {signalApi}
            <span className="mx-2 text-white/[0.28]">/</span>
            {signalDemo}
          </div>
          <div className="mt-4 divide-y divide-white/[0.08]">
            {architectureRows.map((row) => (
              <div key={row.label} className="grid gap-1 py-2 first:pt-0 last:pb-0 sm:grid-cols-[86px_minmax(0,1fr)]">
                <span className="text-[0.68rem] font-bold uppercase tracking-[0.14em] text-white/[0.38]">{row.label}</span>
                <span className="text-sm font-semibold leading-5 text-white/[0.76]">{row.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function EmailAccessCard({
  kicker,
  title,
  description,
  href,
  cta,
  identityLabel,
  identityMeta,
}: {
  kicker: string;
  title: string;
  description: string;
  href: string;
  cta: string;
  identityLabel: string;
  identityMeta: string;
}) {
  return (
    <section className="ea-card relative overflow-hidden p-5">
      <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-center">
        <div className="min-w-0">
          <p className="ea-kicker">{kicker}</p>
          <h3 className="mt-3 text-xl font-bold tracking-[-0.035em] text-brand-graphite">{title}</h3>
          <p className="mt-2 max-w-xl text-sm leading-6 text-brand-muted">{description}</p>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center">
            <a href={href} className="ea-button-primary inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-bold">
              <MailIcon className="h-4 w-4" />
              {cta}
            </a>
          </div>
        </div>

        <div className="rounded-[1.1rem] border border-brand-orchid/10 bg-white/[0.38] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.56)] backdrop-blur-xl">
          <p className="text-[0.68rem] font-bold uppercase tracking-[0.14em] text-brand-muted">{identityLabel}</p>
          <p className="mt-1 text-base font-bold text-brand-graphite">Hanu Behr</p>
          <p className="mt-1 text-xs font-semibold leading-5 text-brand-muted">{identityMeta}</p>
          <p className="mt-4 break-all text-sm font-bold text-brand-graphite">hanu.behr@gmail.com</p>
        </div>
      </div>
    </section>
  );
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="currentColor">
      <path d="M12 .5A11.5 11.5 0 0 0 8.36 22.9c.58.1.8-.25.8-.56v-2.03c-3.25.7-3.94-1.38-3.94-1.38-.53-1.34-1.3-1.7-1.3-1.7-1.06-.72.08-.7.08-.7 1.17.08 1.79 1.2 1.79 1.2 1.04 1.77 2.73 1.26 3.4.96.1-.75.4-1.26.73-1.55-2.6-.29-5.33-1.3-5.33-5.75 0-1.27.45-2.31 1.2-3.13-.12-.29-.52-1.48.11-3.09 0 0 .98-.31 3.19 1.2A11.1 11.1 0 0 1 12 5.98c.99 0 1.98.13 2.91.39 2.2-1.51 3.18-1.2 3.18-1.2.63 1.61.23 2.8.11 3.09.75.82 1.2 1.86 1.2 3.13 0 4.46-2.73 5.45-5.34 5.74.42.36.8 1.08.8 2.17v3.04c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

function MailIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="currentColor" d="M4.5 7.1A2.6 2.6 0 0 1 7.1 4.5h9.8a2.6 2.6 0 0 1 2.6 2.6v9.8a2.6 2.6 0 0 1-2.6 2.6H7.1a2.6 2.6 0 0 1-2.6-2.6V7.1Z" opacity="0.16" />
      <path fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" d="M5.5 7.5h13v9h-13z" />
      <path fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" d="m6.2 8.2 5.8 4.4 5.8-4.4" />
    </svg>
  );
}
