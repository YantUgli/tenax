"use client";

import { useEffect, useState } from "react";

import { TenaxMark } from "@/components/ui";

const NAV = [
  { id: "problem", label: "Problem" },
  { id: "how", label: "How it works" },
  { id: "demo", label: "Demo" },
  { id: "benchmark", label: "Benchmark" },
  { id: "integrations", label: "Works with" },
  { id: "mcp", label: "Install" },
];

// Module-level constant on purpose: a fresh array each render would re-run the
// observer effect on every render, tearing down and rebuilding the observer.
const SECTION_IDS = NAV.map((n) => n.id);

/**
 * Returns the id of the section currently under the reading line.
 *
 * The observer's rootMargin collapses the viewport to a band roughly 25%-40% from the top:
 * a section counts as active while it crosses that band. Using the very top of the viewport
 * would flip to the next section too early, and using the middle flips too late.
 *
 * Returns null while the hero is in view, so nothing is highlighted before the first
 * section is reached.
 */
function useActiveSection(ids: string[]): string | null {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (elements.length === 0) return;

    const visible = new Map<string, number>();

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            visible.set(entry.target.id, entry.intersectionRatio);
          } else {
            visible.delete(entry.target.id);
          }
        }
        // Document order wins ties, so scrolling never highlights a later section
        // while an earlier one still owns the band.
        const current = ids.find((id) => visible.has(id)) ?? null;

        setActive((prev) => {
          if (current) return current;
          // Nothing in the band. Above the first section that means the hero, so clear
          // the highlight. Past it — e.g. at the page bottom, where the last section has
          // scrolled above the band and only the footer is in view — keep the previous
          // one rather than blinking the whole nav off.
          const first = document.getElementById(ids[0]);
          const aboveFirst =
            !first || first.getBoundingClientRect().top > window.innerHeight * 0.4;
          return aboveFirst ? null : prev;
        });
      },
      { rootMargin: "-25% 0px -60% 0px", threshold: 0 },
    );

    elements.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [ids]);

  return active;
}

export function Nav() {
  const active = useActiveSection(SECTION_IDS);
  const activeLabel = NAV.find((n) => n.id === active)?.label;

  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur">
      <nav className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 py-3.5 sm:px-8">
        <a href="#top" className="flex items-baseline gap-2">
          {/* self-center opts the mark out of the baseline alignment the text spans want:
              a square sitting on the text baseline reads as if it has fallen. */}
          <TenaxMark className="size-4.5 self-center text-accent" />
          <span className="font-mono text-lg font-semibold tracking-tight">Tenax</span>
          {/* On small screens the link list is hidden, so the tagline slot doubles as a
              "you are here" indicator. */}
          <span className="font-mono text-[11px] text-muted md:hidden">
            {activeLabel ?? "memoria tenax"}
          </span>
          <span className="hidden font-mono text-[11px] text-muted md:inline">
            memoria tenax
          </span>
        </a>

        <ul className="hidden items-center gap-7 text-sm md:flex">
          {NAV.map((n) => {
            const isActive = n.id === active;
            return (
              <li key={n.id}>
                <a
                  href={`#${n.id}`}
                  aria-current={isActive ? "true" : undefined}
                  className={`relative py-1 transition-colors ${
                    isActive ? "text-foreground" : "text-muted hover:text-foreground"
                  }`}
                >
                  {n.label}
                  <span
                    className={`absolute -bottom-0.5 left-0 h-px w-full origin-left bg-accent transition-transform duration-300 ${
                      isActive ? "scale-x-100" : "scale-x-0"
                    }`}
                  />
                </a>
              </li>
            );
          })}
        </ul>

        <a
          href="https://github.com/YantUgli/tenax"
          className="rounded-lg border border-border px-3 py-1.5 font-mono text-xs text-muted transition-colors hover:border-accent/40 hover:text-foreground"
        >
          GitHub
        </a>
      </nav>
    </header>
  );
}
