import type { ReactNode } from "react";

/**
 * The Tenax mark ("Cascade"): a 2x2 grid stepping down in opacity — what is held vs. what
 * fades. Inlined rather than an <img> to public/logo.svg so it inherits currentColor and
 * costs no extra request; the opacities match brand/icon.svg exactly.
 *
 * The favicon deliberately uses lifted opacities (0.7/0.52/0.36) so the faded squares
 * survive 16px. Those do not belong here — at nav size the design values read fine.
 */
export function TenaxMark({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      fill="currentColor"
      aria-hidden
      className={`shrink-0 ${className}`}
    >
      <rect x="6" y="6" width="42" height="42" rx="2.5" />
      <rect x="52" y="6" width="42" height="42" rx="2.5" opacity="0.6" />
      <rect x="6" y="52" width="42" height="42" rx="2.5" opacity="0.38" />
      <rect x="52" y="52" width="42" height="42" rx="2.5" opacity="0.2" />
    </svg>
  );
}

export function Section({
  id,
  eyebrow,
  title,
  lede,
  children,
}: {
  id: string;
  eyebrow?: string;
  title: string;
  lede?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-border py-20 sm:py-28">
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
        <header className="max-w-3xl">
          {eyebrow ? (
            <p className="mb-3 font-mono text-xs uppercase tracking-[0.2em] text-accent">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            {title}
          </h2>
          {lede ? (
            <p className="mt-4 text-pretty text-base leading-relaxed text-muted sm:text-lg">
              {lede}
            </p>
          ) : null}
        </header>
        <div className="mt-12">{children}</div>
      </div>
    </section>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border bg-surface p-6 shadow-[0_1px_0_rgba(255,255,255,0.03)_inset] ${className}`}
    >
      {children}
    </div>
  );
}

export function Stat({
  value,
  label,
  sub,
  tone = "accent",
}: {
  value: string;
  label: string;
  sub?: string;
  tone?: "accent" | "good" | "plain";
}) {
  const color =
    tone === "good" ? "text-good" : tone === "plain" ? "text-foreground" : "text-accent";
  return (
    <div className="rounded-xl border border-border bg-surface px-5 py-6">
      {/* nowrap + a smaller step: values like "42% → 64%" must never break across lines,
          which strands the arrow at the end of the first line. */}
      <div
        className={`whitespace-nowrap font-mono text-2xl font-semibold tabular-nums sm:text-[1.75rem] ${color}`}
      >
        {value}
      </div>
      <div className="mt-2 text-sm font-medium text-foreground">{label}</div>
      {sub ? <div className="mt-1 text-xs leading-relaxed text-muted">{sub}</div> : null}
    </div>
  );
}

/** A short provenance note: which artifact backs the claim above it. */
export function Provenance({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 font-mono text-xs leading-relaxed text-muted">
      <span className="text-accent-dim">◆</span> {children}
    </p>
  );
}

export function Pill({
  children,
  tone = "plain",
}: {
  children: ReactNode;
  tone?: "plain" | "good" | "bad" | "accent";
}) {
  const tones = {
    plain: "border-border text-muted",
    good: "border-good/30 text-good bg-good/5",
    bad: "border-bad/30 text-bad bg-bad/5",
    accent: "border-accent/30 text-accent bg-accent/5",
  } as const;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 font-mono text-[11px] ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
