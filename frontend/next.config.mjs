/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    // Locally the backend runs on :8000. On Vercel (VERCEL=1 during the build) the backend shares the site's
    // domain under /api (see vercel.json), so nothing needs setting. NEXT_PUBLIC_API_URL overrides both.
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || (process.env.VERCEL ? "/api" : "http://localhost:8000"),
  },
};
export default nextConfig;
