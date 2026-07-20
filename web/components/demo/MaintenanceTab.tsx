"use client";

import { useState } from "react";

import {
  LoadingRow,
  MonoLabel,
  Panel,
  SecondaryButton,
  TabHeader,
  TabProvenance,
} from "@/components/demo/parts";
import { SAMPLE_FADING, sampleForget, sampleReflect } from "@/components/demo/sample-data";
import { benchmark } from "@/lib/data";
import * as api from "@/lib/tenax-api";
import {
  delay,
  type DemoSession,
  type ForgetResult,
  type ReflectResult,
  type StoredMemory,
} from "@/lib/tenax-api";

export function MaintenanceTab({
  session,
  memories,
  onStoreChanged,
}: {
  session: DemoSession;
  memories: StoredMemory[] | null;
  onStoreChanged: () => void;
}) {
  const [forgetting, setForgetting] = useState(false);
  const [forgetResult, setForgetResult] = useState<ForgetResult | null>(null);
  const [reflecting, setReflecting] = useState(false);
  const [reflectResult, setReflectResult] = useState<ReflectResult | null>(null);

  async function runForget() {
    if (forgetting) return;
    setForgetting(true);
    setForgetResult(null);

    let res: ForgetResult;
    let wroteLive = false;
    try {
      if (session.live) {
        res = await api.forget(session.base, session.userId);
        wroteLive = true;
      } else {
        await delay(1500);
        res = sampleForget();
      }
    } catch {
      await delay(300);
      res = sampleForget();
    }

    setForgetting(false);
    setForgetResult(res);
    if (wroteLive) onStoreChanged();
  }

  async function runReflect() {
    if (reflecting) return;
    setReflecting(true);
    setReflectResult(null);

    let res: ReflectResult;
    let wroteLive = false;
    try {
      if (session.live) {
        res = await api.reflect(session.base, session.userId);
        wroteLive = true;
      } else {
        await delay(1500);
        res = sampleReflect();
      }
    } catch {
      await delay(300);
      res = sampleReflect();
    }

    setReflecting(false);
    setReflectResult(res);
    if (wroteLive) onStoreChanged();
  }

  // The rows the sweep just archived, shown fading out. Resolved from the store snapshot by
  // id so live runs name the memories they actually archived, rather than a canned list.
  const fading =
    forgetResult && memories
      ? forgetResult.archived_ids
          .map((id) => memories.find((m) => m.id === id)?.content)
          .filter((c): c is string => Boolean(c))
      : [];
  const fadingRows = fading.length > 0 ? fading : session.live ? [] : SAMPLE_FADING;

  return (
    <section aria-label="Maintenance">
      <TabHeader
        eyebrow="Self-maintenance"
        title="Forget stale, consolidate duplicates — safely."
      />

      <div className="mt-7 grid items-start gap-5 lg:grid-cols-2">
        <Panel>
          <h3 className="text-[17px] font-semibold">Forget sweep</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
            Archive low-value memories below the decay threshold. Soft-forget: status flips to{" "}
            <code className="font-mono text-foreground">archived</code>, never deleted —
            reversible and auditable.
          </p>
          <SecondaryButton onClick={runForget} disabled={forgetting} className="mt-4">
            {forgetting ? "Sweeping…" : "Run forget sweep"}
          </SecondaryButton>

          {forgetting ? <LoadingRow message="Scanning decay scores…" /> : null}

          {!forgetting && forgetResult ? (
            <div className="mt-4.5">
              <div className="grid grid-cols-2 gap-2.5">
                <ResultTile value={forgetResult.scanned} label="scanned" />
                <ResultTile
                  value={forgetResult.archived}
                  label="archived"
                  className="text-bad"
                />
              </div>
              {fadingRows.length > 0 ? (
                <ul className="mt-3.5 flex flex-col gap-2">
                  {fadingRows.map((content, i) => (
                    <li
                      key={content}
                      className="rounded-lg border border-border bg-surface-2 px-3 py-2.5 text-[13px] text-muted"
                      style={{ animation: `tnx-fadeout 1s ease forwards ${i * 0.25}s` }}
                    >
                      {content}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3.5 text-[13px] text-muted">
                  Nothing was below the threshold — every memory still earns its place.
                </p>
              )}
            </div>
          ) : null}
        </Panel>

        <Panel>
          <h3 className="text-[17px] font-semibold">Reflect / consolidate</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-muted">
            Cluster near-duplicates and distill them into canonical facts. The trust signal is{" "}
            <code className="font-mono text-foreground">wrong_merges</code> — merges that
            shouldn&apos;t have happened.
          </p>
          <SecondaryButton onClick={runReflect} disabled={reflecting} className="mt-4">
            {reflecting ? "Reflecting…" : "Run reflection"}
          </SecondaryButton>

          {reflecting ? <LoadingRow message="Clustering & distilling with Qwen…" /> : null}

          {!reflecting && reflectResult ? (
            <div className="mt-4.5">
              <div className="grid grid-cols-3 gap-2.5">
                <ResultTile
                  value={reflectResult.clusters_found}
                  label="clusters"
                  small
                />
                <ResultTile
                  value={reflectResult.memories_merged}
                  label="merged"
                  small
                />
                {/* The /reflect response carries no wrong-merge count — consolidate.py does
                    not compute one. This is the measured benchmark figure, labelled as such
                    by the provenance line below so it is never read as this run's output. */}
                <div className="rounded-[10px] border border-good/30 bg-good/5 p-3.5">
                  <div className="font-mono text-[22px] font-semibold tabular-nums text-good">
                    {benchmark.staleness.wrong_merges}
                  </div>
                  <MonoLabel className="mt-1 text-good">wrong merges</MonoLabel>
                </div>
              </div>
              <p className="mt-3.5 text-[13px] leading-relaxed text-muted">
                <span className="text-good">✓</span> {reflectResult.memories_merged}{" "}
                near-duplicates consolidated
                {reflectResult.semantic_created > 0
                  ? `, ${reflectResult.semantic_created} canonical ${
                      reflectResult.semantic_created === 1 ? "fact" : "facts"
                    } distilled`
                  : ""}
                .
              </p>
            </div>
          ) : null}
        </Panel>
      </div>

      <TabProvenance>
        POST /forget · POST /reflect — the self-managing half of the loop. The wrong-merge
        count is not returned by /reflect; it is the measured figure from the staleness run on{" "}
        {benchmark.measured_on} ({benchmark.staleness.cycles} cycles), recorded in{" "}
        <code>benchmark/results/</code>.
      </TabProvenance>
    </section>
  );
}

function ResultTile({
  value,
  label,
  className = "text-foreground",
  small = false,
}: {
  value: number;
  label: string;
  className?: string;
  small?: boolean;
}) {
  return (
    <div className="rounded-[10px] border border-border bg-surface-2 p-3.5">
      <div
        className={`font-mono font-semibold tabular-nums ${small ? "text-[22px]" : "text-2xl"} ${className}`}
      >
        {value}
      </div>
      <MonoLabel className="mt-1">{label}</MonoLabel>
    </div>
  );
}
