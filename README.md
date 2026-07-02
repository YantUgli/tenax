# 🧠 Mnemo — Persistent Memory for AI Agents, powered by Qwen Cloud

> **Global AI Hackathon Series with Qwen Cloud — Track 1: MemoryAgent**

Mnemo is a **self-managing, persistent memory layer** that any MCP-compatible agent can
plug into. It gives an agent long-term memory across sessions: it decides what is worth
remembering, retrieves the right memories within a tight token budget, forgets stale
information, and periodically consolidates duplicates into canonical facts — all powered
by **Qwen Cloud** (Qwen chat models + `text-embedding-v4`).

It ships as **both an MCP server** (drop it into Claude Desktop / a Qwen client) **and a
REST API** (for the demo UI and cloud deployment).

---

## Why this design wins Track 1

Track 1 rewards three behaviours; Mnemo answers each directly:

| Track-1 goal | How Mnemo does it |
|---|---|
| Efficient storage & retrieval | Qwen extracts **distilled, self-contained** memories (not raw turns); **hybrid retrieval** = dense embeddings + Postgres full-text + recency + importance |
| Forgetting stale info | An **Ebbinghaus-style decay score** (`importance · e^(-Δt/τ) · (1+ln(1+accesses))`) drives a sweep that archives low-value memories; access reinforces retention |
| Recall in a limited context window | **Budget-aware selection**: greedily pack the highest-relevance memories that fit a token budget |

Plus a reflection/**consolidation** skill that clusters near-duplicates and asks Qwen to
distill them into canonical facts — shrinking storage and sharpening precision.

## Architecture

```
        MCP client (Claude/Qwen)         Streamlit demo dashboard
                 │ MCP (stdio)                    │ REST
                 ▼                                ▼
   ┌───────────────────────────────────────────────────────────┐
   │  FastAPI + MCP server   (Alibaba Cloud ECS, Docker Compose) │
   │   app/mcp_server.py   →   app/memory/engine.py              │
   │        ├─ extract.py       (Qwen: what to remember)         │
   │        ├─ retrieve.py      (hybrid + budget-aware recall)   │
   │        ├─ forget.py        (decay + sweep)                  │
   │        └─ consolidate.py   (Qwen: reflection/distillation)  │
   └───────────┬───────────────────────────────┬───────────────┘
               │ Qwen Cloud (DashScope-intl)    │ SQLAlchemy
               ▼                                ▼
     qwen-plus / qwen-turbo            PostgreSQL + pgvector
     text-embedding-v4                 (vectors + metadata + FTS)
```

See [docs/architecture.md](docs/architecture.md) (export a PNG from there for the submission).

## Where Qwen Cloud is used (for judging / deployment proof)

All Qwen Cloud calls go through [app/qwen_client.py](app/qwen_client.py) (OpenAI-compatible
client pointed at `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`):

- **`qwen-plus`** — memory extraction ([app/memory/extract.py](app/memory/extract.py)) and consolidation ([app/memory/consolidate.py](app/memory/consolidate.py))
- **`text-embedding-v4`** — embeddings for storage & retrieval ([app/memory/retrieve.py](app/memory/retrieve.py))

## Quickstart (local)

```bash
# 1. install deps (pipenv)
pipenv install

# 2. configure
cp .env.example .env      # add your QWEN_API_KEY

# 3. verify Qwen Cloud works
pipenv run python -m scripts.first_call

# 4. start Postgres+pgvector and the API
docker compose up -d db
pipenv run python -m scripts.init_db
pipenv run uvicorn app.main:app --reload

# 5. open the demo
pipenv run streamlit run demo/app.py
```

Or run the whole stack in containers: `docker compose up --build`.

## Use as an MCP server

```bash
pipenv run python -m app.mcp_server        # stdio transport
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mnemo": {
      "command": "pipenv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/Qwen-Hackathon",
      "env": { "QWEN_API_KEY": "sk-...", "DATABASE_URL": "postgresql+psycopg://mnemo:mnemo@localhost:5432/mnemo" }
    }
  }
}
```

Tools exposed: `remember`, `recall`, `forget`, `reflect`, `list_memories`.

## REST API

| Method | Path | Body / params |
|---|---|---|
| GET | `/health` | — |
| POST | `/remember` | `{user_id, text, source?}` |
| POST | `/recall` | `{user_id, query, token_budget?}` |
| POST | `/forget` | `{user_id, threshold?}` |
| POST | `/reflect` | `{user_id, threshold?}` |
| GET | `/memories` | `?user_id=&status=active|archived|all&limit=` |
| GET | `/stats` | `?user_id=` |

## Benchmark

Quantifies hybrid + budget-aware recall vs a naive recency-only baseline:

```bash
pipenv run python -m benchmark.run --reset --budget 400
```

## Deploy to Alibaba Cloud

See [infra/DEPLOY.md](infra/DEPLOY.md) — Docker Compose on an ECS instance (satisfies the
hackathon's "backend running on Alibaba Cloud" requirement).

## License

[MIT](LICENSE).
