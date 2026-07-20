/**
 * Typed access to the baked-in data.
 *
 * Both JSON files are generated, never hand-edited:
 *   benchmark.json  <- scripts/export_web_data.py   (from benchmark/results/*.summary.json)
 *   replay.json     <- scripts/record_replay.py     (verbatim capture of a live engine run)
 */
import benchmarkJson from "@/data/benchmark.json";
import replayJson from "@/data/replay.json";

export type CategoryScore = {
  category: string;
  n: number;
  accuracy: number | null;
};

export type AccuracyRun = {
  label: string;
  n: number;
  overall: number;
  per_category?: CategoryScore[];
  scope?: string;
};

export type Benchmark = {
  measured_on: string;
  runtime: {
    provider: string;
    extract_model: string;
    embed_model: string;
    reader_model: string;
  };
  headline: {
    retrieval_hit_rate: number;
    temporal_before: number;
    temporal_after: number;
    avg_tokens_per_query: number;
    token_budget: number;
  };
  accuracy: {
    baseline: AccuracyRun;
    reader_upgrade: AccuracyRun;
    temporal_fix: AccuracyRun;
    projected_overall: { value: number; measured: boolean; note: string };
  };
  no_regression: { n: number; overall: number; claim: string };
  retrieval: {
    hybrid_hits: number;
    hybrid_total: number;
    recency_hits: number;
    recency_total: number;
    budget_tokens: number;
    n_distractors: number;
  };
  belief_revision: {
    updates_applied: number;
    n_updates: number;
    traps_passed: number;
    n_traps: number;
    wrong_supersedes: number;
  };
  staleness: {
    cycles: number;
    accessed_survived: number;
    important_total: number;
    wrong_merges: number;
    dormant_survived: number;
  };
  sources: { artifact: string; command: string; what: string }[];
};

export type MemoryRow = {
  id: number;
  content: string;
  mem_type: string;
  importance: number;
  status: string;
  decay_score: number;
  access_count: number;
  superseded_by: number | null;
  created_at: string;
};

export type RecalledMemory = {
  content: string;
  tokens: number;
  scores: Record<string, number>;
};

export type ReplayStep = {
  step: number;
  act: "remember" | "recall" | "list_memories" | "forget" | "reflect";
  caption: string;
  note?: string;
  label?: string;
  text?: string;
  query?: string;
  at?: string;
  age_days?: number;
  token_budget?: number;
  highlight?: string;
  // Shape depends on `act`; narrowed at the point of use.
  response: any; // eslint-disable-line @typescript-eslint/no-explicit-any
};

export type Replay = {
  recorded_at: string;
  user_id: string;
  runtime: Record<string, string>;
  note: string;
  steps: ReplayStep[];
};

export const benchmark = benchmarkJson as Benchmark;
export const replay = replayJson as unknown as Replay;

/** Pretty category label: "single-session-user" -> "Single-session user". */
export function prettyCategory(key: string): string {
  const s = key.replace(/-/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
