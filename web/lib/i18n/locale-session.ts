import { DEFAULT_LOCALE, isLocale, type Locale } from "@/lib/i18n/translations";

const SESSION_LOCALE_KEY = "encontraai.session.locale.v1";

let activeLocale: Locale = DEFAULT_LOCALE;

export function getActiveLocale() {
  if (typeof window === "undefined") {
    return activeLocale;
  }
  const storedLocale = window.sessionStorage.getItem(SESSION_LOCALE_KEY);
  if (isLocale(storedLocale)) {
    activeLocale = storedLocale;
  }
  return activeLocale;
}

export function setActiveLocale(locale: Locale) {
  activeLocale = locale;
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem(SESSION_LOCALE_KEY, locale);
  }
}
