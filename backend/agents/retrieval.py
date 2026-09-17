"""Policy retrieval stage: RAG over AML/KYC policy docs embedded in pgvector.

Embeds a query derived from the case's actual disposition trigger (via
agents.scoring.determine_disposition - the same function decisioning.py
uses, so the two can't silently diverge), retrieves the top-k most similar
chunks *within the policy document that trigger governs* (populated by
scripts/load_policy_docs.py), and returns them for the decisioning stage to
cite. Restricting retrieval to the governing document is a deliberate,
deterministic guarantee - not left to embedding similarity alone - after a
real citation/disposition mismatch surfaced in testing (a transaction-amount
escalation cited the sanctions doc's "false positive" clause, because query
selection only considered screening_result["matched"], not the actual
trigger). See ARCHITECTURE.md's "Known Limitations" section for a
within-document ranking-quality caveat that this filtering does not address.
"""

from typing import TypedDict

from pgvector.asyncpg import register_vector
from sentence_transformers import SentenceTransformer

from agents.screening import ScreeningResult
from agents.scoring import RiskScore, determine_disposition
from db import get_connection

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 3

SANCTIONS_DOC = "01_sanctions_screening_escalation.md"
TRANSACTION_MONITORING_DOC = "05_transaction_monitoring_red_flags.md"

MATCHED_QUERY = (
    "similarity score 90% or greater sanctions escalation mandatory review"
)
REVIEW_QUERY = (
    "similarity score between 75 and 89 percent standard analyst review documented rationale"
)
NO_MATCH_QUERY = (
    "similarity score below 75% false positive normal processing no escalation required"
)
AMOUNT_QUERY = (
    "wire transfer amount exceeds one million dollars automatically flagged enhanced review"
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


def _select_query(screening_result: ScreeningResult, risk_score: RiskScore) -> tuple[str, str]:
    """Selects the retrieval query and governing document from the case's disposition.

    Uses determine_disposition() (shared with decisioning.py) so the citation
    always comes from the document that actually explains the outcome,
    rather than each stage independently re-deriving - and potentially
    disagreeing on - what drove it.
    """
    disposition = determine_disposition(screening_result, risk_score)
    if disposition == "ESCALATE":
        if screening_result["matched"]:
            return MATCHED_QUERY, SANCTIONS_DOC
        return AMOUNT_QUERY, TRANSACTION_MONITORING_DOC
    if disposition == "REVIEW":
        return REVIEW_QUERY, SANCTIONS_DOC
    return NO_MATCH_QUERY, SANCTIONS_DOC


async def retrieve_policy_chunks(
    screening_result: ScreeningResult, risk_score: RiskScore, top_k: int = TOP_K
) -> list[PolicyChunk]:
    """Embeds a query for the case's escalation trigger and retrieves the top-k most similar
    chunks from the document that trigger governs."""
    query, source_file = _select_query(screening_result, risk_score)
    query_embedding = _get_model().encode(query, normalize_embeddings=True)

    conn = await get_connection()
    try:
        await register_vector(conn)
        rows = await conn.fetch(
            """
            SELECT source_file, chunk_text, 1 - (embedding <=> $1) AS similarity
            FROM policy_chunks
            WHERE source_file = $2
            ORDER BY embedding <=> $1
            LIMIT $3;
            """,
            query_embedding,
            source_file,
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
