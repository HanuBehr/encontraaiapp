import { ApiError } from "@/lib/api/client";

export const BACKEND_UNAVAILABLE_UI_MESSAGE =
  "Não foi possível conectar ao backend. Verifique se a API está rodando na porta 8000.";
export const MISSING_GOOGLE_API_KEY_DETAIL =
  "GOOGLE_API_KEY must be configured to use location-based discovery.";
export const MISSING_GOOGLE_API_KEY_UI_MESSAGE =
  "Configure GOOGLE_API_KEY no backend para usar a busca por localização.";
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
    if (isBackendUnavailableError(error)) {
      return BACKEND_UNAVAILABLE_UI_MESSAGE;
    }
    return sanitizeUserFacingMessage(error.detail, fallback);
  }

  if (error instanceof Error) {
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

function looksLikeBackendUnavailable(message: string) {
  return (
    /backend proxy request failed/i.test(message) ||
    /connection refused/i.test(message) ||
    /connection reset/i.test(message) ||
    /failed to fetch/i.test(message) ||
    /econn/i.test(message)
  );
}
