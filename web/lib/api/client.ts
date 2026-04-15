const apiBasePath = process.env.NEXT_PUBLIC_API_BASE_PATH ?? "/api/backend";

type QueryValue = string | number | boolean | null | undefined;
type QueryParams = Record<string, QueryValue>;

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(message: string, status: number, body: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export async function getJson<T>(path: string, params: QueryParams = {}): Promise<T> {
  const response = await fetch(buildUrl(path, params), {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(`Request failed with ${response.status}`, response.status, body);
  }

  return response.json() as Promise<T>;
}

export async function postJson<TResponse, TBody extends object>(path: string, body: TBody): Promise<TResponse> {
  const response = await fetch(buildUrl(path, {}), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const responseBody = await response.text();
    throw new ApiError(`Request failed with ${response.status}`, response.status, responseBody);
  }

  return response.json() as Promise<TResponse>;
}

export async function postBlob<TBody extends object>(
  path: string,
  body: TBody,
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(buildUrl(path, {}), {
    method: "POST",
    headers: {
      Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const responseBody = await response.text();
    throw new ApiError(`Request failed with ${response.status}`, response.status, responseBody);
  }

  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get("content-disposition")) ?? "lead_export.xlsx",
  };
}

function buildUrl(path: string, params: QueryParams): string {
  const origin = typeof window === "undefined" ? "http://localhost" : window.location.origin;
  const base = apiBasePath.replace(/\/$/, "");
  const pathname = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${base}${pathname}`, origin);

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });

  return url.toString();
}

function filenameFromDisposition(disposition: string | null): string | null {
  if (!disposition) {
    return null;
  }
  const match = /filename="?([^"]+)"?/i.exec(disposition);
  return match?.[1] ?? null;
}
