import { Hero } from "@/components/Hero";
import { Nav } from "@/components/Nav";
import { Problem } from "@/components/Problem";
import { HowItWorks } from "@/components/HowItWorks";
import { Replay } from "@/components/Replay";
import { Benchmark } from "@/components/Benchmark";
import { Integrations } from "@/components/Integrations";
import { Mcp } from "@/components/Mcp";
import { TenaxMark } from "@/components/ui";
import { benchmark } from "@/lib/data";

export default function Home() {
  return (
    <>
      <Nav />
      <main className="flex-1">
        <Hero />
        <Problem />
        <HowItWorks />
        <Replay />
        <Benchmark />
        <Integrations />
        <Mcp />
      </main>
      <Footer />
    </>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border py-12">
      <div className="mx-auto w-full max-w-6xl px-5 sm:px-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <TenaxMark className="size-4 text-accent" />
              <span className="font-mono text-base font-semibold">Tenax</span>
            </div>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
              Latin <em>tenax</em> — &ldquo;holding fast&rdquo;, as in{" "}
              <em>memoria tenax</em>. Built for the Global AI Hackathon with Qwen Cloud,
              Track 1: MemoryAgent.
            </p>
          </div>
          <div className="font-mono text-xs leading-relaxed text-muted">
            <div>{benchmark.runtime.provider}</div>
            <div className="mt-1">
              {benchmark.runtime.extract_model} · {benchmark.runtime.embed_model}
            </div>
            <div className="mt-1">PostgreSQL + pgvector</div>
            <a
              href="https://github.com/YantUgli/tenax"
              className="mt-3 inline-block text-link hover:underline"
            >
              github.com/YantUgli/tenax
            </a>
          </div>
        </div>
        <p className="mt-8 border-t border-border pt-6 font-mono text-[11px] text-muted">
          MIT licensed. Benchmark figures measured {benchmark.measured_on}; raw records in{" "}
          <code>benchmark/results/</code>.
        </p>
      </div>
    </footer>
  );
}
