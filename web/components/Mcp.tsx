"use client";

import { useState } from "react";
import { Section } from "@/components/ui";

const CONFIG = `{
  "mcpServers": {
    "tenax": {
      "command": "pipenv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/Qwen-Hackathon",
      "env": {
        "QWEN_API_KEY": "sk-...",
        "DATABASE_URL": "postgresql+psycopg://tenax:tenax@localhost:5432/tenax"
      }
    }
  }
}`;

const QUICKSTART = `git clone https://github.com/YantUgli/Qwen-Hackathon
cd Qwen-Hackathon
pipenv install
cp .env.example .env          # add your QWEN_API_KEY

docker compose up -d db       # Postgres + pgvector
pipenv run python -m scripts.init_db
pipenv run python -m app.mcp_server   # stdio transport`;

const TOOLS = [
  {
    sig: "remember(text, user_id?, source?)",
    body: "Extracts durable facts from an interaction, embeds them, and applies belief revision against what is already stored.",
    returns: "{ created: [...], superseded: [...] }",
  },
  {
    sig: "recall(query, user_id?, token_budget?)",
    body: "Hybrid retrieval packed to the budget. Returns an assembled context string, ready to paste into a prompt.",
    returns: "{ context, tokens_used, memories: [{ id, content, score }] }",
  },
  {
    sig: "forget(user_id?)",
    body: "Runs the decay sweep and archives memories that fell below the retention threshold.",
    returns: "{ scanned, archived, archived_ids }",
  },
  {
    sig: "reflect(user_id?)",
    body: "Clusters near-duplicates and distills each cluster into one canonical semantic fact.",
    returns: "{ clusters_found, memories_merged, semantic_created, merged_ids }",
  },
  {
    sig: "list_memories(user_id?, status?, limit?)",
    body: "Inspect the store, including live decay scores and supersession pointers.",
    returns: "Memory[]",
  },
];

export function Mcp() {
  return (
    <Section
      id="mcp"
      eyebrow="Install"
      title="It's an MCP server. Point your agent at it."
      lede={
        <>
          Tenax speaks MCP over stdio, so any compatible client — Claude Desktop, a Qwen
          client, your own agent — gets five memory tools with no bespoke integration. A REST
          API ships alongside it for dashboards and cloud deployment.
        </>
      }
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <CodeBlock title="claude_desktop_config.json" code={CONFIG} lang="json" />
        <CodeBlock title="Run it locally" code={QUICKSTART} lang="bash" />
      </div>

      <h3 className="mt-14 text-lg font-medium">The five tools</h3>
      <div className="mt-6 space-y-3">
        {TOOLS.map((t) => (
          <div
            key={t.sig}
            className="rounded-xl border border-border bg-surface p-5 transition-colors hover:border-accent/25"
          >
            <code className="font-mono text-sm text-accent">{t.sig}</code>
            <p className="mt-2.5 text-sm leading-relaxed text-muted">{t.body}</p>
            <code className="mt-3 block font-mono text-[11px] text-muted/70">
              → {t.returns}
            </code>
          </div>
        ))}
      </div>
    </Section>
  );
}

function CodeBlock({
  title,
  code,
  lang,
}: {
  title: string;
  code: string;
  lang: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard can be blocked; the code is selectable either way.
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border bg-surface-2 px-4 py-2.5">
        <span className="font-mono text-[11px] text-muted">{title}</span>
        <button
          onClick={copy}
          className="rounded-md border border-border px-2.5 py-1 font-mono text-[11px] text-muted transition-colors hover:text-foreground"
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      {/* Wrap rather than scroll: a horizontal scrollbar that clips DATABASE_URL mid-string
          reads as a broken layout, and these snippets are meant to be copied anyway. */}
      <pre className="whitespace-pre-wrap break-words p-4 font-mono text-[11.5px] leading-relaxed">
        <code data-lang={lang}>{code}</code>
      </pre>
    </div>
  );
}
