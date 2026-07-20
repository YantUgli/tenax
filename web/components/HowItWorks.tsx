import { Section } from "@/components/ui";
import { benchmark } from "@/lib/data";

const STAGES = [
  {
    tool: "remember",
    title: "Extract, don't log",
    body: "Qwen turns raw turns into distilled, self-contained facts with a type and an importance score. Chat logs are not memories.",
    detail: "extract.py · qwen-turbo",
  },
  {
    tool: "remember",
    title: "Revise beliefs at write time",
    body: "A new fact that genuinely contradicts a stored one archives it with a superseded_by pointer — instead of leaving both versions to fight in the prompt.",
    detail: "revise.py · qwen-turbo",
  },
  {
    tool: "recall",
    title: "Retrieve hybrid, pack to budget",
    body: "Vector similarity + Postgres full-text + recency + importance produce one score; MMR packs the highest-value non-redundant set into the token ceiling.",
    detail: "retrieve.py · text-embedding-v4",
  },
  {
    tool: "forget",
    title: "Let the rest fade",
    body: "An Ebbinghaus-style decay score — importance · e^(−Δt/τ) · (1 + ln(1+accesses)) — drives a sweep that archives what stopped earning its place. Recall reinforces what it returns.",
    detail: "forget.py · no LLM call",
  },
  {
    tool: "reflect",
    title: "Consolidate what's left",
    body: "Near-duplicates are clustered and distilled into canonical facts, shrinking the store and sharpening precision.",
    detail: "consolidate.py · qwen-turbo",
  },
];

export function HowItWorks() {
  const rt = benchmark.runtime;
  return (
    <Section
      id="how"
      eyebrow="How it works"
      title="Five skills, one self-managing loop."
      lede="Tenax is not a vector store with a nice wrapper. Each write and each read triggers maintenance, so the store stays small, current, and non-contradictory without anyone curating it."
    >
      <ol className="relative space-y-3 border-l border-border pl-6 sm:pl-8">
        {STAGES.map((s, i) => (
          <li key={i} className="relative">
            <span className="absolute -left-[31px] top-6 h-2.5 w-2.5 rounded-full bg-accent ring-4 ring-background sm:-left-[39px]" />
            <div className="rounded-xl border border-border bg-surface p-5 sm:p-6">
              <div className="flex flex-wrap items-center gap-3">
                <code className="rounded-md bg-accent/10 px-2 py-0.5 font-mono text-xs text-accent">
                  {s.tool}()
                </code>
                <h3 className="font-medium">{s.title}</h3>
              </div>
              <p className="mt-2.5 text-sm leading-relaxed text-muted">{s.body}</p>
              <p className="mt-3 font-mono text-[11px] text-muted/70">{s.detail}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="mt-10 grid gap-5 sm:grid-cols-3">
        <StackCard
          label="Reasoning"
          value={`${rt.extract_model} · ${rt.reader_model}`}
          note={rt.provider}
        />
        <StackCard label="Embeddings" value={rt.embed_model} note="1024-dim, Qwen Cloud" />
        <StackCard
          label="Store"
          value="PostgreSQL + pgvector"
          note="vectors · metadata · full-text, one database"
        />
      </div>
    </Section>
  );
}

function StackCard({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface px-5 py-5">
      <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">
        {label}
      </div>
      <div className="mt-2 font-mono text-sm text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted">{note}</div>
    </div>
  );
}
