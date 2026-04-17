import type { NextConfig } from "next";

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.API_BASE_URL ??
  "http://127.0.0.1:8010";
const apiBackendUrl = apiBaseUrl.replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiBackendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
