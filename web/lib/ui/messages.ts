import { ApiError } from "@/lib/api/client";

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
): string {
  if (error instanceof ApiError) {
    if (error.detail === MISSING_GOOGLE_API_KEY_DETAIL) {
      return MISSING_GOOGLE_API_KEY_UI_MESSAGE;
    }
    if (error.detail === MISSING_CNPJA_API_KEY_DETAIL) {
      return MISSING_CNPJA_API_KEY_UI_MESSAGE;
    }
    if (isTimeoutLikeError(error)) {
      return LONG_RUNNING_OPERATION_TIMEOUT_UI_MESSAGE;
    }
    if (isBackendUnavailableError(error)) {
      return BACKEND_UNAVAILABLE_UI_MESSAGE;
    }
    return sanitizeUserFacingMessage(error.detail, fallback);
  }

  if (error instanceof Error) {
    if (isTimeoutLikeError(error)) {
      return LONG_RUNNING_OPERATION_TIMEOUT_UI_MESSAGE;
    }
    if (looksLikeBackendUnavailable(error.message)) {
      return BACKEND_UNAVAILABLE_UI_MESSAGE;
    }
    return sanitizeUserFacingMessage(error.message, fallback);
  }

  return fallback;
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
