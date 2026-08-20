/** @type {import('next').NextConfig} */
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy API + media to the FastAPI backend during development.
    return [
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      { source: "/media/:path*", destination: `${apiBase}/media/:path*` },
      { source: "/health", destination: `${apiBase}/health` },
    ];
  },
};

export default nextConfig;
