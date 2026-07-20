"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { replay, type ReplayStep } from "@/lib/data";
import { Pill, Section } from "@/components/ui";

const STEPS = replay.steps;

const ACT_LABEL: Record<ReplayStep["act"], string> = {
  remember: "remember()",
  recall: "recall()",
  list_memories: "list_memories()",
  forget: "forget()",
  reflect: "reflect()",
};

export function Replay() {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const step = STEPS[i];
  const atEnd = i >= STEPS.length - 1;

  const next = useCallback(() => setI((n) => Math.min(n + 1, STEPS.length - 1)), []);
  const prev = useCallback(() => setI((n) => Math.max(n - 1, 0)), []);

  useEffect(() => {
    if (!playing) return;
    if (atEnd) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(next, 3800);
    return () => clearTimeout(t);
  }, [playing, atEnd, i, next]);

  return (
    <Section
      id="demo"
      eyebrow="See it run"
      title="A real session, replayed step by step."
      lede={
        <>
          Every response below is a verbatim capture of the live engine — Qwen Cloud for
          extraction and embeddings, Postgres/pgvector for the store. It is replayed rather
          than called live so it is identical every time you watch it, but nothing here is
          mocked or written by hand.
        </>
      }
    >
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={() => {
            if (atEnd) setI(0);
            setPlaying((p) => !p);
          }}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-[#07090d] transition-opacity hover:opacity-90"
        >
          {playing ? "Pause" : atEnd ? "Replay from start" : "Play"}
        </button>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => {
              setPlaying(false);
              prev();
            }}
            disabled={i === 0}
            className="rounded-lg border border-border px-3 py-2 text-sm text-muted transition-colors hover:text-foreground disabled:opacity-35"
          >
            ←
          </button>
          <button
            onClick={() => {
              setPlaying(false);
              next();
            }}
            disabled={atEnd}
            className="rounded-lg border border-border px-3 py-2 text-sm text-muted transition-colors hover:text-foreground disabled:opacity-35"
          >
            →
          </button>
        </div>
        <span className="font-mono text-xs text-muted">
          step {step.step} / {STEPS.length}
        </span>
      </div>

      {/* Step rail */}
      <div className="mt-5 flex gap-1" role="tablist" aria-label="Replay steps">
        {STEPS.map((s, idx) => (
          <button
            key={s.step}
            role="tab"
            aria-selected={idx === i}
            aria-label={`Step ${s.step}: ${s.caption}`}
            onClick={() => {
              setPlaying(false);
              setI(idx);
            }}
            className={`h-1.5 flex-1 rounded-full transition-colors ${
              idx === i ? "bg-accent" : idx < i ? "bg-accent/35" : "bg-surface-2"
            }`}
          />
        ))}
      </div>

      {/* Stage */}
      <div className="mt-8 grid gap-5 lg:grid-cols-[1fr_1.3fr]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded-md bg-accent/10 px-2 py-0.5 font-mono text-xs text-accent">
              {ACT_LABEL[step.act]}
            </code>
            {step.age_days !== undefined ? (
              <Pill>{step.age_days}d ago</Pill>
            ) : null}
            {step.token_budget ? <Pill>budget {step.token_budget} tok</Pill> : null}
          </div>
          <h3 className="mt-4 text-lg font-medium leading-snug">{step.caption}</h3>
          {step.note ? (
            <p className="mt-3 text-sm leading-relaxed text-muted">{step.note}</p>
          ) : null}

          {step.text ? (
            <div className="mt-5 rounded-xl border border-border bg-surface-2 p-4">
              <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
                Input
              </div>
              <p className="mt-2 text-sm leading-relaxed">{step.text}</p>
            </div>
          ) : null}
          {step.query ? (
            <div className="mt-5 rounded-xl border border-border bg-surface-2 p-4">
              <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
                Query
              </div>
              <p className="mt-2 text-sm leading-relaxed">{step.query}</p>
            </div>
          ) : null}
        </div>

        <div className="min-h-[22rem] rounded-xl border border-border bg-surface p-5">
          <StepOutput step={step} />
        </div>
      </div>

      <p className="mt-5 font-mono text-xs text-muted">
        <span className="text-accent-dim">◆</span> Captured by{" "}
        <code>scripts/record_replay.py</code> · full transcript in{" "}
        <code>web/data/replay.json</code>
      </p>

      {/* The handoff: this replay is fixed and cannot fail mid-demo, which is exactly why it
          proves nothing a recording couldn't. The live console is where someone types their
          own query. */}
      <p className="mt-3 text-sm text-muted">
        This session is a recording — identical every viewing.{" "}
        <Link href="/demo" className="text-link hover:underline">
          Drive a live instance yourself →
        </Link>
      </p>
    </Section>
  );
}

function StepOutput({ step }: { step: ReplayStep }) {
  const r = step.response;

  if (step.act === "remember") {
    return (
      <div>
        <OutputHeading>
          Extracted {r.created?.length ?? 0} memor
          {(r.created?.length ?? 0) === 1 ? "y" : "ies"}
        </OutputHeading>
        <ul className="mt-3 space-y-2">
          {(r.created ?? []).map((m: any) => (
            <li
              key={m.id}
              className="rounded-lg border border-border bg-surface-2 px-3.5 py-2.5"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm leading-relaxed">{m.content}</p>
                <span className="shrink-0 font-mono text-[11px] text-accent">
                  i={m.importance}
                </span>
              </div>
              <div className="mt-1.5 font-mono text-[11px] text-muted">{m.mem_type}</div>
            </li>
          ))}
        </ul>
        {(r.superseded ?? []).length > 0 ? (
          <div className="mt-5 rounded-lg border border-bad/30 bg-bad/5 px-3.5 py-3">
            <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-bad">
              Belief revised
            </div>
            {r.superseded.map((s: any) => (
              <p key={s.id} className="mt-2 text-sm leading-relaxed">
                <span className="line-through decoration-bad/60">{s.content}</span>
                <span className="mt-1 block font-mono text-[11px] text-muted">
                  archived · superseded_by #{s.superseded_by}
                </span>
              </p>
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  if (step.act === "recall") {
    const pctUsed = Math.round((r.tokens_used / r.token_budget) * 100);
    return (
      <div>
        <OutputHeading>
          Assembled context — {r.memories.length} of {r.candidates_considered} candidates
        </OutputHeading>
        <div className="mt-3">
          <div className="flex items-center justify-between font-mono text-[11px] text-muted">
            <span>
              {r.tokens_used} / {r.token_budget} tokens
            </span>
            <span>{pctUsed}% of budget</span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full bg-accent" style={{ width: `${pctUsed}%` }} />
          </div>
        </div>
        <pre className="mt-4 overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-surface-2 p-3.5 font-mono text-[12px] leading-relaxed">
          {(r.context as string).split("\n").map((line, idx) => {
            const isPast = line.includes("PAST (superseded");
            return (
              <span
                key={idx}
                className={isPast ? "block text-bad/85" : "block"}
              >
                {line}
              </span>
            );
          })}
        </pre>
      </div>
    );
  }

  if (step.act === "list_memories") {
    const rows = r as any[];
    const active = rows.filter((m) => m.status === "active");
    const archived = rows.filter((m) => m.status !== "active");
    return (
      <div>
        <OutputHeading>
          {active.length} active · {archived.length} archived
        </OutputHeading>
        <ul className="mt-3 max-h-[26rem] space-y-1.5 overflow-y-auto pr-1">
          {rows.map((m) => (
            <li
              key={m.id}
              className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2 ${
                m.status === "active"
                  ? "border-border bg-surface-2"
                  : "border-border/50 bg-transparent opacity-55"
              }`}
            >
              <p className="text-[13px] leading-relaxed">
                {m.status !== "active" ? (
                  <span className="mr-1.5 font-mono text-[10px] uppercase text-bad">
                    {m.superseded_by ? "superseded" : "forgotten"}
                  </span>
                ) : null}
                {m.content}
              </p>
              <span
                className={`shrink-0 font-mono text-[11px] tabular-nums ${
                  m.decay_score < 0.15 ? "text-bad" : "text-muted"
                }`}
                title="decay score"
              >
                {m.decay_score.toFixed(3)}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 font-mono text-[11px] text-muted">
          decay = importance · e^(−Δt/τ) · (1 + ln(1+accesses)) · threshold 0.15
        </p>
      </div>
    );
  }

  if (step.act === "forget") {
    return (
      <div>
        <OutputHeading>Decay sweep</OutputHeading>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <BigNum value={r.scanned} label="scanned" />
          <BigNum value={r.archived} label="archived" tone="bad" />
        </div>
        <p className="mt-4 text-sm leading-relaxed text-muted">
          Soft-forget: status flips to <code className="font-mono">archived</code> rather than
          being deleted, so a sweep is reversible and auditable.
        </p>
      </div>
    );
  }

  // reflect
  return (
    <div>
      <OutputHeading>Consolidation</OutputHeading>
      <div className="mt-4 grid grid-cols-3 gap-3">
        <BigNum value={r.clusters_found} label="clusters" />
        <BigNum value={r.memories_merged} label="merged" />
        <BigNum value={r.semantic_created} label="canonical" />
      </div>
    </div>
  );
}

function OutputHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
      {children}
    </div>
  );
}

function BigNum({
  value,
  label,
  tone = "plain",
}: {
  value: number;
  label: string;
  tone?: "plain" | "bad";
}) {
  return (
    <div className="rounded-lg border border-border bg-surface-2 px-4 py-4">
      <div
        className={`font-mono text-2xl font-semibold tabular-nums ${
          tone === "bad" && value > 0 ? "text-bad" : "text-foreground"
        }`}
      >
        {value}
      </div>
      <div className="mt-1 font-mono text-[11px] text-muted">{label}</div>
    </div>
  );
}
