"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { MaintenanceTab } from "@/components/demo/MaintenanceTab";
import { RecallTab } from "@/components/demo/RecallTab";
import { RememberTab } from "@/components/demo/RememberTab";
import { SettingsTab } from "@/components/demo/SettingsTab";
import { StoreTab } from "@/components/demo/StoreTab";
import { sampleMemories, sampleStats } from "@/components/demo/sample-data";
import { TenaxMark } from "@/components/ui";
import * as api from "@/lib/tenax-api";
import { DEFAULT_BASE, type DemoSession, type StatsResult, type StoredMemory } from "@/lib/tenax-api";

const TABS = [
  { id: "recall", label: "Recall" },
  { id: "remember", label: "Remember" },
  { id: "store", label: "Memory store" },
  { id: "maintenance", label: "Maintenance" },
  // Last on purpose: settings is the only tab that configures the console rather than
  // demonstrating it, and it inherits the identical styling by living in this same array.
  { id: "settings", label: "Settings" },
] as const;

type TabId = (typeof TABS)[number]["id"];

/**
 * The live Tenax console.
 *
 * Owns the session (backend URL, user, token budget) and the health probe; each tab owns its
 * own request state. Every call degrades to sample data rather than erroring — if the backend
 * is down while someone is watching, the page still demonstrates the shape of the system, and
 * the status chip says plainly which mode is on screen.
 */
export function DemoConsole() {
  const [tab, setTab] = useState<TabId>("recall");

  const [base, setBase] = useState(DEFAULT_BASE);
  const [userId, setUserId] = useState("demo");
  const [tokenBudget, setTokenBudget] = useState(1200);

  const [live, setLive] = useState(false);
  const [model, setModel] = useState("");
  const [checking, setChecking] = useState(true);

  // Store data lives here rather than in StoreTab: the maintenance sweeps mutate it, and
  // switching tabs unmounts the tab that fetched it.
  const [memories, setMemories] = useState<StoredMemory[] | null>(null);
  const [stats, setStats] = useState<StatsResult | null>(null);

  const loadStore = useCallback(
    async (isLive: boolean) => {
      if (isLive) {
        try {
          const [m, s] = await Promise.all([
            api.listMemories(base, userId),
            api.stats(base, userId),
          ]);
          setMemories(m);
          setStats(s);
          return;
        } catch {
          // Health said OK but the store call failed — fall through to samples.
        }
      }
      setMemories(sampleMemories());
      setStats(sampleStats());
    },
    [base, userId],
  );

  const checkHealth = useCallback(async () => {
    setChecking(true);
    try {
      const r = await api.health(base);
      const ok = Boolean(r?.status);
      setLive(ok);
      setModel(r?.model ?? "qwen");
      setChecking(false);
      await loadStore(ok);
    } catch {
      setLive(false);
      setChecking(false);
      await loadStore(false);
    }
  }, [base, loadStore]);

  // Mount only. checkHealth closes over the settings fields, so running it on every change
  // would re-probe the backend on each keystroke in the URL box; the Settings tab's "Recheck
  // backend" button is the deliberate re-trigger.
  const probe = useRef(checkHealth);
  useEffect(() => {
    probe.current = checkHealth;
  });
  useEffect(() => {
    void probe.current();
  }, []);

  const session: DemoSession = { base, userId, tokenBudget, live };
  const reloadStore = useCallback(() => loadStore(live), [loadStore, live]);

  const statusTone = checking ? "text-accent-dim" : live ? "text-good" : "text-accent-dim";
  const statusText = checking
    ? "Checking backend…"
    : live
      ? `Backend OK · ${model}`
      : "Sample data · offline";

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-3.5 sm:px-8">
          <div className="flex items-baseline gap-2">
            <Link href="/" className="flex items-baseline gap-2">
              <TenaxMark className="size-4.5 self-center text-accent" />
              <span className="font-mono text-lg font-semibold tracking-tight">Tenax</span>
            </Link>
            {/* Same slot and same styling as Nav's "MCP memory server" descriptor, saying
                where you are instead. Hidden on the narrowest screens so the status chip and
                buttons keep the header to one row. */}
            <span className="hidden font-mono text-[11px] text-muted sm:inline">
              memoria tenax · live demo
            </span>
          </div>

          {/* Wraps because the chip's text is nowrap: on a phone the chip and the two buttons
              cannot share a line, so they stack instead of forcing the page to scroll sideways. */}
          <div className="flex flex-wrap items-center justify-end gap-2.5">
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5">
              {/* shrink-0: without it the flex row squeezes the dot's width on narrow screens
                  while its height holds, and the status light renders as an ellipse. */}
              <span
                className={`size-2 shrink-0 rounded-full bg-current ${statusTone}`}
                style={{ boxShadow: "0 0 8px currentColor" }}
                aria-hidden
              />
              <span className="whitespace-nowrap font-mono text-[11px] text-muted">
                {statusText}
              </span>
            </div>

            {/* Nav.tsx's secondary button style, verbatim. Deliberately not the accented
                variant Nav gives "Live demo →": there, the accent marks the way into the app.
                Here the app is already open, so leaving it is the quieter action. */}
            <Link
              href="/"
              className="whitespace-nowrap rounded-lg border border-border px-3 py-1.5 font-mono text-xs text-muted transition-colors hover:border-accent/40 hover:text-foreground"
            >
              ← Back to site
            </Link>
            <a
              href="https://github.com/YantUgli/tenax"
              className="rounded-lg border border-border px-3 py-1.5 font-mono text-xs text-muted transition-colors hover:border-accent/40 hover:text-foreground"
            >
              GitHub
            </a>
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-6xl gap-1 overflow-x-auto px-5 sm:px-8">
          {TABS.map((t) => {
            const isActive = t.id === tab;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                aria-current={isActive ? "page" : undefined}
                className={`relative whitespace-nowrap px-3.5 pb-3.5 pt-3 text-sm transition-colors ${
                  isActive ? "text-foreground" : "text-muted hover:text-foreground"
                }`}
              >
                {t.label}
                <span
                  className={`absolute inset-x-2 bottom-0 h-0.5 origin-left rounded-sm bg-accent transition-transform duration-300 ${
                    isActive ? "scale-x-100" : "scale-x-0"
                  }`}
                />
              </button>
            );
          })}
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-8 sm:px-8">
        {tab === "recall" ? <RecallTab session={session} /> : null}
        {tab === "remember" ? (
          <RememberTab session={session} onStoreChanged={reloadStore} />
        ) : null}
        {tab === "store" ? <StoreTab memories={memories} stats={stats} /> : null}
        {tab === "maintenance" ? (
          <MaintenanceTab
            session={session}
            memories={memories}
            onStoreChanged={reloadStore}
          />
        ) : null}
        {tab === "settings" ? (
          <SettingsTab
            base={base}
            userId={userId}
            tokenBudget={tokenBudget}
            live={live}
            model={model}
            checking={checking}
            onBase={setBase}
            onUser={setUserId}
            onBudget={setTokenBudget}
            onRecheck={() => void checkHealth()}
          />
        ) : null}
      </main>
    </div>
  );
}
