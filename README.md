# AML/KYC Decisioning Copilot

[![CI](https://github.com/adamkaushal512-collab/aml-kyc-decisioning-copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/adamkaushal512-collab/aml-kyc-decisioning-copilot/actions/workflows/ci.yml)

An agentic pipeline that produces auditable, cited risk decisions for
AML/KYC (Anti-Money Laundering / Know Your Customer) case review —
replacing slow, inconsistent manual analyst review with a system that
gathers evidence, applies policy, and recommends a disposition with a
traceable rationale a human can verify and an auditor can reconstruct
later.

See [`DISCOVERY.md`](./DISCOVERY.md) for the full problem statement,
affected stakeholders, and target success metrics.

## Key Results

From the 17-case golden-set evaluation ([`EVAL_RESULTS.md`](./EVAL_RESULTS.md)):

| Metric | Result |
|---|---|
| Decision accuracy | **100%** (17/17) |
| Citation accuracy (document + clause) | **100%** (17/17) |
| Screening false-positive rate | **0%** |
| Effective catch rate (true matches reaching an actionable disposition) | **87.5%** |

The evaluation also did its job: it surfaced a real gap between the mock
policy corpus and the implemented decision logic — cases scoring 75-89%
similarity against the watchlist were being silently auto-cleared instead
of routed to the "standard analyst review" disposition policy actually
requires. That's now fixed (a third `REVIEW` disposition tier, with
citation routing and decisioning sharing one source of truth so they can't
silently diverge again) and regression-tested. See "The Engineering Story"
below and [`EVAL_RESULTS.md`](./EVAL_RESULTS.md) for the full writeup,
including what's still a known limitation.

## The Engineering Story

This wasn't built end-to-end in one pass — it went through the stages a
real project does, and each one is documented rather than lost to history:

1. **Discovery.** A vague stakeholder complaint ("our AML/KYC review is too
   slow and inconsistent") got scoped against three other candidate use
   cases before committing to this one. [`docs/DISCOVERY_BRIEF.md`](./docs/DISCOVERY_BRIEF.md)
   is the stakeholder-facing readout explaining why this use case won.
2. **Architecture, then a PRD.** The pipeline design came first
   ([`ARCHITECTURE.md`](./ARCHITECTURE.md)), then each business need got
   translated into a specific technical requirement and a measurable eval
   criterion ([`PRD.md`](./PRD.md)) — so "is this working" would have a
   concrete answer, not a vibe.
3. **Thin-slice validation.** Before building all eight pipeline stages,
   one case ran end-to-end through four of them with a hardcoded policy
   snippet, just to prove the shape of the pipeline worked.
4. **Full build-out.** Real pgvector-backed policy retrieval, a hybrid
   rule+ML risk-scoring stage, Langfuse tracing, and an append-only,
   tamper-evident audit log (enforced by a database trigger, not just
   application discipline) replaced the placeholders one at a time.
5. **Golden-set evaluation caught a real gap.** A 17-case labeled dataset
   built to probe threshold behavior — not just happy-path cases —
   surfaced the REVIEW-tier gap described above. The fix and the
   regression test that guards it are both in this repo.
6. **Production hardening.** A CI pipeline that runs the golden-set
   evaluation as a merge gate, a multi-stage Docker build, and a demo UI
   for walking through a live case closed out the loop from "it works on
   my machine" to "someone else can verify that."

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
- **Containerization:** Docker (multi-stage backend build, docker-compose)
- **CI:** GitHub Actions (golden-set evaluation as a merge gate)

## Try It

See [`SETUP.md`](./SETUP.md) for full local setup — installing
dependencies and running the backend and frontend without Docker, or
`docker compose up` for a one-command backend + Postgres/pgvector stack
with no local Python or Postgres install required.

Once both are running, open the frontend for a demo UI that walks through
a live case end-to-end: pick a sample case, run it through the pipeline,
and see the disposition, risk tier, cited policy clause, and the resulting
audit log entry.

## Status

**v1 complete.** The full eight-stage pipeline, golden-set evaluation
(with CI enforcing it as a merge gate), Docker packaging, and a demo UI
are all in place. See [`EVAL_RESULTS.md`](./EVAL_RESULTS.md) for current
results and [`ARCHITECTURE.md`](./ARCHITECTURE.md)'s "Known Limitations"
for what's still open (RAGAS LLM-as-judge scoring pending an API key, the
ML component's synthetic training data, and the scope deferred at
discovery — beneficial ownership analysis and prior-case history).
