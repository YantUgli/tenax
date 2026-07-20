"use client";

import { useState } from "react";

import {
  EmptyStage,
  LoadingStage,
  Meter,
  MonoLabel,
  Panel,
  PrimaryButton,
  TabHeader,
  TabProvenance,
} from "@/components/demo/parts";
import { sampleRecall } from "@/components/demo/sample-data";
import { Pill } from "@/components/ui";
import * as api from "@/lib/tenax-api";
import { delay, type DemoSession, type RecallResult } from "@/lib/tenax-api";

/** Colour per retrieval signal, so the same signal reads the same across every card. */
const SIGNALS = [
  { key: "semantic", label: "sem", color: "bg-accent" },
  { key: "keyword", label: "kw", color: "bg-link" },
  { key: "recency", label: "rec", color: "bg-good" },
  { key: "importance", label: "imp", color: "bg-bad" },
] as const;

export function RecallTab({ session }: { session: DemoSession }) {
  const [query, setQuery] = useState("What do you remember about my research?");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RecallResult | null>(null);
  // The budget bar mounts at 0 and transitions to its real width one tick later, so the fill
  // animates rather than appearing already full. This is the tab's signature moment.
  const [barFilled, setBarFilled] = useState(false);

  async function run() {
    const q = query.trim();
    if (!q || busy) return;

    setBusy(true);
    setResult(null);
    setBarFilled(false);

    let res: RecallResult;
    try {
      if (session.live) {
        res = await api.recall(session.base, session.userId, q, session.tokenBudget);
      } else {
        // Held deliberately: without it the sample path resolves instantly and the loading
        // state flashes past, which reads as nothing having happened.
        await delay(1400);
        res = sampleRecall(session.tokenBudget);
      }
    } catch {
      await delay(300);
      res = sampleRecall(session.tokenBudget);
    }

    setBusy(false);
    setResult(res);
    setTimeout(() => setBarFilled(true), 80);
  }

  const pct = result && result.token_budget > 0
    ? Math.round((result.tokens_used / result.token_budget) * 100)
    : 0;

  return (
    <section aria-label="Recall">
      <TabHeader
        eyebrow="The money shot"
        title="Recall — hybrid retrieval, packed to a token budget."
        lede="Ask a question. Tenax scores every candidate memory on four signals, then greedily packs the highest-relevance set that fits the budget — that assembled context is exactly what gets injected into the agent."
      />

      <div className="mt-7 grid items-start gap-5 lg:grid-cols-2">
        <Panel className="shadow-[0_1px_0_rgba(255,255,255,0.03)_inset]">
          <MonoLabel>
            <label htmlFor="tnx-query">Query</label>
          </MonoLabel>
          <textarea
            id="tnx-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={3}
            placeholder="What do you remember about my research?"
            className="mt-2.5 w-full resize-y rounded-[10px] border border-border bg-surface-2 p-3 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted/50 focus:border-accent/50"
          />
          <div className="mt-3.5 flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2">
              {/* One text node on purpose: Pill is inline-flex, so separate children become
                  flex items and the whitespace between them collapses ("budget1200tok"). */}
              <Pill tone="accent">
                <span className="tabular-nums">{`budget ${session.tokenBudget} tok`}</span>
              </Pill>
              <span className="font-mono text-[11px] text-muted/70">
                user {session.userId}
              </span>
            </div>
            <PrimaryButton onClick={run} disabled={busy}>
              {busy ? "Recalling…" : "Recall"}
            </PrimaryButton>
          </div>
        </Panel>

        <Panel className="min-h-[340px]">
          {busy ? (
            <LoadingStage message="Embedding query · scoring candidates · packing budget…" />
          ) : !result ? (
            <EmptyStage message="Run a query to see the budget bar fill and the assembled context appear." />
          ) : (
            <div>
              <MonoLabel>
                Assembled context — {result.memories.length} of{" "}
                {/* Absent on the empty-candidate early return, so never read unguarded. */}
                {result.candidates_considered ?? result.memories.length} candidates
              </MonoLabel>

              <div className="mt-3.5 flex justify-between font-mono text-[11px] tabular-nums text-muted">
                <span>
                  {result.tokens_used} / {result.token_budget} tokens
                </span>
                <span>{pct}% of budget</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{
                    width: `${barFilled ? pct : 0}%`,
                    transition: "width .9s cubic-bezier(.2,.8,.2,1)",
                  }}
                />
              </div>

              <ul className="tnx-scroll mt-4.5 flex max-h-[300px] flex-col gap-2.5 overflow-y-auto">
                {result.memories.map((m, i) => (
                  <li
                    key={m.id}
                    className="rounded-[10px] border border-border bg-surface-2 px-3.5 py-3"
                    style={{ animation: `tnx-fadeup .4s ease both ${i * 0.09}s` }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-[13.5px] leading-relaxed">{m.content}</p>
                      <span className="shrink-0 font-mono text-[11px] tabular-nums text-accent">
                        {m.scores.combined.toFixed(2)}
                      </span>
                    </div>
                    <div className="mt-2.5 grid grid-cols-4 gap-2">
                      {SIGNALS.map((s) => (
                        <Meter
                          key={s.key}
                          label={s.label}
                          pct={Math.round((m.scores[s.key] ?? 0) * 100)}
                          color={s.color}
                        />
                      ))}
                    </div>
                  </li>
                ))}
              </ul>

              <MonoLabel className="mt-4">context injected into agent</MonoLabel>
              <pre className="tnx-scroll mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded-[10px] border border-border bg-surface-2 p-3.5 font-mono text-xs leading-relaxed">
                {result.context.split("\n").map((line, i) => (
                  <span
                    key={i}
                    className={`block ${line.startsWith("PAST") ? "text-bad/85" : ""}`}
                  >
                    {line || " "}
                  </span>
                ))}
              </pre>
            </div>
          )}
        </Panel>
      </div>

      <TabProvenance>
        POST /recall · scores = semantic · keyword · recency · importance → combined; greedy
        pack under budget.
      </TabProvenance>
    </section>
  );
}
