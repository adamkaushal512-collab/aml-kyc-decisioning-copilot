# AML/KYC Decisioning Copilot

An agentic pipeline that produces auditable, cited risk decisions for
AML/KYC (Anti-Money Laundering / Know Your Customer) case review —
replacing slow, inconsistent manual analyst review with a system that
gathers evidence, applies policy, and recommends a disposition with a
traceable rationale a human can verify and an auditor can reconstruct
later.

See [`DISCOVERY.md`](./DISCOVERY.md) for the full problem statement,
affected stakeholders, and target success metrics.

## Pipeline

Each case flows through eight stages — intake, document normalization,
entity resolution, sanctions/PEP screening, policy retrieval (RAG), risk
scoring, hybrid rule+ML decisioning, and audit logging — orchestrated as a
LangGraph graph, with retrieval, evaluation, and tracing handled by
dedicated tooling at each relevant stage.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full pipeline diagram,
per-stage detail, and known v1 scope limitations (beneficial ownership
analysis and prior-case-history retrieval are deferred to a later
version).

## Tech Stack

- **Backend:** Python, FastAPI
- **Frontend:** TypeScript, React
- **Orchestration:** LangGraph
- **Retrieval store:** pgvector
- **Evaluation:** RAGAS
- **Observability / tracing:** Langfuse

## Status

**Early build phase.** The pipeline architecture and problem scope are
defined; implementation is just getting underway.
