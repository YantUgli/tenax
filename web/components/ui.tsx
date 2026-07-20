import type { ReactNode } from "react";

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
