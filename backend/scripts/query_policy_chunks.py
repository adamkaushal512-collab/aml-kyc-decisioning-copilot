"""Quick test: embeds a query and retrieves the top-k most similar policy_chunks rows.

Usage: python scripts/query_policy_chunks.py "your query text" [top_k]

Known limitation: all-MiniLM-L6-v2 can misrank semantically-close clauses
(e.g. it ranked the "below 75%" clause above the "90% or greater" clause for
a query about a 92% match). See ARCHITECTURE.md's "Known Limitations"
section for the full note and planned mitigation.
"""

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from pgvector.asyncpg import register_vector  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from db import get_connection  # noqa: E402

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_QUERY = "what happens if a sanctions screening match is 92% similar?"
DEFAULT_TOP_K = 3


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_TOP_K

    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    query_embedding = model.encode(query, normalize_embeddings=True)

    conn = await get_connection()
    try:
        await register_vector(conn)
        rows = await conn.fetch(
            """
            SELECT source_file, chunk_text, embedding <=> $1 AS distance
            FROM policy_chunks
            ORDER BY embedding <=> $1
            LIMIT $2;
            """,
            query_embedding,
            top_k,
        )
    finally:
        await conn.close()

    print(f"Query: {query!r}\n")
    for rank, row in enumerate(rows, start=1):
        similarity = 1 - row["distance"]
        print(f"#{rank} | {row['source_file']} | cosine similarity: {similarity:.4f}")
        print(row["chunk_text"])
        print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
