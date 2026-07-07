"""Mnemo demo dashboard (Streamlit).

Talks to the Mnemo REST backend so the same UI works locally and against the
Alibaba Cloud deployment. Run:  pipenv run streamlit run demo/app.py
"""
from __future__ import annotations

import os

import httpx
import pandas as pd
import streamlit as st

API = os.getenv("MNEMO_API", "http://localhost:8000")

st.set_page_config(page_title="Mnemo — Qwen-powered memory", layout="wide")
st.title("Mnemo — persistent memory for AI agents")
st.caption("Multi-tier memory · hybrid retrieval · belief revision · forgetting curve · consolidation — powered by Qwen Cloud")

with st.sidebar:
    st.header("Session")
    api = st.text_input("Backend URL", API)
    user_id = st.text_input("User ID", "demo")
    token_budget = st.slider("Recall token budget", 100, 4000, 1200, 100)
    try:
        h = httpx.get(f"{api}/health", timeout=5).json()
        st.success(f"Backend OK · {h.get('model')}")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Backend unreachable: {exc}")


def post(path: str, payload: dict) -> dict:
    return httpx.post(f"{api}{path}", json=payload, timeout=60).json()


def get(path: str, params: dict) -> object:
    return httpx.get(f"{api}{path}", params=params, timeout=30).json()


tab_remember, tab_recall, tab_mem, tab_maint = st.tabs(
    ["Remember", "Recall", "Memories", "Maintenance"]
)

with tab_remember:
    st.subheader("Feed an interaction — Qwen extracts what's worth remembering")
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

with tab_recall:
    st.subheader("Recall — hybrid retrieval packed into the token budget")
    query = st.text_input("Query", placeholder="What do you remember about my research?")
    if st.button("Recall", type="primary") and query.strip():
        res = post("/recall", {"user_id": user_id, "query": query, "token_budget": token_budget})
        c1, c2 = st.columns(2)
        c1.metric("Tokens used", res.get("tokens_used", 0))
        c2.metric("Budget", res.get("token_budget", token_budget))
        st.markdown("**Assembled context:**")
        st.code(res.get("context", "") or "(no memories)", language="markdown")
        mems = res.get("memories", [])
        if mems:
            df = pd.DataFrame([{**m["scores"], "content": m["content"], "tokens": m["tokens"]} for m in mems])
            st.dataframe(df, use_container_width=True)

with tab_mem:
    st.subheader("Memory store")
    status = st.selectbox("Status", ["active", "archived", "all"])
    if st.button("Refresh"):
        st.session_state["mems"] = get("/memories", {"user_id": user_id, "status": status, "limit": 200})
        st.session_state["stats"] = get("/stats", {"user_id": user_id})
    if "stats" in st.session_state:
        s = st.session_state["stats"]
        cols = st.columns(3)
        cols[0].metric("Total", s.get("total", 0))
        cols[1].metric("Active by type", ", ".join(f"{k}:{v}" for k, v in s.get("active_by_type", {}).items()) or "-")
        cols[2].metric("By status", ", ".join(f"{k}:{v}" for k, v in s.get("by_status", {}).items()) or "-")
    if "mems" in st.session_state and st.session_state["mems"]:
        df = pd.DataFrame(st.session_state["mems"])
        show = [c for c in ["content", "mem_type", "importance", "decay_score", "access_count", "status", "superseded_by", "created_at"] if c in df]
        st.dataframe(df[show], use_container_width=True)

with tab_maint:
    st.subheader("Self-maintenance skills")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Forget** — archive stale, low-value memories")
        if st.button("Run forget sweep"):
            st.json(post("/forget", {"user_id": user_id}))
    with c2:
        st.markdown("**Reflect** — consolidate duplicates into canonical facts")
        if st.button("Run reflection"):
            st.json(post("/reflect", {"user_id": user_id}))
