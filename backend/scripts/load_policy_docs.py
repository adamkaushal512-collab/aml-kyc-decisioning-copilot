"""Loads backend/data/policy_docs/*.md into the policy_chunks pgvector table.

Each doc is chunked by clause (numbered list items), embedded with
sentence-transformers, and inserted into Postgres for future retrieval
(see ARCHITECTURE.md stage 5, currently a hardcoded placeholder in
agents/retrieval.py).

Usage: python scripts/load_policy_docs.py
"""

import asyncio
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from pgvector.asyncpg import register_vector  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from db import get_connection  # noqa: E402

POLICY_DOCS_DIR = BACKEND_DIR / "data" / "policy_docs"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Matches numbered clauses like "1. " at the start of a line.
CLAUSE_PATTERN = re.compile(r"^\d+\.\s+", re.MULTILINE)


def chunk_markdown(text: str) -> list[str]:
    """Splits a policy doc into a header/preamble chunk plus one chunk per numbered clause."""
    preamble, *clause_bodies = CLAUSE_PATTERN.split(text)
    clause_numbers = CLAUSE_PATTERN.findall(text)

    chunks = []
    if preamble.strip():
        chunks.append(preamble.strip())
    for number, body in zip(clause_numbers, clause_bodies):
        clause = (number + body).strip()
        if clause:
            chunks.append(clause)
    return chunks


async def create_table(conn) -> None:
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    await conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS policy_chunks (
            id SERIAL PRIMARY KEY,
            source_file TEXT NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}) NOT NULL
        );
        """
    )


async def main() -> None:
    doc_paths = sorted(POLICY_DOCS_DIR.glob("*.md"))
    if not doc_paths:
        raise SystemExit(f"No .md files found in {POLICY_DOCS_DIR}")

    chunks: list[tuple[str, str]] = []
    for path in doc_paths:
        for chunk_text in chunk_markdown(path.read_text()):
            chunks.append((path.name, chunk_text))

    print(f"Chunked {len(doc_paths)} docs into {len(chunks)} chunks.")

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    embeddings = model.encode(
        [chunk_text for _, chunk_text in chunks],
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    conn = await get_connection()
    try:
        await register_vector(conn)
        await create_table(conn)
        await conn.execute("TRUNCATE TABLE policy_chunks;")

        rows = [
            (source_file, chunk_text, embedding)
            for (source_file, chunk_text), embedding in zip(chunks, embeddings)
        ]
        await conn.executemany(
            "INSERT INTO policy_chunks (source_file, chunk_text, embedding) VALUES ($1, $2, $3)",
            rows,
        )

        row_count = await conn.fetchval("SELECT COUNT(*) FROM policy_chunks;")
        print(f"policy_chunks row count: {row_count}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
