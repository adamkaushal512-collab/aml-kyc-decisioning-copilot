"""Hybrid rule + ML decision stage: produces the final disposition recommendation and cited rationale.

Thin-slice version: a single deterministic rule (sanctions/PEP match -> escalate),
citing the screening result and policy snippet. The ML/LLM-based judgment for
nuanced cases (see ARCHITECTURE.md stage 7) is not yet implemented.
"""

from agents.screening import ScreeningResult
from data.schema import Case


def decide(case: Case, screening_result: ScreeningResult, policy_snippet: str) -> str:
    """Combines the screening result and policy snippet into a decision string."""
    if screening_result["matched"]:
        similarity_pct = screening_result["similarity"] * 100
        return (
            f"ESCALATE - sanctions match found: {case.customer_name} matches "
            f"{screening_result['matched_source']} entry "
            f"'{screening_result['matched_name']}' with {similarity_pct:.1f}% similarity. "
            f"Policy: {policy_snippet}"
        )

    return (
        f"CLEAR - no sanctions/PEP match found for {case.customer_name}. "
        f"Policy: {policy_snippet}"
    )
