"use client";

import { createContext, useContext, useEffect, useState } from "react";

import {
  DEFAULT_LOCALE,
  type Locale,
  type TranslationKey,
  interpolate,
  translations,
} from "@/lib/i18n/translations";
import { getActiveLocale, setActiveLocale } from "@/lib/i18n/locale-session";

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey, values?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    setLocaleState(getActiveLocale());
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  function setLocale(nextLocale: Locale) {
    setLocaleState(nextLocale);
    setActiveLocale(nextLocale);
  }

  function t(key: TranslationKey, values?: Record<string, string | number>) {
    return interpolate(translations[locale][key], values);
  }

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return context;
}
