import { benchmark, prettyCategory } from "@/lib/data";
import { Card, Pill, Provenance, Section, Stat } from "@/components/ui";

export function Benchmark() {
  const a = benchmark.accuracy;
  const base = a.baseline;
  const plus = a.reader_upgrade;
  const cats = base.per_category ?? [];
  const plusByCat = new Map((plus.per_category ?? []).map((c) => [c.category, c]));

  return (
    <Section
      id="benchmark"
      eyebrow="Measured, not claimed"
      title="Every number here comes from a run you can reproduce."
      lede={
        <>
          Evaluated on LongMemEval against Qwen Cloud. Raw records live in{" "}
          <code className="font-mono text-sm">benchmark/results/</code>, and the site reads
          those files directly — so nothing on this page can drift from the artifacts.
        </>
      }
    >
      {/* Headline grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          value={`${benchmark.headline.retrieval_hit_rate}%`}
          label="Retrieval hit rate"
          sub={`n=${plus.n}. The right evidence reached the reader every single time.`}
          tone="good"
        />
        <Stat
          value={`${base.overall}% → ${plus.overall}%`}
          label="End-to-end accuracy"
          sub={`Same memory engine, reader swapped ${base.label} → ${plus.label}.`}
        />
        <Stat
          value={`${a.temporal_fix.overall}%`}
          label="Temporal reasoning"
          sub={`Up from ${benchmark.headline.temporal_before}%, after event_time validity anchors. n=${a.temporal_fix.n}.`}
        />
        <Stat
          value={`${benchmark.no_regression.overall}%`}
          label="Non-temporal control"
          sub={`n=${benchmark.no_regression.n}. The temporal change cost nothing elsewhere.`}
          tone="good"
        />
      </div>

      {/* Honest framing of the projection */}
      <Card className="mt-5 border-accent/25">
        <div className="flex flex-wrap items-center gap-3">
          <Pill tone="accent">projection, not a measurement</Pill>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-muted">
          Substituting the separately measured {a.temporal_fix.overall}% temporal subset into
          the {plus.n}-item run projects{" "}
          <span className="font-mono font-semibold text-accent">
            ~{a.projected_overall.value}%
          </span>{" "}
          overall. We report it as a projection because it was never produced by one
          end-to-end run — the measured overall figure remains{" "}
          <span className="font-mono text-foreground">{plus.overall}%</span>.
        </p>
      </Card>

      {/* Per-category */}
      <h3 className="mt-14 text-lg font-medium">Where the gains came from</h3>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
        Retrieval was already saturated, so the remaining headroom was on the reasoning side.
        Swapping the reader lifted every weak category without touching the memory engine.
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-surface-2 text-left">
              <th className="px-4 py-3 font-medium">Category</th>
              <th className="px-4 py-3 text-right font-mono text-xs font-medium text-muted">
                n
              </th>
              <th className="px-4 py-3 font-medium">{base.label}</th>
              <th className="px-4 py-3 font-medium">{plus.label}</th>
            </tr>
          </thead>
          <tbody>
            {cats.map((c) => {
              const after = plusByCat.get(c.category);
              return (
                <tr key={c.category} className="border-b border-border/60 last:border-0">
                  <td className="px-4 py-3">{prettyCategory(c.category)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-muted">
                    {c.n}
                  </td>
                  <td className="px-4 py-3">
                    <Bar value={c.accuracy ?? 0} tone="muted" />
                  </td>
                  <td className="px-4 py-3">
                    <Bar
                      value={after?.accuracy ?? 0}
                      tone={
                        (after?.accuracy ?? 0) > (c.accuracy ?? 0) ? "good" : "accent"
                      }
                    />
                  </td>
                </tr>
              );
            })}
            <tr className="bg-surface-2">
              <td className="px-4 py-3 font-medium">Overall</td>
              <td className="px-4 py-3 text-right font-mono text-xs text-muted">
                {base.n}
              </td>
              <td className="px-4 py-3">
                <Bar value={base.overall} tone="muted" />
              </td>
              <td className="px-4 py-3">
                <Bar value={plus.overall} tone="good" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Provenance>
        <code>baseline_oracle.summary.json</code> ·{" "}
        <code>qwen37plus_sample50.summary.json</code> · LongMemEval oracle set, budget{" "}
        {benchmark.headline.token_budget} tokens
      </Provenance>

      {/* Safety properties */}
      <h3 className="mt-14 text-lg font-medium">The parts that are easy to get wrong</h3>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
        A memory that updates beliefs can corrupt them, and a memory that forgets can drop
        something load-bearing. Both were measured for false positives, not just for recall.
      </p>
      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <Card>
          <h4 className="font-medium">Belief revision</h4>
          <div className="mt-4 space-y-2.5 text-sm">
            <Row
              label="Genuine updates applied"
              value={`${benchmark.belief_revision.updates_applied}/${benchmark.belief_revision.n_updates}`}
              good
            />
            <Row
              label="Trap facts left untouched"
              value={`${benchmark.belief_revision.traps_passed}/${benchmark.belief_revision.n_traps}`}
              good
            />
            <Row
              label="Wrong supersedes"
              value={`${benchmark.belief_revision.wrong_supersedes}`}
              good
            />
          </div>
          <p className="mt-4 text-xs leading-relaxed text-muted">
            Traps are facts that merely look similar. Superseding one would mean silently
            destroying a true memory — so the count that matters is the zero.
          </p>
          <Provenance>
            <code>update.summary.json</code> · <code>python -m benchmark.update</code>
          </Provenance>
        </Card>

        <Card>
          <h4 className="font-medium">
            Staleness, {benchmark.staleness.cycles} forget/reflect cycles
          </h4>
          <div className="mt-4 space-y-2.5 text-sm">
            <Row
              label="Actively-used facts surviving"
              value={`${benchmark.staleness.accessed_survived}/${benchmark.staleness.important_total}`}
              good
            />
            <Row
              label="Wrong merges"
              value={`${benchmark.staleness.wrong_merges}`}
              good
            />
            <Row
              label="Dormant facts surviving"
              value={`${benchmark.staleness.dormant_survived}/${benchmark.staleness.important_total}`}
            />
          </div>
          <p className="mt-4 text-xs leading-relaxed text-muted">
            The last row is the design working as intended, not a failure: memories that are
            never accessed are meant to fade. Access is what buys retention.
          </p>
          <Provenance>
            <code>staleness.summary.json</code> · <code>python -m benchmark.staleness</code>
          </Provenance>
        </Card>
      </div>

      {/* Provenance table */}
      <details className="mt-10 rounded-xl border border-border bg-surface p-5">
        <summary className="cursor-pointer text-sm font-medium">
          Every artifact behind these numbers
        </summary>
        <ul className="mt-4 space-y-2.5">
          {benchmark.sources.map((s) => (
            <li key={s.artifact} className="text-xs leading-relaxed">
              <code className="font-mono text-link">{s.artifact}</code>
              <span className="text-muted"> — {s.what}</span>
            </li>
          ))}
        </ul>
        <p className="mt-4 font-mono text-[11px] text-muted">
          Measured {benchmark.measured_on} on {benchmark.runtime.provider}.
        </p>
      </details>
    </Section>
  );
}

function Bar({ value, tone }: { value: number; tone: "muted" | "good" | "accent" }) {
  const color =
    tone === "good" ? "bg-good" : tone === "accent" ? "bg-accent" : "bg-muted/50";
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-1.5 w-full max-w-[7rem] overflow-hidden rounded-full bg-surface-2">
        <div className={`h-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className="w-12 shrink-0 font-mono text-xs tabular-nums text-muted">
        {value}%
      </span>
    </div>
  );
}

function Row({
  label,
  value,
  good = false,
}: {
  label: string;
  value: string;
  good?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/50 pb-2 last:border-0">
      <span className="text-muted">{label}</span>
      <span
        className={`font-mono font-semibold tabular-nums ${good ? "text-good" : "text-foreground"}`}
      >
        {value}
      </span>
    </div>
  );
}
