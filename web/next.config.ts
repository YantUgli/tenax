import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Not a static export any more: /demo proxies to the Tenax backend through
  // app/api/tenax, and a route handler needs a Node runtime.
  //
  // The guarantee that motivated the export still holds, though — the marketing page (/) is
  // prerendered from web/data at build time and calls nothing at runtime, so it renders with
  // no backend, no database and no Qwen key. Only /demo reaches out, and it falls back to
  // sample data when the backend is unreachable.
  images: { unoptimized: true },
};

export default nextConfig;
