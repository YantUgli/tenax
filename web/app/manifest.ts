import type { MetadataRoute } from "next";

// Required under `output: "export"`, same as opengraph-image.tsx.
export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Tenax",
    short_name: "Tenax",
    description: "Self-managing persistent memory for AI agents.",
    start_url: "/",
    display: "standalone",
    theme_color: "#07090d",
    background_color: "#07090d",
    icons: [
      { src: "/app-icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/app-icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
