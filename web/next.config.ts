import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Fully static: the site must render with no Tenax backend running. Every number and
  // every demo step is baked in from web/data at build time.
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
