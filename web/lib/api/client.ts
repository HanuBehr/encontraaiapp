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
