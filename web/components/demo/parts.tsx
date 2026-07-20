import type { ReactNode } from "react";

import { TenaxMark } from "@/components/ui";

/**
 * Primitives shared by the four /demo tabs.
 *
 * These are demo-local on purpose. ui.tsx's Section/Card/Stat are built for the scrolling
 * marketing page — Section hardcodes a top border, py-20 and its own header; Stat is a
 * page-scale KPI tile. The console needs denser equivalents. TenaxMark and Pill do carry
 * over unchanged and are imported rather than redrawn.
 */

/** The console's standard surface: every input box, output stage and result card. */
export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-xl border border-border bg-surface p-5 ${className}`}>
      {children}
    </div>
  );
}

/** Mono micro-label. The most repeated text style in the design. */
export function MonoLabel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`font-mono text-[11px] uppercase tracking-[0.16em] text-muted ${className}`}
    >
      {children}
    </div>
  );
}

/** Each tab's eyebrow + title + lede, matching Section's typographic rhythm at console scale. */
export function TabHeader({
  eyebrow,
  title,
  lede,
}: {
  eyebrow: string;
  title: string;
  lede?: ReactNode;
}) {
  return (
    <header>
      <p className="mb-2.5 font-mono text-xs uppercase tracking-[0.2em] text-accent">
        {eyebrow}
      </p>
      <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-[1.75rem]">
        {title}
      </h2>
      {lede ? (
        <p className="mt-2.5 max-w-2xl text-pretty leading-relaxed text-muted">{lede}</p>
      ) : null}
    </header>
  );
}

/**
 * The Cascade mark pulsing square by square while a request is in flight. The staggered
 * delays run the pulse around the grid rather than flashing all four at once, which reads as
 * work happening in sequence — the same read the static mark gives with its stepped opacity.
 */
export function CascadeLoader({ size = 16 }: { size?: number }) {
  return (
    <div
      className="grid gap-[5px]"
      style={{ gridTemplateColumns: `repeat(2, ${size}px)` }}
      aria-hidden
    >
      {[0, 0.15, 0.3, 0.45].map((d) => (
        <div
          key={d}
          className="rounded-[3px] bg-accent"
          style={{
            width: size,
            height: size,
            animation: `tnx-casc 1.2s ease-in-out infinite ${d}s`,
          }}
        />
      ))}
    </div>
  );
}

/** In-flight state for a full output panel. */
export function LoadingStage({ message }: { message: string }) {
  return (
    <div
      className="flex min-h-[300px] flex-col items-center justify-center gap-[18px] text-center"
      role="status"
    >
      <CascadeLoader />
      <p className="font-mono text-xs text-muted">{message}</p>
    </div>
  );
}

/** Compact in-flight state, for the maintenance cards where the button stays visible. */
export function LoadingRow({ message }: { message: string }) {
  return (
    <div className="mt-5 flex items-center gap-3" role="status">
      <CascadeLoader size={12} />
      <span className="font-mono text-xs text-muted">{message}</span>
    </div>
  );
}

/** Before-first-run state: the mark at rest, at its design opacities. */
export function EmptyStage({ message }: { message: string }) {
  return (
    <div className="flex min-h-[300px] flex-col items-center justify-center gap-4 text-center">
      <TenaxMark className="size-11 text-accent opacity-50" />
      <p className="max-w-[280px] leading-relaxed text-muted">{message}</p>
    </div>
  );
}

/** The amber primary action. Matches Hero/Replay, including the hardcoded dark text — the
 *  foreground token does not have enough contrast on accent. */
export function PrimaryButton({
  children,
  onClick,
  disabled,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded-lg bg-accent px-4.5 py-2.5 text-sm font-semibold text-[#07090d] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}

/** The bordered secondary action, as used by the maintenance sweeps. */
export function SecondaryButton({
  children,
  onClick,
  disabled,
  className = "",
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg border border-border bg-surface-2 px-4 py-2.5 text-sm transition-colors hover:border-accent/40 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
    >
      {children}
    </button>
  );
}

/** A small labelled meter. Used for the four recall signals and the decay bars. */
export function Meter({
  label,
  pct,
  color,
  opacity = 1,
}: {
  label: string;
  pct: number;
  color: string;
  opacity?: number;
}) {
  return (
    <div>
      <div className="mb-[3px] flex justify-between font-mono text-[9px] text-muted/70">
        <span>{label}</span>
        <span className="tabular-nums">{pct}</span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-border">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%`, opacity }}
        />
      </div>
    </div>
  );
}

/** The provenance footnote each tab closes with. Mirrors ui.tsx's Provenance, but the demo's
 *  sits at the bottom of a tab rather than under a figure, so it carries its own spacing. */
export function TabProvenance({ children }: { children: ReactNode }) {
  return (
    <p className="mt-5 font-mono text-[11px] leading-relaxed text-muted">
      <span className="text-accent-dim">◆</span> {children}
    </p>
  );
}
