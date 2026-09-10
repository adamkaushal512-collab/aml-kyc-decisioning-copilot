"""Policy retrieval stage: RAG over AML/KYC policy docs embedded in pgvector.

Thin-slice placeholder: returns a hardcoded policy snippet instead of querying
pgvector. Real retrieval will be wired in once this basic pipeline flow works
end-to-end (see ARCHITECTURE.md stage 5).
"""

from agents.screening import ScreeningResult

ESCALATION_POLICY_SNIPPET = (
    "Sanctions matches above 90% similarity require escalation per policy X."
)
NO_MATCH_POLICY_SNIPPET = (
    "No sanctions/PEP match above the escalation threshold; standard review applies."
)


def retrieve_policy_snippet(screening_result: ScreeningResult) -> str:
    """Returns the policy snippet relevant to the case's screening outcome."""
    if screening_result["matched"]:
        return ESCALATION_POLICY_SNIPPET
    return NO_MATCH_POLICY_SNIPPET
