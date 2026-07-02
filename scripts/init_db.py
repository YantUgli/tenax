"""Create the pgvector extension, tables, and indexes. Idempotent."""
from app.db import init_db

if __name__ == "__main__":
    init_db()
    print("Mnemo schema initialized.")
