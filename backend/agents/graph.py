"""Thin-slice LangGraph pipeline: intake -> screening -> scoring -> retrieval -> decisioning -> audit.

Retrieval runs after scoring (not before, despite ARCHITECTURE.md's stage
numbering) because its query - and which policy document it targets -
depends on the case's actual escalation trigger (sanctions match vs.
transaction-amount rule vs. no trigger), which risk_score only determines
once scoring has run. See agents/retrieval.py for why this matters.

Wires the 6 stages together as a LangGraph graph. Entity resolution is folded
into the screening stage for this thin slice (both operate on customer_name);
see ARCHITECTURE.md for the full 8-stage pipeline this will grow into.

Traced with Langfuse via langfuse.langchain.CallbackHandler, passed to
ainvoke's config - LangGraph's compiled graph is a LangChain Runnable, so
each node executes as its own traced step under one trace per invocation,
without needing to instrument every node function individually. Credentials
(LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY/LANGFUSE_HOST) are read from the
environment; see .env.example.
"""

from typing import NotRequired, TypedDict, cast

from dotenv import load_dotenv
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, StateGraph

from agents.audit import log_decision
from agents.decisioning import Decision, decide
from agents.intake import load_case
from agents.retrieval import PolicyChunk, retrieve_policy_chunks
from agents.screening import ScreeningResult, screen_name
from agents.scoring import RiskScore, score_case
from data.schema import Case

load_dotenv()


class PipelineState(TypedDict):
    case_id: str
    case: NotRequired[Case]
    screening_result: NotRequired[ScreeningResult]
    policy_chunks: NotRequired[list[PolicyChunk]]
    risk_score: NotRequired[RiskScore]
    decision: NotRequired[Decision]


def intake_node(state: PipelineState) -> dict:
    case = load_case(state["case_id"])
    return {"case": case}


def screening_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    result = screen_name(case.customer_name)
    return {"screening_result": result}


def scoring_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    screening_result = cast(ScreeningResult, state["screening_result"])
    risk_score = score_case(case, screening_result)
    return {"risk_score": risk_score}


async def retrieval_node(state: PipelineState) -> dict:
    screening_result = cast(ScreeningResult, state["screening_result"])
    risk_score = cast(RiskScore, state["risk_score"])
    chunks = await retrieve_policy_chunks(screening_result, risk_score)
    return {"policy_chunks": chunks}


def decisioning_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    screening_result = cast(ScreeningResult, state["screening_result"])
    policy_chunks = cast("list[PolicyChunk]", state["policy_chunks"])
    risk_score = cast(RiskScore, state["risk_score"])
    decision = decide(case, screening_result, policy_chunks, risk_score)
    return {"decision": decision}


async def audit_node(state: PipelineState) -> dict:
    case = cast(Case, state["case"])
    screening_result = cast(ScreeningResult, state["screening_result"])
    risk_score = cast(RiskScore, state["risk_score"])
    decision = cast(Decision, state["decision"])
    await log_decision(case, screening_result, risk_score, decision)
    return {}


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("intake", intake_node)
    graph.add_node("screening", screening_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("decisioning", decisioning_node)
    graph.add_node("audit", audit_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "screening")
    graph.add_edge("screening", "scoring")
    graph.add_edge("scoring", "retrieval")
    graph.add_edge("retrieval", "decisioning")
    graph.add_edge("decisioning", "audit")
    graph.add_edge("audit", END)

    return graph.compile()


async def run_pipeline(case_id: str) -> PipelineState:
    app = build_graph()
    langfuse_handler = CallbackHandler()
    try:
        return await app.ainvoke(
            {"case_id": case_id},
            config={"callbacks": [langfuse_handler], "run_name": f"case-{case_id}"},
        )
    finally:
        # Flush explicitly: this is a short-lived script, and the OTel
        # exporter batches spans in the background rather than sending them
        # synchronously per node.
        get_client().flush()
