/**
 * Fallback data for /demo when the backend is unreachable.
 *
 * The reference design carries these samples so the page is never blank, and that matters
 * here: if the ECS box is down while someone is looking at the demo, they should see the
 * shape of the thing rather than an error.
 *
 * Shapes conform to the real engine's schema, not the design's placeholder values — the same
 * components render both, so importance is on the engine's 1-10 scale and mem_type is drawn
 * from the actual MemType enum (episodic | semantic | procedural). A sample that rendered
 * differently from live data would be a misleading preview.
 *
 * The status chip always says "Sample data · offline" whenever these are in use, so nothing
 * here is ever mistaken for a live result.
 */
import type {
  ForgetResult,
  Memory,
  RecallResult,
  ReflectResult,
  RememberResult,
  StatsResult,
  StoredMemory,
} from "@/lib/tenax-api";

const USER = "demo";

function base(
  id: number,
  content: string,
  mem_type: string,
  importance: number,
  created_at: string,
): Memory {
  return {
    id,
    user_id: USER,
    content,
    mem_type,
    importance,
    created_at,
    event_time: null,
    last_accessed: null,
    access_count: 0,
    status: "active",
    source: null,
    superseded_by: null,
  };
}

/** Ranked by combined score, then greedily packed under the budget — the same order the real
 *  retriever produces, so the budget bar behaves identically. */
const RECALL_POOL = [
  {
    content: "Researching retrieval-augmented generation (RAG) for long-document QA.",
    tokens: 62,
    scores: { semantic: 0.91, keyword: 0.72, recency: 0.8, importance: 0.9, combined: 0.86 },
  },
  {
    content: "Prefers dense retrieval over the BM25 baseline.",
    tokens: 58,
    scores: { semantic: 0.77, keyword: 0.61, recency: 0.55, importance: 0.6, combined: 0.68 },
  },
  {
    content: "Advisor is Dr. Lin; weekly meeting on Thursdays.",
    tokens: 44,
    scores: { semantic: 0.68, keyword: 0.4, recency: 0.7, importance: 0.85, combined: 0.67 },
  },
  {
    content: "Uses text-embedding-v4 for the vector index.",
    tokens: 74,
    scores: { semantic: 0.6, keyword: 0.55, recency: 0.48, importance: 0.55, combined: 0.56 },
  },
  {
    content: "Paper deadline: EMNLP, May 2026.",
    tokens: 66,
    scores: { semantic: 0.52, keyword: 0.3, recency: 0.6, importance: 0.75, combined: 0.55 },
  },
];

export function sampleRecall(budget: number): RecallResult {
  const sorted = [...RECALL_POOL].sort((a, b) => b.scores.combined - a.scores.combined);

  const picked: typeof RECALL_POOL = [];
  let used = 0;
  for (const m of sorted) {
    if (used + m.tokens <= budget) {
      picked.push(m);
      used += m.tokens;
    }
  }

  const lines = ["# What you know about this user", ""];
  for (const m of picked) lines.push("- " + m.content);
  lines.push("");
  lines.push("PAST (superseded, do not use): Lived in Jakarta. → now: Lives in Singapore.");

  return {
    tokens_used: used,
    token_budget: budget,
    context: lines.join("\n"),
    candidates_considered: RECALL_POOL.length + 2,
    memories: picked.map((m, i) => ({
      ...base(100 + i, m.content, "semantic", 7, "2026-04-01"),
      tokens: m.tokens,
      scores: m.scores,
    })),
  };
}

export function sampleRemember(): RememberResult {
  return {
    created: [
      base(10, "Moved to Singapore for a postdoc.", "semantic", 8, "2026-05-02"),
      base(11, "Dr. Lin continues as advisor, now remotely.", "semantic", 7, "2026-05-02"),
    ],
    // superseded_by points at id 10 above, so the replacement text resolves through
    // resolveReplacement() exactly as it does on a live response.
    superseded: [{ id: 4, content: "Lived in Jakarta.", superseded_by: 10 }],
  };
}

export function sampleMemories(): StoredMemory[] {
  const rows: [number, string, string, number, number, number, string][] = [
    [1, "Researching retrieval-augmented generation (RAG) for long-document QA.", "semantic", 9, 0.94, 12, "2026-03-14"],
    [2, "Advisor is Dr. Lin; weekly meeting on Thursdays.", "semantic", 8.5, 0.88, 8, "2026-03-20"],
    [3, "Lives in Singapore (moved for a postdoc).", "semantic", 8, 0.91, 5, "2026-05-02"],
    [5, "Prefers dense retrieval over the BM25 baseline.", "semantic", 6, 0.71, 3, "2026-04-01"],
    [6, "Paper deadline: EMNLP, May 2026.", "semantic", 7.5, 0.66, 4, "2026-04-10"],
    [7, "Uses text-embedding-v4 for the vector index.", "procedural", 5.5, 0.58, 2, "2026-04-18"],
    [9, "Weekly reading group on Fridays.", "semantic", 5, 0.44, 2, "2026-04-22"],
  ];

  const active: StoredMemory[] = rows.map(([id, content, type, imp, decay, reads, at]) => ({
    ...base(id, content, type, imp, at),
    access_count: reads,
    decay_score: decay,
  }));

  return [
    ...active,
    {
      ...base(4, "Lived in Jakarta.", "semantic", 7, "2026-02-10"),
      access_count: 1,
      status: "archived",
      superseded_by: 3,
      decay_score: 0.12,
    },
    {
      ...base(8, "Was skimming a blog post about HyDE query expansion.", "episodic", 3, "2026-03-02"),
      access_count: 0,
      status: "archived",
      decay_score: 0.08,
    },
  ];
}

export function sampleStats(): StatsResult {
  return {
    total: 9,
    by_status: { active: 7, archived: 2 },
    active_by_type: { semantic: 6, procedural: 1 },
  };
}

export function sampleForget(): ForgetResult {
  return { scanned: 9, archived: 2, archived_ids: [4, 8] };
}

export function sampleReflect(): ReflectResult {
  return { clusters_found: 3, memories_merged: 2, semantic_created: 1, merged_ids: [5, 9] };
}

/** The two rows the sample forget sweep archives, shown fading out. */
export const SAMPLE_FADING = [
  "Lived in Jakarta.",
  "Was skimming a blog post about HyDE query expansion.",
];
