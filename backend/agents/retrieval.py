"""Policy retrieval stage: RAG over AML/KYC policy docs embedded in pgvector.

Embeds a query derived from the case's screening result, retrieves the
top-k most similar chunks from the policy_chunks table (populated by
scripts/load_policy_docs.py), and returns them for the decisioning stage to
cite. See ARCHITECTURE.md's "Known Limitations" section for a retrieval-
quality caveat with the current embedding model.
"""

from typing import TypedDict

from pgvector.asyncpg import register_vector
from sentence_transformers import SentenceTransformer

from agents.screening import ScreeningResult
from db import get_connection

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 3

MATCHED_QUERY = (
    "similarity score 90% or greater sanctions escalation mandatory review"
)
NO_MATCH_QUERY = (
    "similarity score below 75% false positive normal processing no escalation required"
)

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model


class PolicyChunk(TypedDict):
    source_file: str
    chunk_text: str
    similarity: float


def _build_query(screening_result: ScreeningResult) -> str:
    """Derives a retrieval query from the case's screening outcome.

    v1 only distinguishes matched/not-matched on sanctions screening; richer
    query construction (transaction risk factors, PEP status, etc.) is a
    natural extension once those signals feed into screening_result.
    """
    return MATCHED_QUERY if screening_result["matched"] else NO_MATCH_QUERY


async def retrieve_policy_chunks(
    screening_result: ScreeningResult, top_k: int = TOP_K
) -> list[PolicyChunk]:
    """Embeds a query for the screening outcome and retrieves the top-k most similar policy chunks."""
    query = _build_query(screening_result)
    query_embedding = _get_model().encode(query, normalize_embeddings=True)

    conn = await get_connection()
    try:
        await register_vector(conn)
        rows = await conn.fetch(
            """
            SELECT source_file, chunk_text, 1 - (embedding <=> $1) AS similarity
            FROM policy_chunks
            ORDER BY embedding <=> $1
            LIMIT $2;
            """,
            query_embedding,
            top_k,
        )
    finally:
        await conn.close()

    return [
        {
            "source_file": row["source_file"],
            "chunk_text": row["chunk_text"],
            "similarity": row["similarity"],
        }
        for row in rows
    ]
