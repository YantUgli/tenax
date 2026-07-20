import { benchmark } from "@/lib/data";
import { Provenance, Section } from "@/components/ui";

/**
 * The haystack: 6 important facts buried under 30 recent distractors, identical in both
 * panels. Filled cells are what actually made it into the token budget.
 */
function Haystack({ variant }: { variant: "recency" | "hybrid" }) {
  // 30 distractors + 6 planted facts, matching the benchmark exactly.
  const cells = Array.from({ length: 36 }, (_, i) => i);
  // Fixed positions so both panels show the same haystack. These must scatter across the
  // 12 columns (a regular pattern reads as ornament) and must NOT overlap `newest` — an
  // important fact counted as retrieved would contradict the 0/6 label above the panel.
  const important = new Set([3, 8, 13, 19, 24, 29]);
  // Recency-only spends the whole budget on the six newest items.
  const newest = new Set([30, 31, 32, 33, 34, 35]);

  return (
    <div className="grid max-w-[19rem] grid-cols-12 gap-1" aria-hidden>
      {cells.map((i) => {
        const isImportant = important.has(i);
        const selected =
          variant === "hybrid" ? isImportant : newest.has(i);
        const missedImportant = isImportant && !selected;

        return (
          <div
            key={i}
            className={[
              "aspect-square rounded-[2px]",
              selected
                ? variant === "hybrid"
                  ? "bg-good"
                  : "bg-muted"
                : missedImportant
                  ? "border border-bad/70 bg-bad/20"
                  : "bg-surface-2",
            ].join(" ")}
          />
        );
      })}
    </div>
  );
}

function Legend({ variant }: { variant: "recency" | "hybrid" }) {
  return (
    <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 font-mono text-[11px] text-muted">
      <span className="flex items-center gap-1.5">
        <span
          className={`h-2.5 w-2.5 rounded-[2px] ${variant === "hybrid" ? "bg-good" : "bg-muted"}`}
        />
        in context
      </span>
      {variant === "recency" ? (
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[2px] border border-bad/70 bg-bad/20" />
          important, missed
        </span>
      ) : null}
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[2px] bg-surface-2" />
        distractor
      </span>
    </div>
  );
}

export function Problem() {
  const r = benchmark.retrieval;
  return (
    <Section
      id="problem"
      eyebrow="The problem"
      title="An agent that forgets is an agent you have to repeat yourself to."
      lede={
        <>
          Most memory layers are a chat log with a similarity search bolted on. They keep
          everything, rank by recency, and pour whatever fits into the prompt. That fails in
          the exact moment memory is supposed to matter: when the fact you need is old,
          important, and buried under a week of noise.
        </>
      }
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-xl border border-bad/25 bg-surface p-6">
          <div className="flex items-baseline justify-between">
            <h3 className="font-medium">Recency-only retrieval</h3>
            <span className="font-mono text-2xl font-semibold tabular-nums text-bad">
              {r.recency_hits}/{r.recency_total}
            </span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            The budget fills with whatever happened most recently. Every important older fact
            is missed — not ranked low, missed entirely.
          </p>
          <div className="mt-6">
            <Haystack variant="recency" />
            <Legend variant="recency" />
          </div>
        </div>

        <div className="rounded-xl border border-good/25 bg-surface p-6">
          <div className="flex items-baseline justify-between">
            <h3 className="font-medium">Tenax hybrid retrieval</h3>
            <span className="font-mono text-2xl font-semibold tabular-nums text-good">
              {r.hybrid_hits}/{r.hybrid_total}
            </span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Dense vectors + full-text + recency + importance, packed to the same ceiling.
            Every buried fact surfaces, within the identical token budget.
          </p>
          <div className="mt-6">
            <Haystack variant="hybrid" />
            <Legend variant="hybrid" />
          </div>
        </div>
      </div>

      <Provenance>
        {r.n_distractors} distractors, {r.hybrid_total} planted facts, {r.budget_tokens}-token
        budget for both arms · <code>benchmark/results/hybrid_vs_naive.summary.json</code> ·
        reproduce with <code>python -m benchmark.run --reset --budget {r.budget_tokens}</code>
      </Provenance>
    </Section>
  );
}
