import { benchmark } from "@/lib/data";

export function Hero() {
  const h = benchmark.headline;
  return (
    <div id="top" className="mx-auto w-full max-w-6xl px-5 pb-16 pt-10 sm:px-8 sm:pt-14">
      <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 font-mono text-[11px] text-muted">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        Global AI Hackathon with Qwen Cloud · Track 1: MemoryAgent
      </div>

      <h1 className="mt-7 max-w-4xl text-balance text-4xl font-semibold leading-[1.08] tracking-tight sm:text-6xl">
        Persistent memory for AI agents,
        <span className="text-accent"> that manages itself.</span>
      </h1>

      <p className="mt-6 max-w-2xl text-pretty text-lg leading-relaxed text-muted">
        Tenax is an MCP server that gives any compatible agent long-term memory across
        sessions. It decides what is worth keeping, retrieves the right facts inside a strict
        token budget, revises beliefs when the world changes, and lets the rest fade — all
        running on Qwen Cloud.
      </p>

      <div className="mt-9 flex flex-wrap items-center gap-3">
        <a
          href="#mcp"
          className="rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-[#07090d] transition-opacity hover:opacity-90"
        >
          Add to your agent
        </a>
        <a
          href="#demo"
          className="rounded-lg border border-border px-5 py-2.5 text-sm font-medium text-foreground transition-colors hover:border-accent/40"
        >
          Watch a real session
        </a>
      </div>

      <dl className="mt-11 grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-3">
        <HeroStat
          value={`${h.retrieval_hit_rate}%`}
          label="Retrieval hit rate"
          sub={`LongMemEval oracle, ${benchmark.accuracy.reader_upgrade.n} questions — the evidence was in context every time.`}
        />
        <HeroStat
          value={`${h.temporal_before}% → ${h.temporal_after}%`}
          label="Temporal reasoning"
          sub="After giving every memory a validity anchor (event_time), n=13."
        />
        <HeroStat
          value={`~${h.avg_tokens_per_query}`}
          label="Tokens per query"
          sub={`Packed against a ${h.token_budget}-token ceiling, not dumped whole.`}
        />
      </dl>
    </div>
  );
}

function HeroStat({ value, label, sub }: { value: string; label: string; sub: string }) {
  return (
    <div className="bg-surface px-6 py-7">
      <dd className="whitespace-nowrap font-mono text-xl font-semibold tabular-nums text-accent sm:text-2xl">
        {value}
      </dd>
      <dt className="mt-2 text-sm font-medium">{label}</dt>
      <p className="mt-1.5 text-xs leading-relaxed text-muted">{sub}</p>
    </div>
  );
}
