/**
 * Typed client for the live Tenax backend, used only by /demo.
 *
 * Requests go through the same-origin proxy at app/api/tenax (see that file for why). The
 * base path is configurable at runtime from the demo's settings popover, so a judge can point
 * the page at any reachable backend without a rebuild.
 *
 * The types below are transcribed from what the engine actually returns, which differs from
 * the reference design's sample data in several ways that would otherwise crash the page.
 * Each divergence is called out at its field.
 */

export const DEFAULT_BASE = "/api/tenax";

/** Matches the client-side abort in the reference design. */
const TIMEOUT_MS = 6000;

export type MemStatus = "active" | "archived";

/** Anything else (e.g. a typo) makes MemStatus(...) raise inside the backend, and /memories
 *  has no try/except — so it returns an unhandled 500, not a 422. Only send these three. */
export type StatusFilter = MemStatus | "all";

/** app/memory/models.py: Memory.as_dict(). */
export type Memory = {
  id: number;
  user_id: string;
  content: string;
  mem_type: string;
  /** Float on a 1-10 scale, NOT 0-1. The design's samples use 0-1; the engine does not. */
  importance: number;
  created_at: string;
  event_time: string | null;
  last_accessed: string | null;
  access_count: number;
  status: MemStatus;
  source: string | null;
  superseded_by: number | null;
};

/** Memory.as_dict() + decay_score, from MemoryEngine.list_memories. Returned as a bare array. */
export type StoredMemory = Memory & { decay_score: number };

export type RecallScores = {
  combined: number;
  semantic: number;
  keyword: number;
  recency: number;
  importance: number;
};

/** Memory.as_dict() + tokens + scores, from app/memory/retrieve.py. */
export type RecalledMemory = Memory & { tokens: number; scores: RecallScores };

export type RecallResult = {
  memories: RecalledMemory[];
  context: string;
  tokens_used: number;
  token_budget: number;
  /** Optional on purpose: the empty-candidate early return in retrieve.py omits this key
   *  entirely, so a cold user would KeyError anything that assumes it. */
  candidates_considered?: number;
};

/** Narrower than created[] — revise.py appends only these three fields. In particular there
 *  is no `replacement` text; resolveReplacement() below recovers it from created[]. */
export type SupersededMemory = {
  id: number;
  content: string;
  superseded_by: number;
};

/** Two shapes: {created, note} when nothing was worth extracting (no `superseded` key at
 *  all), or {created, superseded} on the normal path (no `note`). Both fields optional. */
export type RememberResult = {
  created?: Memory[];
  superseded?: SupersededMemory[];
  note?: string;
};

export type ForgetResult = {
  scanned: number;
  archived: number;
  archived_ids: number[];
};

/** Note the field names — consolidate.py returns clusters_found / memories_merged /
 *  semantic_created. There is no wrong_merges here; that figure exists only in the offline
 *  benchmark (see the note in MaintenanceTab). */
export type ReflectResult = {
  clusters_found: number;
  memories_merged: number;
  semantic_created: number;
  merged_ids: number[];
};

export type StatsResult = {
  total: number;
  by_status: Partial<Record<MemStatus, number>>;
  active_by_type: Record<string, number>;
};

export type HealthResult = { status: string; model?: string };

/** What every tab needs to make a call. Owned by DemoConsole, passed down. */
export type DemoSession = {
  base: string;
  userId: string;
  tokenBudget: number;
  /** False when the last health probe failed — tabs then serve sample data without
   *  attempting a request that is known to fail. */
  live: boolean;
};

/* -------------------------------------------------------------------------- */

function normalise(base: string): string {
  return (base || DEFAULT_BASE).replace(/\/+$/, "");
}

async function request<T>(
  base: string,
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(normalise(base) + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export function health(base: string) {
  return request<HealthResult>(base, "GET", "/health");
}

export function recall(base: string, user_id: string, query: string, token_budget: number) {
  return request<RecallResult>(base, "POST", "/recall", { user_id, query, token_budget });
}

export function remember(base: string, user_id: string, text: string) {
  return request<RememberResult>(base, "POST", "/remember", { user_id, text });
}

export function forget(base: string, user_id: string) {
  return request<ForgetResult>(base, "POST", "/forget", { user_id });
}

export function reflect(base: string, user_id: string) {
  return request<ReflectResult>(base, "POST", "/reflect", { user_id });
}

export function listMemories(base: string, user_id: string, status: StatusFilter = "all") {
  const qs = new URLSearchParams({ user_id, status, limit: "200" });
  return request<StoredMemory[]>(base, "GET", `/memories?${qs}`);
}

export function stats(base: string, user_id: string) {
  const qs = new URLSearchParams({ user_id });
  return request<StatsResult>(base, "GET", `/stats?${qs}`);
}

/* -------------------------------------------------------------------------- */

/**
 * The design shows each superseded memory struck through above the fact that replaced it, but
 * the API only hands back the replacing memory's id. Look it up in created[] from the same
 * response; fall back to the design's own wording when the id isn't among them (the
 * replacement can be a pre-existing memory, not one created by this call).
 */
export function resolveReplacement(
  superseded: SupersededMemory,
  created: Memory[],
): string {
  return (
    created.find((m) => m.id === superseded.superseded_by)?.content ??
    "the newly stored memory"
  );
}

/** Importance renders on the engine's 1-10 scale, so it must not be formatted like a 0-1
 *  probability. One decimal is enough to distinguish 7 from 7.5 without implying precision. */
export function formatImportance(v: number | null | undefined): string {
  return v == null ? "—" : v.toFixed(1);
}

export function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
