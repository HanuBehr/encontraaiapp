import { ApiError } from "@/lib/api/client";
import { translateLooseText } from "@/lib/i18n/loose";
import type { Locale } from "@/lib/i18n/translations";
import { translations } from "@/lib/i18n/translations";

export const BACKEND_UNAVAILABLE_UI_MESSAGE =
  "Não foi possível conectar ao backend. Verifique se a API está rodando na porta 8000.";
export const LONG_RUNNING_OPERATION_TIMEOUT_UI_MESSAGE =
  "A operação demorou mais que o esperado. Tente novamente com menos empresas por vez.";
export const MISSING_GOOGLE_API_KEY_DETAIL =
  "GOOGLE_API_KEY must be configured to use location-based discovery.";
export const MISSING_GOOGLE_API_KEY_UI_MESSAGE =
  "Configure GOOGLE_API_KEY no backend para usar a busca por localização.";
export const MISSING_CNPJA_API_KEY_DETAIL =
  "CNPJA_API_KEY must be configured to use batch CNPJ enrichment.";
export const MISSING_CNPJA_API_KEY_UI_MESSAGE =
  "Configure CNPJA_API_KEY no backend para usar enriquecimento CNPJ em lote.";
export const CNPJ_WEBSITE_BATCH_LIMIT_DETAIL =
  "Website-based CNPJ enrichment works better in smaller batches. Select fewer leads and retry.";
export const CNPJ_WEBSITE_BATCH_LIMIT_UI_MESSAGE =
  "A consulta CNPJ por site roda melhor em lotes menores. Selecione menos empresas por vez.";
export const NO_DISCOVERY_RESULTS_UI_MESSAGE =
  "Nenhuma empresa encontrada para essa busca. Tente outro nicho, cidade ou raio.";

const TECHNICAL_ERROR_PATTERNS = [
  /traceback/i,
  /httpconnectionpool/i,
  /requests\./i,
  /sqlalchemy/i,
  /stack/i,
  /<!doctype/i,
  /<html/i,
  /econn/i,
  /enotfound/i,
  /failed to fetch/i,
  /connection reset/i,
];

export function formatUserFacingError(
  error: unknown,
  fallback = "Não foi possível concluir a ação.",
  locale: Locale = "pt-BR",
): string {
  const fallbackMessage = translateFallback(fallback, locale);
  if (error instanceof ApiError) {
    if (error.detail === MISSING_GOOGLE_API_KEY_DETAIL) {
      return translations[locale]["error.missingGoogleKey"];
    }
    if (error.detail === MISSING_CNPJA_API_KEY_DETAIL) {
      return translations[locale]["error.missingCnpjaKey"];
    }
    if (error.detail === CNPJ_WEBSITE_BATCH_LIMIT_DETAIL) {
      return translations[locale]["error.cnpjWebsiteBatchLimit"];
    }
    if (isTimeoutLikeError(error)) {
      return translations[locale]["error.longRunning"];
    }
    if (isBackendUnavailableError(error)) {
      return translations[locale]["error.backendUnavailable"];
    }
    return translateLooseText(sanitizeUserFacingMessage(error.detail, fallbackMessage), locale);
  }

  if (error instanceof Error) {
    if (isTimeoutLikeError(error)) {
      return translations[locale]["error.longRunning"];
    }
    if (looksLikeBackendUnavailable(error.message)) {
      return translations[locale]["error.backendUnavailable"];
    }
    return translateLooseText(sanitizeUserFacingMessage(error.message, fallbackMessage), locale);
  }

  return fallbackMessage;
}

export function sanitizeUserFacingMessage(
  message: string | null | undefined,
  fallback: string,
): string {
  const trimmed = message?.trim();
  if (!trimmed) {
    return fallback;
  }
  if (trimmed.length > 280) {
    return fallback;
  }
  if (TECHNICAL_ERROR_PATTERNS.some((pattern) => pattern.test(trimmed))) {
    return fallback;
  }
  return trimmed;
}

function isBackendUnavailableError(error: ApiError) {
  return error.status === 502 || looksLikeBackendUnavailable(error.detail ?? "");
}

function isTimeoutLikeError(error: ApiError | Error) {
  const detail = error instanceof ApiError ? error.detail ?? error.body : error.message;
  return (
    (error instanceof ApiError && error.status === 504) ||
    /timed out|timeout|demorou|smaller enrichment batch/i.test(detail)
  );
}

function looksLikeBackendUnavailable(message: string) {
  return (
    /backend proxy request failed/i.test(message) ||
    /connection refused/i.test(message) ||
    /connection reset/i.test(message) ||
    /failed to fetch/i.test(message) ||
    /econn/i.test(message)
  );
}

function translateFallback(fallback: string, locale: Locale) {
  if (locale === "pt-BR") {
    return fallback;
  }
  switch (fallback) {
    case "Não foi possível concluir a ação.":
      return translations.en["error.genericAction"];
    case "Não foi possível carregar os filtros agora.":
      return "Could not load filters right now.";
    case "Não foi possível carregar os leads agora.":
      return "Could not load leads right now.";
    case "Tente novamente em instantes.":
      return "Try again in a moment.";
    case "Não foi possível concluir a busca.":
      return "Could not complete the search.";
    case "Não foi possível concluir a ação em lote.":
      return "Could not complete the batch action.";
    default:
      return fallback;
  }
}
