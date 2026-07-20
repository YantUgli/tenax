"use client";

import {
  MonoLabel,
  Panel,
  SecondaryButton,
  TabHeader,
  TabProvenance,
} from "@/components/demo/parts";

/**
 * Session settings.
 *
 * This is the same set of controls that used to live in the header's gear popover — same
 * fields, same ids, same handlers — re-laid-out as a tab panel. Nothing was rebuilt: the state
 * still lives in DemoConsole, which is what the status chip and every tab read from.
 *
 * The popover's cramped 290px column is gone, so the fields get room and the explanatory notes
 * can sit beside the input they describe rather than under it.
 */
export function SettingsTab({
  base,
  userId,
  tokenBudget,
  live,
  model,
  checking,
  onBase,
  onUser,
  onBudget,
  onRecheck,
}: {
  base: string;
  userId: string;
  tokenBudget: number;
  live: boolean;
  model: string;
  checking: boolean;
  onBase: (v: string) => void;
  onUser: (v: string) => void;
  onBudget: (v: number) => void;
  onRecheck: () => void;
}) {
  const field =
    "w-full rounded-[10px] border border-border bg-surface-2 px-3 py-2.5 font-mono text-xs text-foreground outline-none focus:border-accent/50";
  const note = "mt-2 font-mono text-[11px] leading-relaxed text-muted/70";

  return (
    <section aria-label="Settings">
      <TabHeader
        eyebrow="Session"
        title="Settings — point the console at a backend."
        lede="Every tab reads this session. Change a field, recheck, and the status chip in the header tells you which mode you are in — live, or sample data."
      />

      <div className="mt-7 grid items-start gap-5 lg:grid-cols-2">
        <Panel>
          <MonoLabel>
            <label htmlFor="tnx-backend">Backend URL</label>
          </MonoLabel>
          <input
            id="tnx-backend"
            value={base}
            onChange={(e) => onBase(e.target.value)}
            spellCheck={false}
            className={`${field} mt-2.5`}
          />
          <p className={note}>
            Browser → <b className="text-muted">/api/tenax</b> (https) → backend (http). The
            proxy fixes mixed content.
          </p>

          <MonoLabel className="mt-5">
            <label htmlFor="tnx-user">User ID</label>
          </MonoLabel>
          <input
            id="tnx-user"
            value={userId}
            onChange={(e) => onUser(e.target.value)}
            spellCheck={false}
            className={`${field} mt-2.5`}
          />
          <p className={note}>
            Memories are scoped per user. A name nobody has used yet starts from an empty
            store.
          </p>
        </Panel>

        <Panel>
          <MonoLabel>
            <label htmlFor="tnx-budget">Recall token budget</label>
          </MonoLabel>
          <div className="mt-2.5 flex items-center gap-4">
            <input
              id="tnx-budget"
              type="range"
              min={100}
              max={4000}
              step={100}
              value={tokenBudget}
              onChange={(e) => onBudget(Number.parseInt(e.target.value, 10))}
              className="w-full accent-accent"
            />
            <span className="shrink-0 font-mono text-sm tabular-nums text-accent">
              {tokenBudget}
            </span>
          </div>
          <p className={note}>
            The ceiling Recall packs to. Lower it to watch the greedy packer drop the
            lowest-scoring memories first.
          </p>

          <div className="mt-6 border-t border-border pt-5">
            <MonoLabel>Backend status</MonoLabel>
            <p className="mt-2.5 text-sm text-muted">
              {checking
                ? "Checking…"
                : live
                  ? `Connected — reader model ${model}.`
                  : "Unreachable. Every tab is rendering sample data, labelled as such."}
            </p>
            <SecondaryButton onClick={onRecheck} className="mt-3.5">
              Recheck backend
            </SecondaryButton>
          </div>
        </Panel>
      </div>

      <TabProvenance>
        GET /health on load and on recheck · settings are client-side only and reset on reload.
      </TabProvenance>
    </section>
  );
}
