"use client";

import { useI18n } from "@/lib/i18n/client";
import { LOCALE_LABELS, LOCALES, type Locale } from "@/lib/i18n/translations";

export function SettingsWorkspace() {
  const { locale, setLocale, t } = useI18n();

  return (
    <div className="space-y-5">
      <div className="ea-card p-5">
        <p className="ea-kicker">{t("settings.kicker")}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-brand-graphite">
          {t("settings.title")}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-brand-muted">
          {t("settings.description")}
        </p>
      </div>

      <section className="ea-card max-w-2xl p-5">
        <div>
          <p className="text-base font-semibold text-brand-graphite">{t("settings.languageTitle")}</p>
          <p className="mt-1 text-sm leading-6 text-brand-muted">{t("settings.languageDescription")}</p>
        </div>

        <label className="mt-5 block max-w-sm">
          <span className="text-xs font-medium text-brand-muted">{t("settings.languageLabel")}</span>
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

        <p className="mt-3 text-xs text-brand-muted">{t("settings.updated")}</p>
      </section>
    </div>
  );
}
