/**
 * Source for `app/opengraph-image.png` — NOT a live route.
 *
 * Next can generate this card at build time, but under `output: "export"` it emits the
 * result as an extensionless file (`out/opengraph-image`). Static hosts then serve it as
 * application/octet-stream, and social scrapers reject an og:image that isn't image/*.
 * So the card is generated once and committed as a static metadata file instead, which
 * exports as a real `.png` and needs no build machinery.
 *
 * To regenerate after editing this file:
 *   cp scripts/opengraph-image.source.tsx app/opengraph-image.tsx
 *   npm run build
 *   cp out/opengraph-image app/opengraph-image.png
 *   rm app/opengraph-image.tsx && npm run build
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ImageResponse } from "next/og";

export const dynamic = "force-static";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tenax | Self-Managing AI Memory";

/**
 * The wordmark and tagline ship as outlined paths, so embedding them as data URIs renders
 * the brand type exactly without handing ImageResponse a font file — which would otherwise
 * mean fetching Geist Mono at build time, and this build must not need the network.
 */
function svgDataUri(file: string): string {
  const svg = readFileSync(join(process.cwd(), "public", file), "utf8");
  return `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;
}

// The mark's four opacities, in reading order: held → fading.
const CASCADE = [1, 0.6, 0.38, 0.2];

export default function Image() {
  const wordmark = svgDataUri("wordmark.svg");
  const tagline = svgDataUri("tagline.svg");

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          background: "#07090d",
          // Echoes the amber wash the site puts behind its hero.
          backgroundImage:
            "radial-gradient(ellipse 70% 55% at 50% -5%, rgba(245,181,68,0.14), transparent)",
          padding: "0 90px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 34 }}>
          <div style={{ display: "flex", flexWrap: "wrap", width: 132, height: 132 }}>
            {CASCADE.map((opacity, i) => (
              <div
                key={i}
                style={{
                  width: 60,
                  height: 60,
                  margin: 3,
                  borderRadius: 4,
                  background: "#f5b544",
                  opacity,
                }}
              />
            ))}
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={wordmark} width={370} height={103} alt="Tenax" />
        </div>

        <div
          style={{
            display: "flex",
            fontSize: 44,
            lineHeight: 1.3,
            color: "#e7ecf3",
            marginTop: 56,
            maxWidth: 940,
          }}
        >
          Persistent memory for AI agents, that manages itself.
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 22, marginTop: 44 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={tagline} width={232} height={23} alt="memoria tenax" />
          <div style={{ display: "flex", width: 1, height: 26, background: "#1f2733" }} />
          <div style={{ display: "flex", fontSize: 24, color: "#8b97a8" }}>
            MCP server · built on Qwen Cloud
          </div>
        </div>
      </div>
    ),
    size,
  );
}
