import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Social cards need absolute URLs. The deploy host isn't fixed yet, so it comes from the
  // build environment; set NEXT_PUBLIC_SITE_URL when deploying or cards will point at the
  // placeholder below. opengraph-image.tsx is picked up automatically — no images entry.
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "https://tenax.example.com",
  ),
  title: "Tenax | Self-Managing AI Memory",
  description:
    "An MCP server that gives any compatible agent long-term memory: hybrid retrieval inside a token budget, belief revision, and a forgetting curve. Built on Qwen Cloud.",
  openGraph: {
    title: "Tenax | Self-Managing AI Memory",
    description:
      "Hybrid retrieval, belief revision, and a forgetting curve, exposed as five MCP tools. 100% retrieval hit rate on LongMemEval.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
