import type { NextRequest } from "next/server";

const apiBaseUrl =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://127.0.0.1:8000";
const apiBackendUrl = apiBaseUrl.replace(/\/$/, "");

const excludedRequestHeaders = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

const excludedResponseHeaders = new Set([
  "connection",
  "content-length",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

async function proxyBackend(request: NextRequest, context: RouteContext): Promise<Response> {
  const { path = [] } = await context.params;
  const targetUrl = new URL(path.join("/"), `${apiBackendUrl}/`);
  targetUrl.search = request.nextUrl.search;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!excludedRequestHeaders.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  headers.set("x-forwarded-host", request.headers.get("host") ?? "");
  headers.set("x-forwarded-proto", request.nextUrl.protocol.replace(":", ""));

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
    redirect: "manual",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const body = await request.arrayBuffer();
    if (body.byteLength > 0) {
      init.body = body;
    }
  }

  let upstreamResponse: Response;
  try {
    upstreamResponse = await fetch(targetUrl, init);
  } catch {
    return Response.json(
      {
        detail:
          "Backend proxy request failed. The backend may be unavailable or the dev proxy connection was reset. Retry shortly.",
      },
      { status: 502 },
    );
  }

  const responseHeaders = new Headers();
  upstreamResponse.headers.forEach((value, key) => {
    if (!excludedResponseHeaders.has(key.toLowerCase())) {
      responseHeaders.set(key, value);
    }
  });

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxyBackend;
export const POST = proxyBackend;
export const PUT = proxyBackend;
export const PATCH = proxyBackend;
export const DELETE = proxyBackend;
export const OPTIONS = proxyBackend;
