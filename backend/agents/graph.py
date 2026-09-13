"""Thin-slice LangGraph pipeline: intake -> screening -> policy retrieval -> scoring -> decisioning.

Wires the 5 stages together as a LangGraph graph. Entity resolution is folded
into the screening stage for this thin slice (both operate on customer_name);
see ARCHITECTURE.md for the full 8-stage pipeline this will grow into.
"""

from typing import NotRequired, TypedDict, cast

from langgraph.graph import END, StateGraph

from agents.decisioning import decide
from agents.intake import load_case
from agents.retrieval import PolicyChunk, retrieve_policy_chunks
from agents.screening import ScreeningResult, screen_name
from agents.scoring import RiskScore, score_case
from data.schema import Case


class PipelineState(TypedDict):
    case_id: str
    case: NotRequired[Case]
    screening_result: NotRequired[ScreeningResult]
    policy_chunks: NotRequired[list[PolicyChunk]]
    risk_score: NotRequired[RiskScore]
    decision: NotRequired[str]


def intake_node(state: PipelineState) -> dict:
    case = load_case(state["case_id"])
    return {"case": case}


def screening_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    result = screen_name(case.customer_name)
    return {"screening_result": result}


async def retrieval_node(state: PipelineState) -> dict:
    screening_result = cast(ScreeningResult, state["screening_result"])
    chunks = await retrieve_policy_chunks(screening_result)
    return {"policy_chunks": chunks}


def scoring_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    screening_result = cast(ScreeningResult, state["screening_result"])
    risk_score = score_case(case, screening_result)
    return {"risk_score": risk_score}


def decisioning_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    screening_result = cast(ScreeningResult, state["screening_result"])
    policy_chunks = cast("list[PolicyChunk]", state["policy_chunks"])
    risk_score = cast(RiskScore, state["risk_score"])
    decision = decide(case, screening_result, policy_chunks, risk_score)
    return {"decision": decision}


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("intake", intake_node)
    graph.add_node("screening", screening_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("decisioning", decisioning_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "screening")
    graph.add_edge("screening", "retrieval")
    graph.add_edge("retrieval", "scoring")
    graph.add_edge("scoring", "decisioning")
    graph.add_edge("decisioning", END)

    return graph.compile()


async def run_pipeline(case_id: str) -> PipelineState:
    app = build_graph()
    return await app.ainvoke({"case_id": case_id})
