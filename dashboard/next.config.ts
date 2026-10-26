import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // The API proxy: a page opened from another machine calls its own origin at
  // /api/v1 (lib/api-base.ts), and this forwards it to the API on loopback.
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
