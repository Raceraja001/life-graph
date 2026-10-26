import type { NextConfig } from "next";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1";

const nextConfig: NextConfig = {
  output: "standalone",
  // Keep "/api/v1/memories/" as sent. Next's default 308 to the slashless path
  // reached FastAPI's own redirect back, to http://localhost:8080/... — the
  // other machine's localhost — so lists failed off-box (2026-10-26).
  skipTrailingSlashRedirect: true,
  // The API proxy: a page opened from another machine calls its own origin at
  // /api/v1 (lib/api-base.ts), and this forwards it to the API on loopback,
  // with or without the trailing slash the route was declared with.
  async rewrites() {
    return [
      { source: "/api/v1/:path*/", destination: `${API}/:path*/` },
      { source: "/api/v1/:path*", destination: `${API}/:path*` },
    ];
  },
};

export default nextConfig;
