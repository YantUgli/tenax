"""Day-1 smoke test: prove the Qwen Cloud key works for both chat and embeddings.

Run:  pipenv run python -m scripts.first_call
"""
from app.config import get_settings
from app.qwen_client import QwenClient


def main() -> None:
    s = get_settings()
    print(f"Base URL : {s.qwen_base_url}")
    print(f"Chat     : {s.qwen_chat_model}")
    print(f"Embed    : {s.qwen_embed_model} (dim {s.embed_dim})")
    print("-" * 50)

    client = QwenClient()

    reply = client.chat([{"role": "user", "content": "Reply with exactly: Qwen Cloud is connected."}])
    print("Chat reply :", reply.strip())

    vec = client.embed_one("Tenax persistent memory smoke test")
    print("Embed dim  :", len(vec))
    assert len(vec) == s.embed_dim, f"expected {s.embed_dim}, got {len(vec)}"
    print("\n✅ Qwen Cloud chat + embeddings both working.")


if __name__ == "__main__":
    main()
