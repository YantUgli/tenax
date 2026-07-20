import { Card, Pill, Section } from "@/components/ui";

const CLIENTS = [
  {
    name: "Claude Desktop",
    how: "stdio",
    body: "Drop the config block into claude_desktop_config.json and the five tools appear in the client.",
    shipped: true,
  },
  {
    name: "Qwen desktop client",
    how: "stdio",
    body: "Same server, same config shape — Tenax does not special-case the client it is talking to.",
    shipped: true,
  },
  {
    name: "Any MCP client",
    how: "stdio",
    body: "Tenax implements the MCP tool protocol, so compatibility is at the protocol level rather than per-integration.",
    shipped: false,
  },
  {
    name: "Your own agent",
    how: "REST",
    body: "Seven endpoints (/remember, /recall, /forget, /reflect, /memories, /stats, /health) for anything that does not speak MCP.",
    shipped: true,
  },
];

export function Integrations() {
  return (
    <Section
      id="integrations"
      eyebrow="Works with"
      title="One server, no per-client adapters."
      lede={
        <>
          Memory should not be something you re-integrate for every agent you try. Tenax
          exposes its five skills through MCP, so any compatible client gets them without a
          bespoke plugin — and a REST API covers everything that speaks HTTP instead.
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {CLIENTS.map((c) => (
          <Card key={c.name}>
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-medium">{c.name}</h3>
              <Pill tone={c.how === "REST" ? "plain" : "accent"}>{c.how}</Pill>
            </div>
            <p className="mt-2.5 text-sm leading-relaxed text-muted">{c.body}</p>
          </Card>
        ))}
      </div>

      {/* Being explicit about the boundary is worth more than an inflated logo wall. */}
      <Card className="mt-5 border-border">
        <h4 className="text-sm font-medium">What is and isn&rsquo;t true today</h4>
        <ul className="mt-3 space-y-2 text-sm leading-relaxed text-muted">
          <li>
            <span className="text-foreground">stdio is the only MCP transport.</span> There
            is no hosted HTTP or SSE MCP endpoint — you run the server next to your agent.
          </li>
          <li>
            <span className="text-foreground">
              Compatibility is protocol-level, not a per-client integration list.
            </span>{" "}
            The configs shipped in the repo are for Claude Desktop and Qwen clients; other
            MCP clients should work, but we only claim what we ship.
          </li>
          <li>
            <span className="text-foreground">It needs Postgres with pgvector</span> and a
            Qwen Cloud API key. Both are set up by the quickstart below.
          </li>
        </ul>
      </Card>
    </Section>
  );
}
