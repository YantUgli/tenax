"use client";

import { useState } from "react";

import { TabHeader, TabProvenance } from "@/components/demo/parts";
import {
  formatImportance,
  type StatsResult,
  type StatusFilter,
  type StoredMemory,
} from "@/lib/tenax-api";

const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: "active", label: "active" },
  { id: "archived", label: "archived" },
  { id: "all", label: "all" },
];

/** Below this the memory is a forget-sweep candidate, so the meter turns red. Matches
 *  Settings.forget_threshold on the backend. */
const DECAY_ALERT = 0.15;

export function StoreTab({
  memories,
  stats,
}: {
  memories: StoredMemory[] | null;
  stats: StatsResult | null;
}) {
  // Filtered client-side rather than refetching: the console loads every status up front, so
  // switching filters is instant and costs no request.
  const [filter, setFilter] = useState<StatusFilter>("all");

  const rows = (memories ?? []).filter((m) =>
    filter === "all" ? true : filter === "active" ? m.status === "active" : m.status !== "active",
  );

  const byType = Object.entries(stats?.active_by_type ?? {});

  return (
    <section aria-label="Memory store">
      <TabHeader eyebrow="The store" title="Every memory, with its decay." />

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile value={stats?.total ?? 0} label="total memories" />
        <StatTile
          value={stats?.by_status?.active ?? 0}
          label="active"
          className="text-good"
        />
        <StatTile
          value={stats?.by_status?.archived ?? 0}
          label="archived"
          className="text-muted"
        />
        <div className="rounded-xl border border-border bg-surface px-5 py-4.5">
          <div className="flex flex-wrap gap-1.5">
            {byType.map(([k, v]) => (
              <span
                key={k}
                className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-px font-mono text-[11px] text-muted"
              >
                <span>{k}</span>
                <span className="tabular-nums">{v}</span>
              </span>
            ))}
          </div>
          <div className="mt-2 text-sm text-muted">active by type</div>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-2">
        <span className="font-mono text-[11px] text-muted">filter</span>
        {FILTERS.map((f) => {
          const on = filter === f.id;
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              aria-pressed={on}
              className={`rounded-full border px-3.5 py-1 font-mono text-xs transition-colors ${
                on
                  ? "border-accent/40 bg-accent/8 text-accent"
                  : "border-border text-muted hover:text-foreground"
              }`}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {rows.length === 0 ? (
        <p className="mt-4 rounded-xl border border-border bg-surface p-6 text-center text-muted">
          {memories === null ? "Loading memories…" : "No memories match this filter."}
        </p>
      ) : (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((m) => (
            <MemoryCard key={m.id} memory={m} />
          ))}
        </div>
      )}

      <TabProvenance>
        GET /memories · decay = importance × recency × (1 + log access_count); below{" "}
        {DECAY_ALERT} a memory is a forget-sweep candidate.
      </TabProvenance>
    </section>
  );
}

function StatTile({
  value,
  label,
  className = "text-foreground",
}: {
  value: number;
  label: string;
  className?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface px-5 py-4.5">
      <div className={`font-mono text-2xl font-semibold tabular-nums ${className}`}>
        {value}
      </div>
      <div className="mt-1.5 text-sm text-muted">{label}</div>
    </div>
  );
}

function MemoryCard({ memory: m }: { memory: StoredMemory }) {
  const dimmed = m.status !== "active";
  const badge = m.superseded_by ? "superseded" : dimmed ? "forgotten" : null;
  const alert = m.decay_score < DECAY_ALERT;
  const decayColor = alert ? "text-bad" : "text-accent";
  const decayBar = alert ? "bg-bad" : "bg-accent";

  return (
    <div
      className={`rounded-xl border bg-surface p-4 transition-opacity ${
        dimmed ? "border-border/50 opacity-55" : "border-border"
      }`}
    >
      <p className="text-sm leading-relaxed">
        {badge ? (
          <span className="mr-1.5 font-mono text-[10px] uppercase text-bad">{badge}</span>
        ) : null}
        {m.content}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center rounded-full border border-border px-2.5 py-px font-mono text-[10px] text-muted">
          {m.mem_type}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-muted">
          i={formatImportance(m.importance)}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-muted/70">
          {m.access_count} reads
        </span>
      </div>

      <div className="mt-3">
        <div className="mb-1 flex justify-between font-mono text-[10px] text-muted/70">
          <span>decay</span>
          <span className={`tabular-nums ${decayColor}`}>{m.decay_score.toFixed(3)}</span>
        </div>
        <div className="h-1.25 overflow-hidden rounded-full bg-surface-2">
          {/* Opacity tracks the score as well as width — a decaying memory fades as it
              shortens, which is the Cascade idea applied to a single row. */}
          <div
            className={`h-full rounded-full ${decayBar}`}
            style={{
              width: `${Math.round(Math.min(m.decay_score, 1) * 100)}%`,
              opacity: Math.max(0.2, m.decay_score),
            }}
          />
        </div>
      </div>
    </div>
  );
}
