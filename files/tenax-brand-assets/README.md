# Tenax — Brand Assets

Logo concept: **Cascade** — a 2×2 grid of amber squares stepping down in opacity,
expressing *selective retention* (what is held vs. what fades). Amber `#f5b544` is the
only brand hue; designed dark-first on `#07090d`.

## Files

| File | Use |
|------|-----|
| `logo.svg` | Full lockup (amber mark + off-white "Tenax"). Primary, on dark. |
| `logo-light.svg` | Lockup with near-black wordmark, for light backgrounds. |
| `logo-mono-amber.svg` | Single-hue amber lockup (mark + wordmark). |
| `icon.svg` | Mark only, amber, transparent bg. |
| `icon-mono.svg` | Mark only, off-white (single-color contexts). |
| `wordmark.svg` | "Tenax" only, outlined Geist Mono SemiBold. |
| `tagline.svg` | "memoria tenax" secondary line, muted grey-blue. |
| `favicon.svg` | Mark with lifted opacities so all 4 squares read at 16px. |
| `favicon.ico` | Multi-res 16/32/48. |
| `favicon-16/32/48/64.png` | Individual raster favicons. |
| `app-icon-512/192.png` | Rounded dark tile + mark (PWA / store icons). |
| `apple-touch-icon.png` | 180px, for iOS home-screen. |

Note: favicons use slightly lifted opacities (0.7 / 0.52 / 0.36 vs the design's
0.6 / 0.38 / 0.2) so the faded squares don't disappear at 16px. The full-size
`logo.svg` / `icon.svg` keep the original design opacities.

## Next.js (App Router) integration

Drop favicons into `web/app/` and the rest into `web/public/`:

```
web/app/favicon.ico
web/app/icon.svg            → icon.svg
web/app/apple-icon.png      → apple-touch-icon.png
web/public/logo.svg
```

Next.js auto-serves `app/favicon.ico`, `app/icon.svg`, and `app/apple-icon.png`.
For the manifest, add `web/app/manifest.ts`:

```ts
import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Tenax",
    short_name: "Tenax",
    theme_color: "#07090d",
    background_color: "#07090d",
    icons: [
      { src: "/app-icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/app-icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
```

Use the wordmark in the Nav either as this outlined SVG or, since the site already
loads Geist Mono, as live text (`font-weight:600; letter-spacing:-0.04em`).
