import type { NextConfig } from "next";

// The app is always served through Caddy at http://localhost:8080, which routes /api and /ws
// to FastAPI, so no rewrites or CORS are needed here.
const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
