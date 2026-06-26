"use client";

import type { ReactNode } from "react";

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

        <AccessPanel
          icon={<GitHubIcon className="h-5 w-5" />}
          tone="dark"
          kicker={t("settings.githubKicker")}
          title={t("settings.githubTitle")}
          description={t("settings.githubDescription")}
          href="https://github.com/HanuBehr/encontraaiapp"
          cta={t("settings.githubAction")}
          variant="secondary"
        />
        <AccessPanel
          icon={<MailIcon className="h-5 w-5" />}
          tone="purple"
          kicker={t("settings.emailKicker")}
          title={t("settings.emailTitle")}
          description={t("settings.emailDescription")}
          href={emailHref}
          cta={t("settings.emailAction")}
          meta="hanu.behr@gmail.com"
          variant="primary"
        />
      </div>
    </div>
  );
}

function AccessPanel({
  icon,
  tone,
  kicker,
  title,
  description,
  href,
  cta,
  meta,
  variant,
}: {
  icon: ReactNode;
  tone: "dark" | "purple";
  kicker: string;
  title: string;
  description: string;
  href: string;
  cta: string;
  meta?: string;
  variant: "primary" | "secondary";
}) {
  const iconClassName =
    tone === "dark"
      ? "border-brand-graphite/10 bg-brand-graphite text-white"
      : "border-brand-orchid/14 bg-brand-orchid/[0.08] text-brand-orchid";

  return (
    <section className="ea-card p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 gap-4">
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border shadow-[inset_0_1px_0_rgba(255,255,255,0.24)] ${iconClassName}`}>
            {icon}
          </div>
          <div className="min-w-0">
            <p className="ea-kicker">{kicker}</p>
            <h3 className="mt-2 text-lg font-bold tracking-[-0.025em] text-brand-graphite">{title}</h3>
            <p className="mt-2 max-w-xl text-sm leading-6 text-brand-muted">{description}</p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:items-end">
          <a
            href={href}
            target={href.startsWith("http") ? "_blank" : undefined}
            rel={href.startsWith("http") ? "noreferrer" : undefined}
            className={`${variant === "primary" ? "ea-button-primary" : "ea-button-secondary"} inline-flex items-center justify-center px-4 py-2 text-sm font-bold`}
          >
            {cta}
          </a>
          {meta ? <span className="text-xs font-medium text-brand-muted">{meta}</span> : null}
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
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" />
      <path d="m5 8 7 5 7-5" />
    </svg>
  );
}
