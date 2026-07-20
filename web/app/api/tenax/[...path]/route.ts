import { NextResponse } from "next/server";

/**
 * Same-origin proxy to the Tenax FastAPI backend.
 *
 * This exists to solve three problems at once, all of which block the browser from calling the
 * backend directly:
 *
 *   1. app/main.py installs no CORS middleware, so a cross-origin XHR is refused outright.
 *   2. infra/DEPLOY.md publishes the API as plain http://<ECS_IP>:8000 with no TLS, so an
 *      https-served page cannot reach it at all — the browser blocks it as mixed content.
 *   3. The backend URL then has to be baked into client JS, which pins the deployment.
 *
 * Proxying server-side makes the request same-origin (1 and 2 evaporate) and moves the http
 * hop out of the browser, where the mixed-content rule does not apply. TENAX_API_URL is read
 * per-request at runtime, so the same build works against any backend.
 */

const BACKEND = (process.env.TENAX_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/**
 * The backend has no authentication, no API key and no rate limiting, and /remember, /recall
 * and /reflect each spend Qwen Cloud credits. An open proxy to an arbitrary path on an
 * internal host is not something to expose, so only the routes the demo actually calls are
 * forwarded. Anything else 404s here without a request leaving this process.
 */
const GET_PATHS = new Set(["health", "memories", "stats"]);
const POST_PATHS = new Set(["remember", "recall", "forget", "reflect"]);

// Above the client's own 6s abort, so a slow backend surfaces as the client's timeout (which
// degrades to sample data) rather than as a proxy error the client has to interpret.
const TIMEOUT_MS = 15_000;

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: Request, ctx: Ctx) {
  return proxy(req, ctx, "GET", GET_PATHS);
}

export async function POST(req: Request, ctx: Ctx) {
  return proxy(req, ctx, "POST", POST_PATHS);
}

async function proxy(req: Request, ctx: Ctx, method: "GET" | "POST", allowed: Set<string>) {
  const { path } = await ctx.params;

  // Single-segment only: every backend route is flat, so a multi-segment path is either a
  // mistake or a traversal attempt. Checking the joined form would let "health/../../x" pass.
  if (path.length !== 1 || !allowed.has(path[0])) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  // Query string passes through verbatim: /memories and /stats are query-param based.
  const search = new URL(req.url).search;
  const url = `${BACKEND}/${path[0]}${search}`;

  try {
    const upstream = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: method === "POST" ? await req.text() : undefined,
      signal: AbortSignal.timeout(TIMEOUT_MS),
      cache: "no-store",
    });

    // Forwarded as-is, status included. The client treats any non-2xx as "backend unavailable"
    // and falls back to sample data, so an upstream 500 degrades rather than breaking the page.
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("Content-Type") ?? "application/json" },
    });
  } catch (err) {
    // Unreachable backend, DNS failure, or our own timeout. 502 keeps it distinguishable from
    // the 404 above, but the client's handling is the same either way.
    const detail = err instanceof Error ? err.message : "Upstream request failed";
    return NextResponse.json({ detail }, { status: 502 });
  }
}
