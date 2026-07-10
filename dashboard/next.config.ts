import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Allow API proxy in development
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
