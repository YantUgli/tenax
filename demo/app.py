"""Tenax demo dashboard (Streamlit).

Talks to the Tenax REST backend so the same UI works locally and against the
Alibaba Cloud deployment. Run:  pipenv run streamlit run demo/app.py
"""
from __future__ import annotations

import os

import httpx
import pandas as pd
import streamlit as st

API = os.getenv("TENAX_API", "http://localhost:8000")

# Design tokens, mirroring web/app/globals.css. The palette proper is set in
# .streamlit/config.toml; these are here for the handful of elements Streamlit's theme does
# not reach (panel borders, the eyebrow, mono technical lines).
ACCENT = "#f5b544"
SURFACE = "#0e1219"
BORDER = "#1f2733"
MUTED = "#8b97a8"

st.set_page_config(page_title="Tenax — persistent memory for AI agents", layout="wide")

# Deliberately small. Streamlit's own dark theme already carries the palette from
# config.toml; this only adds what that cannot express — the accent eyebrow, panel borders on
# containers, and the mono treatment web/ gives technical lines. Chasing every widget would
# mean fighting Streamlit's internals for no real gain.
st.markdown(
    f"""
    <style>
      /* The eyebrow above each tab's heading — web/'s TabHeader, at Streamlit scale. */
      .tnx-eyebrow {{
        font-family: ui-monospace, "Geist Mono", monospace;
        font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.2em;
        color: {ACCENT}; margin-bottom: 0.35rem;
      }}
      /* The provenance footnote each tab closes with, ◆-prefixed as in web/. */
      .tnx-prov {{
        font-family: ui-monospace, "Geist Mono", monospace;
        font-size: 0.75rem; line-height: 1.7; color: {MUTED}; margin-top: 1.4rem;
      }}
      .tnx-prov b {{ color: {ACCENT}; font-weight: 400; }}
      /* Metrics are the one place this app has a panel: web/'s StatTile, same bordered
         surface with the value in accent. (No rule for stVerticalBlockBorderWrapper — this
         app never uses st.container(border=True), so such a rule would style nothing.) */
      div[data-testid="stMetric"] {{
        background: {SURFACE}; border: 1px solid {BORDER};
        border-radius: 10px; padding: 0.85rem 1rem;
      }}
      div[data-testid="stMetricValue"] {{ color: {ACCENT}; }}
      /* Mono uppercase is web/'s treatment for metric labels specifically — its MonoLabel.
         Captions are deliberately excluded: they carry each tab's lede, which web/ sets as
         ordinary muted prose. Uppercasing a paragraph of it makes it shout. */
      [data-testid="stMetricLabel"] p {{ /* a <label>, not a <div> — no element prefix */
        font-family: ui-monospace, "Geist Mono", monospace;
        font-size: 0.72rem !important; letter-spacing: 0.12em; text-transform: uppercase;
        color: {MUTED};
      }}
      div[data-testid="stCaptionContainer"] p {{ color: {MUTED}; line-height: 1.65; }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 1.6rem; border-bottom: 1px solid {BORDER}; }}
      /* Dark text on amber, as web/'s PrimaryButton does. Streamlit's default white on
         #f5b544 is about 1.9:1 — unreadable, and not the brand's button. */
      button[data-testid="stBaseButton-primary"],
      button[data-testid="stBaseButton-primary"] p {{
        color: #07090d !important; font-weight: 600;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)


def eyebrow(text: str) -> None:
    """The uppercase mono kicker web/ puts above every tab heading."""
    st.markdown(f'<div class="tnx-eyebrow">{text}</div>', unsafe_allow_html=True)


def provenance(text: str) -> None:
    """The ◆ footnote naming the endpoint behind what is on screen, as in web/."""
    st.markdown(f'<p class="tnx-prov">◆ {text}</p>', unsafe_allow_html=True)


st.title("Tenax — persistent memory for AI agents")
st.caption(
    "Multi-tier memory · hybrid retrieval · belief revision · forgetting curve · "
    "consolidation — powered by Qwen Cloud"
)

with st.sidebar:
    st.header("Session")
    api = st.text_input("Backend URL", API)
    user_id = st.text_input("User ID", "demo")
    token_budget = st.slider("Recall token budget", 100, 4000, 1200, 100)
    st.caption("Memories are scoped per user. A name nobody has used yet starts empty.")
    try:
        h = httpx.get(f"{api}/health", timeout=5).json()
        st.success(f"Backend OK · {h.get('model')}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Backend unreachable: {exc}")


def post(path: str, payload: dict) -> dict:
    return httpx.post(f"{api}{path}", json=payload, timeout=60).json()


def get(path: str, params: dict) -> object:
    return httpx.get(f"{api}{path}", params=params, timeout=30).json()


# Tab names match web/'s console exactly — "Memory store", not "Memories".
tab_remember, tab_recall, tab_mem, tab_maint = st.tabs(
    ["Remember", "Recall", "Memory store", "Maintenance"]
)

with tab_remember:
    eyebrow("Write path")
    st.subheader("Remember — Qwen extracts what's worth keeping.")
    st.caption(
        "Feed an interaction. Distilled memories are extracted with a type and importance. "
        "When a new fact contradicts a stored one, belief revision fires: the stale memory is "
        "archived with a pointer to what supersedes it."
    )
    text = st.text_area("Interaction / document text", height=160,
                        placeholder="e.g. I'm researching retrieval-augmented generation; my advisor is Dr. Lin...")
    if st.button("Remember", type="primary") and text.strip():
        res = post("/remember", {"user_id": user_id, "text": text})
        created = res.get("created", [])
        st.success(f"Stored {len(created)} memory(ies).")
        if created:
            st.dataframe(pd.DataFrame(created)[["content", "mem_type", "importance"]], use_container_width=True)
        elif res.get("note"):
            st.info(res["note"])
        superseded = res.get("superseded", [])
        if superseded:
            st.warning(f"Belief revised: {len(superseded)} stale fact(s) superseded and archived.")
            st.dataframe(
                pd.DataFrame(superseded)[["content", "superseded_by"]]
                .rename(columns={"content": "stale belief (archived)", "superseded_by": "replaced by memory id"}),
                use_container_width=True,
            )
    provenance(
        "POST /remember → <b>{ created[], superseded[] }</b> · revision keeps recall serving "
        "the current truth."
    )

with tab_recall:
    eyebrow("The money shot")
    st.subheader("Recall — hybrid retrieval, packed to a token budget.")
    st.caption(
        "Ask a question. Tenax scores every candidate memory on four signals, then greedily "
        "packs the highest-relevance set that fits the budget — that assembled context is "
        "exactly what gets injected into the agent."
    )
    query = st.text_input("Query", placeholder="What do you remember about my research?")
    if st.button("Recall", type="primary") and query.strip():
        res = post("/recall", {"user_id": user_id, "query": query, "token_budget": token_budget})
        c1, c2 = st.columns(2)
        c1.metric("tokens used", res.get("tokens_used", 0))
        c2.metric("token budget", res.get("token_budget", token_budget))
        st.markdown("**Context injected into agent:**")
        st.code(res.get("context", "") or "(no memories)", language="markdown")
        mems = res.get("memories", [])
        if mems:
            df = pd.DataFrame([{**m["scores"], "content": m["content"], "tokens": m["tokens"]} for m in mems])
            st.dataframe(df, use_container_width=True)
    provenance(
        "POST /recall · scores = semantic · keyword · recency · importance → combined; "
        "greedy pack under budget."
    )

with tab_mem:
    eyebrow("The store")
    st.subheader("Every memory, with its decay.")
    status = st.selectbox("Status", ["active", "archived", "all"])
    if st.button("Refresh"):
        st.session_state["mems"] = get("/memories", {"user_id": user_id, "status": status, "limit": 200})
        st.session_state["stats"] = get("/stats", {"user_id": user_id})
    if "stats" in st.session_state:
        s = st.session_state["stats"]
        cols = st.columns(3)
        cols[0].metric("total memories", s.get("total", 0))
        cols[1].metric("active by type", ", ".join(f"{k}:{v}" for k, v in s.get("active_by_type", {}).items()) or "-")
        cols[2].metric("by status", ", ".join(f"{k}:{v}" for k, v in s.get("by_status", {}).items()) or "-")
    if "mems" in st.session_state and st.session_state["mems"]:
        df = pd.DataFrame(st.session_state["mems"])
        show = [c for c in ["content", "mem_type", "importance", "decay_score", "access_count", "status", "superseded_by", "created_at"] if c in df]
        st.dataframe(df[show], use_container_width=True)
    provenance(
        "GET /memories · decay = importance × recency × (1 + log access_count); below "
        "<b>0.15</b> a memory is a forget-sweep candidate."
    )

with tab_maint:
    eyebrow("Self-maintenance")
    st.subheader("Forget stale, consolidate duplicates — safely.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Forget sweep**")
        st.caption(
            "Archive low-value memories below the decay threshold. Soft-forget: status flips "
            "to `archived`, never deleted — reversible and auditable."
        )
        if st.button("Run forget sweep"):
            st.json(post("/forget", {"user_id": user_id}))
    with c2:
        st.markdown("**Reflect / consolidate**")
        st.caption(
            "Cluster near-duplicates and distill them into canonical facts. The trust signal "
            "is `wrong_merges` — merges that shouldn't have happened."
        )
        if st.button("Run reflection"):
            st.json(post("/reflect", {"user_id": user_id}))
    provenance("POST /forget · POST /reflect — the self-managing half of the loop.")
