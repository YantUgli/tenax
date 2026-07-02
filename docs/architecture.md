# Mnemo Architecture

Export this diagram to `docs/architecture.png` (e.g. paste the Mermaid block into
<https://mermaid.live> and download PNG) and attach it to the Devpost submission.

## Component diagram (Mermaid)

```mermaid
flowchart TB
    subgraph Clients
        A[MCP client<br/>Claude Desktop / Qwen]
        B[Streamlit demo dashboard]
    end

    subgraph ECS["Alibaba Cloud ECS (Docker Compose)"]
        M[app/mcp_server.py<br/>MCP tools]
        R[app/main.py<br/>FastAPI REST]
        E[app/memory/engine.py]
        X[extract.py] --- E
        RE[retrieve.py] --- E
        F[forget.py] --- E
        C[consolidate.py] --- E
        M --> E
        R --> E
    end

    subgraph Qwen["Qwen Cloud (DashScope-intl, OpenAI-compatible)"]
        Q1[qwen-plus / qwen-turbo]
        Q2[text-embedding-v4]
    end

    DB[(PostgreSQL + pgvector<br/>vectors · metadata · full-text)]

    A -- MCP stdio --> M
    B -- REST --> R
    X -- extract & score --> Q1
    C -- distill --> Q1
    RE -- embed query --> Q2
    E -- store / query --> DB
```

## Memory lifecycle

1. **Write** — `remember(text)` → Qwen extracts salient, self-contained statements + type
   + importance → embed with `text-embedding-v4` → store in `memories`.
2. **Read** — `recall(query, budget)` → embed query → hybrid candidate generation
   (vector + full-text) → unified scoring (semantic + keyword + recency + importance) →
   budget-aware packing → reinforce accessed memories.
3. **Forget** — `forget()` → compute decay score per memory → archive those below threshold.
4. **Reflect** — `reflect()` → cluster near-duplicates → Qwen distills each cluster into
   canonical semantic facts → archive sources (`superseded_by`).
