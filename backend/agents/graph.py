"""Thin-slice LangGraph pipeline: intake -> screening -> policy retrieval -> decisioning.

Wires the 4 stages together as a LangGraph graph. Entity resolution is folded
into the screening stage for this thin slice (both operate on customer_name);
see ARCHITECTURE.md for the full 8-stage pipeline this will grow into.
"""

from typing import NotRequired, TypedDict, cast

from langgraph.graph import END, StateGraph

from agents.decisioning import decide
from agents.intake import load_case
from agents.retrieval import retrieve_policy_snippet
from agents.screening import ScreeningResult, screen_name
from data.schema import Case


class PipelineState(TypedDict):
    case_id: str
    case: NotRequired[Case]
    screening_result: NotRequired[ScreeningResult]
    policy_snippet: NotRequired[str]
    decision: NotRequired[str]


def intake_node(state: PipelineState) -> dict:
    case = load_case(state["case_id"])
    return {"case": case}


def screening_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    result = screen_name(case.customer_name)
    return {"screening_result": result}


def retrieval_node(state: PipelineState) -> dict:
    screening_result = cast(ScreeningResult, state["screening_result"])
    snippet = retrieve_policy_snippet(screening_result)
    return {"policy_snippet": snippet}


def decisioning_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    screening_result = cast(ScreeningResult, state["screening_result"])
    policy_snippet = cast(str, state["policy_snippet"])
    decision = decide(case, screening_result, policy_snippet)
    return {"decision": decision}


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("intake", intake_node)
    graph.add_node("screening", screening_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("decisioning", decisioning_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "screening")
    graph.add_edge("screening", "retrieval")
    graph.add_edge("retrieval", "decisioning")
    graph.add_edge("decisioning", END)

    return graph.compile()


def run_pipeline(case_id: str) -> PipelineState:
    app = build_graph()
    return app.invoke({"case_id": case_id})
