"""Hybrid rule + ML decision stage: produces the final disposition recommendation and cited rationale.

Three-tier disposition (ESCALATE / REVIEW / CLEAR), matching policy
AML-014's clauses 2/3/4. Disposition comes from agents.scoring.
determine_disposition() - the same function retrieval.py uses for citation
routing - so a case can never show "CLEAR" alongside a HIGH risk tier, and
a REVIEW-band case can never be silently auto-cleared. The ML/LLM-based
judgment for nuanced cases beyond this rule+threshold logic (see
ARCHITECTURE.md stage 7) is not yet implemented.
"""

from typing import TypedDict

from agents.retrieval import PolicyChunk
from agents.screening import ScreeningResult
from agents.scoring import Disposition, RiskScore, determine_disposition
from data.schema import Case


class Decision(TypedDict):
    text: str
    disposition: Disposition
    primary_citation: str


def _format_citation(chunk: PolicyChunk) -> str:
    return f"[{chunk['source_file']}] {chunk['chunk_text']}"


def _escalation_reason(case: Case, screening_result: ScreeningResult, risk_score: RiskScore) -> str:
    """Describes the actual trigger for an escalation, not just that one occurred."""
    if screening_result["matched"]:
        similarity_pct = screening_result["similarity"] * 100
        return (
            f"escalated due to sanctions match: {case.customer_name} matches "
            f"{screening_result['matched_source']} entry "
            f"'{screening_result['matched_name']}' with {similarity_pct:.1f}% similarity"
        )

    if risk_score["rule_tier"] == "high":
        amount = case.transaction_amount or 0.0
        return (
            f"escalated due to transaction amount (${amount:,.2f}) exceeding "
            f"the high-risk threshold per policy AML-045"
        )

    return "escalated due to elevated model-assessed risk (no rule trigger present)"


def decide(
    case: Case,
    screening_result: ScreeningResult,
    policy_chunks: list[PolicyChunk],
    risk_score: RiskScore,
) -> Decision:
    """Combines the screening result, retrieved policy chunks, and risk score into a decision.

    Disposition is driven by determine_disposition(): "high" risk_tier always
    escalates, regardless of whether that tier came from a screening match or
    a rule-based transaction-amount trigger; a 75-89% similarity band (with
    risk_tier not already high) requires documented analyst REVIEW rather
    than auto-clearing. Uses the top-ranked chunk as the primary citation in
    the rationale, but keeps the remaining retrieved chunks available as
    supporting citations (mitigating the retrieval ranking quality caveat
    noted in ARCHITECTURE.md by not relying on the top-1 result alone).
    Returns disposition and primary_citation as separate fields (not just
    embedded in the text) so the audit stage can record them without
    re-deriving the same logic.
    """
    if not policy_chunks:
        raise ValueError("decide() requires at least one retrieved policy chunk to cite")

    primary_citation = _format_citation(policy_chunks[0])
    supporting_citations = [_format_citation(chunk) for chunk in policy_chunks[1:]]

    disposition = determine_disposition(screening_result, risk_score)

    if disposition == "ESCALATE":
        reason = _escalation_reason(case, screening_result, risk_score)
        text = f"ESCALATE - {reason}. Policy: {primary_citation}"
    elif disposition == "REVIEW":
        similarity_pct = screening_result["similarity"] * 100
        text = (
            f"REVIEW - name similarity {similarity_pct:.1f}% falls within the standard-review "
            f"band (75-89%): {case.customer_name} vs. {screening_result['matched_name']} "
            f"({screening_result['matched_source']}). Requires documented analyst rationale to "
            f"clear or escalate; auto-clearance is not permitted. Policy: {primary_citation}"
        )
    else:
        text = (
            f"CLEAR - no sanctions/PEP match found for {case.customer_name}. "
            f"Policy: {primary_citation}"
        )

    if supporting_citations:
        text += " | Also considered: " + "; ".join(supporting_citations)

    text += (
        f" | Risk Tier: {risk_score['risk_tier'].upper()} (score: {risk_score['risk_score']:.2f}, "
        f"rule: {risk_score['rule_tier']}, ml: {risk_score['ml_tier']})"
    )

    return {
        "text": text,
        "disposition": disposition,
        "primary_citation": primary_citation,
    }
