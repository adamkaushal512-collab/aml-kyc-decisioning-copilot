"""Hybrid rule + ML decision stage: produces the final disposition recommendation and cited rationale.

Thin-slice version: a single deterministic rule (sanctions/PEP match -> escalate),
citing the retrieved policy chunks. The ML/LLM-based judgment for nuanced
cases (see ARCHITECTURE.md stage 7) is not yet implemented.
"""

from agents.retrieval import PolicyChunk
from agents.screening import ScreeningResult
from data.schema import Case


def _format_citation(chunk: PolicyChunk) -> str:
    return f"[{chunk['source_file']}] {chunk['chunk_text']}"


def decide(case: Case, screening_result: ScreeningResult, policy_chunks: list[PolicyChunk]) -> str:
    """Combines the screening result and retrieved policy chunks into a decision string.

    Uses the top-ranked chunk as the primary citation in the rationale, but
    keeps the remaining retrieved chunks available as supporting citations
    (mitigating the retrieval ranking quality caveat noted in
    ARCHITECTURE.md by not relying on the top-1 result alone).
    """
    if not policy_chunks:
        raise ValueError("decide() requires at least one retrieved policy chunk to cite")

    primary_citation = _format_citation(policy_chunks[0])
    supporting_citations = [_format_citation(chunk) for chunk in policy_chunks[1:]]

    if screening_result["matched"]:
        similarity_pct = screening_result["similarity"] * 100
        decision = (
            f"ESCALATE - sanctions match found: {case.customer_name} matches "
            f"{screening_result['matched_source']} entry "
            f"'{screening_result['matched_name']}' with {similarity_pct:.1f}% similarity. "
            f"Policy: {primary_citation}"
        )
    else:
        decision = (
            f"CLEAR - no sanctions/PEP match found for {case.customer_name}. "
            f"Policy: {primary_citation}"
        )

    if supporting_citations:
        decision += " | Also considered: " + "; ".join(supporting_citations)

    return decision
