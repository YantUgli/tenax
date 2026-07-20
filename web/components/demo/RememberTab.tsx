"use client";

import { useState } from "react";

import {
  EmptyStage,
  LoadingStage,
  MonoLabel,
  Panel,
  PrimaryButton,
  TabHeader,
  TabProvenance,
} from "@/components/demo/parts";
import { sampleRemember } from "@/components/demo/sample-data";
import * as api from "@/lib/tenax-api";
import {
  delay,
  formatImportance,
  resolveReplacement,
  type DemoSession,
  type RememberResult,
} from "@/lib/tenax-api";

export function RememberTab({
  session,
  onStoreChanged,
}: {
  session: DemoSession;
  onStoreChanged: () => void;
}) {
  const [text, setText] = useState(
    "I just moved to Singapore for a postdoc. Dr. Lin is still my advisor, now remotely.",
  );
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RememberResult | null>(null);

  async function run() {
    const t = text.trim();
    if (!t || busy) return;

    setBusy(true);
    setResult(null);

    let res: RememberResult;
    let wroteLive = false;
    try {
      if (session.live) {
        res = await api.remember(session.base, session.userId, t);
        wroteLive = true;
      } else {
        await delay(1600);
        res = sampleRemember();
      }
    } catch {
      await delay(300);
      res = sampleRemember();
    }

    setBusy(false);
    setResult(res);
    // A live write changes the store, so the Memory store tab must not keep showing the
    // pre-write snapshot.
    if (wroteLive) onStoreChanged();
  }

  // Both fields are optional: the "nothing worth remembering" response carries `note` and no
  // `superseded` key at all.
  const created = result?.created ?? [];
  const superseded = result?.superseded ?? [];

  return (
    <section aria-label="Remember">
      <TabHeader
        eyebrow="Write path"
        title="Remember — Qwen extracts what's worth keeping."
        lede="Feed an interaction. Distilled memories are extracted with a type and importance. When a new fact contradicts a stored one, belief revision fires: the stale memory is archived with a pointer to what supersedes it."
      />

      <div className="mt-7 grid items-start gap-5 lg:grid-cols-2">
        <Panel className="shadow-[0_1px_0_rgba(255,255,255,0.03)_inset]">
          <MonoLabel>
            <label htmlFor="tnx-interaction">Feed an interaction</label>
          </MonoLabel>
          <textarea
            id="tnx-interaction"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            placeholder="e.g. I just moved to Singapore for a postdoc. Dr. Lin is still my advisor…"
            className="mt-2.5 w-full resize-y rounded-[10px] border border-border bg-surface-2 p-3 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted/50 focus:border-accent/50"
          />
          <div className="mt-3.5 flex justify-end">
            <PrimaryButton onClick={run} disabled={busy}>
              {busy ? "Remembering…" : "Remember"}
            </PrimaryButton>
          </div>
        </Panel>

        <Panel className="min-h-[340px]">
          {busy ? (
            <LoadingStage message="Qwen is extracting memories & checking for revisions…" />
          ) : !result ? (
            <EmptyStage message="Submit an interaction to watch memories get extracted — and beliefs revised." />
          ) : created.length === 0 ? (
            // The engine's explicit "nothing worth remembering" path. Surfaced as itself
            // rather than as an empty list, because deciding not to store is a real result.
            <div className="flex min-h-[300px] flex-col items-center justify-center gap-3 text-center">
              <MonoLabel>Nothing extracted</MonoLabel>
              <p className="max-w-[300px] leading-relaxed text-muted">
                {result.note ?? "Nothing in that interaction was worth remembering."}
              </p>
            </div>
          ) : (
            <div>
              <MonoLabel>
                Extracted {created.length} {created.length === 1 ? "memory" : "memories"}
              </MonoLabel>
              <ul className="mt-3 flex flex-col gap-2.5">
                {created.map((m, i) => (
                  <li
                    key={m.id}
                    className="rounded-[10px] border border-border bg-surface-2 px-3.5 py-3"
                    style={{ animation: `tnx-fadeup .45s ease both ${i * 0.12}s` }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-[13.5px] leading-relaxed">{m.content}</p>
                      <span className="shrink-0 font-mono text-[11px] tabular-nums text-accent">
                        i={formatImportance(m.importance)}
                      </span>
                    </div>
                    <div className="mt-2 inline-flex items-center rounded-full border border-border px-2.5 py-px font-mono text-[10px] text-muted">
                      {m.mem_type}
                    </div>
                  </li>
                ))}
              </ul>

              {superseded.length > 0 ? (
                <div
                  className="mt-4 rounded-[10px] border border-bad/30 bg-bad/5 p-3.5"
                  style={{ animation: "tnx-fadeup .5s ease both .35s" }}
                >
                  <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-bad">
                    Belief revised
                  </div>
                  {superseded.map((s) => (
                    <div key={s.id} className="mt-2.5">
                      <p className="text-[13.5px] leading-relaxed text-bad line-through decoration-bad/60">
                        {s.content}
                      </p>
                      <div className="mt-1.5 flex items-center gap-2">
                        <span className="text-[15px] leading-none text-bad">↓</span>
                        <p className="text-[13.5px] leading-relaxed">
                          {/* The API returns only the replacing id; the text is recovered
                              from created[] in the same response. */}
                          {resolveReplacement(s, created)}
                        </p>
                      </div>
                      <div className="mt-1.5 font-mono text-[10px] text-muted">
                        archived · superseded_by #{s.superseded_by}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </Panel>
      </div>

      <TabProvenance>
        POST /remember → {"{ created[], superseded[] }"} · revision keeps recall serving the
        current truth.
      </TabProvenance>
    </section>
  );
}
