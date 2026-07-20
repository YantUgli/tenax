import type { Metadata } from "next";

import { DemoConsole } from "@/components/demo/DemoConsole";

export const metadata: Metadata = {
  title: "Live demo | Tenax",
  description:
    "Drive a running Tenax instance: recall under a token budget with the four retrieval signals broken out, watch belief revision fire on write, and run the forget and reflect sweeps.",
};

/**
 * The live console.
 *
 * Deliberately does not render <Nav />: the console ships its own header with the tab bar, and
 * Nav's links are #-anchors into the landing page's sections, which are not on this route.
 * The wordmark links back to /.
 */
export default function DemoPage() {
  return <DemoConsole />;
}
