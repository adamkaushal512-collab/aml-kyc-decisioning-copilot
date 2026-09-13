# Architecture: AML/KYC Decisioning Copilot

This document describes the v1 pipeline architecture: the stages a case
moves through, the technology backing each stage, and what is explicitly
out of scope for this version.

## Pipeline Overview

The pipeline is an agentic, staged workflow orchestrated with **LangGraph**.
Each case flows through the same sequence of stages; LangGraph manages state
between stages, retries, and conditional branching (e.g., re-screening after
entity resolution resolves an alias).

```
                    ┌───────────────────┐
                    │   1. Intake       │
                    │  (case arrives)   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 2. Document        │
                    │    Normalization   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 3. Entity          │
                    │    Resolution      │
                    │ (fuzzy name match) │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 4. Sanctions/PEP   │
                    │    Screening       │
                    │ (local mock list)  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 5. Policy          │
                    │    Retrieval (RAG) │
                    │   [pgvector]       │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 6. Risk Scoring    │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 7. Hybrid Decision │
                    │  (rules + ML)      │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 8. Audit Logging   │
                    └───────────────────┘

        Orchestration: LangGraph (all stages)
        Observability: Langfuse (traces every stage)
        Evaluation:    RAGAS (scores stage 5's retrieval + generation)
```

## Stages

### 1. Intake
A case (transaction-monitoring alert or KYC refresh trigger) enters the
pipeline with its raw supporting data: customer record, transaction(s), and
any documents attached to the alert.

### 2. Document Normalization
Raw inputs (PDFs, scanned IDs, free-text alert notes, structured transaction
fields) are parsed and normalized into a consistent internal schema so
downstream stages can operate on structured fields rather than raw
documents.

### 3. Entity Resolution (Fuzzy Name Matching)
Resolves the customer/counterparty names referenced across the case's
documents and transactions into a single canonical entity record, using
fuzzy matching to account for transliteration, abbreviation, and data-entry
variance (e.g., "Robert Smith" vs. "Bob Smith" vs. "R. Smith").

### 4. Sanctions/PEP Screening
Screens the resolved entity against a **local mock watchlist** standing in
for real sanctions/PEP/adverse-media data sources (e.g., OFAC, UN, PEP
lists). Produces candidate hits with match scores for downstream review.

### 5. Policy Retrieval (RAG)
Retrieves the AML/KYC policy passages relevant to the case's risk factors
(customer type, jurisdiction, transaction pattern, screening hits) using
retrieval-augmented generation over a policy document corpus embedded in
**pgvector**. This grounds the eventual decision rationale in actual policy
text rather than the model's unaided judgment.

### 6. Risk Scoring
Combines entity attributes, screening results, transaction risk signals, and
retrieved policy guidance into a quantitative risk score for the case.

### 7. Hybrid Rule + ML Decision
Produces the final disposition recommendation (clear / escalate / file SAR /
request more info) using a hybrid approach: deterministic policy rules
handle unambiguous cases (e.g., confirmed sanctions match → auto-escalate),
while an ML/LLM-based judgment handles nuanced, borderline cases — with the
rationale citing the specific screening hits and policy passages that drove
the decision.

### 8. Audit Logging
Persists the full case trace — inputs, intermediate stage outputs, retrieved
policy citations, screening hits, and final decision with rationale — so the
decision can be reconstructed and defended during an audit or examination,
independent of Langfuse's operational tracing.

## Supporting Infrastructure

| Concern | Technology | Role |
|---|---|---|
| Orchestration | **LangGraph** | Sequences the 8 stages as a graph, manages state and conditional flow between them |
| Retrieval store | **pgvector** | Vector store for the policy-document corpus used in stage 5 (Policy Retrieval) |
| Evaluation | **RAGAS** | Scores retrieval and generation quality (e.g., context precision/recall, faithfulness) for the RAG step, independent of production traffic |
| Observability / tracing | **Langfuse** | Traces every pipeline run stage-by-stage in real time, for debugging and monitoring — distinct from the permanent audit log in stage 8 |

## Deployment

**AWS is the documented production target.** No infrastructure has been
provisioned yet — this section describes the intended deployment, not the
current state:

- **Agent services (LangGraph pipeline):** ECS/Fargate or Lambda. Fargate is
  the likely fit for the full pipeline given multi-stage runtimes and
  potential per-stage memory/timeout variance; Lambda remains an option for
  lighter-weight or individually invokable stages.
- **Storage:** RDS (PostgreSQL) with the pgvector extension, serving both
  the policy-document embeddings (stage 5) and the pipeline's relational
  case/audit data.

The specific split between ECS/Fargate and Lambda, networking, and scaling
configuration are open decisions to be settled during implementation.

## Security & Governance

- **PII handling:** Case data includes customer PII (names, IDs,
  transaction details) that must be handled deliberately, not incidentally.
  At minimum: encrypt PII at rest and in transit, scope access to what each
  pipeline stage actually needs, and avoid passing raw PII into logs or
  traces (Langfuse and stage 8's audit log) without redaction or masking
  where the raw value isn't itself the evidence being audited.
- **Prompt-injection defense:** Several stages (policy retrieval, hybrid
  decisioning) put an LLM in contact with content it does not control —
  free-text alert notes, adverse-media snippets, and retrieved policy
  passages could all carry adversarial or malformed instructions. The
  pipeline must treat all such content as untrusted data, not instructions:
  keep retrieved/ingested text out of the system prompt, constrain what
  actions an LLM stage can take as a result of what it reads (e.g., it can
  recommend a disposition, not alter pipeline control flow or trigger side
  effects), and validate/sanitize document text during normalization
  (stage 2) before it reaches any LLM-facing stage.
- **Audit-log integrity:** The audit log produced in stage 8 is the record
  an examiner relies on to reconstruct a decision, so it must be
  tamper-evident and immutable once written — append-only storage, no
  update/delete path for existing entries, and a durability/retention
  policy that outlives the case itself. This is a stronger guarantee than
  Langfuse's operational tracing is expected to provide, which is why the
  two are kept distinct (see stage 8).

## Known Limitations / Out of Scope for v1

`DISCOVERY.md` lists **beneficial ownership analysis** and **prior-case-
history retrieval** as evidence types a complete decisioning system should
draw on. Both are **explicitly out of scope for v1**:

- **Beneficial ownership analysis** — resolving corporate structures to
  identify ultimate beneficial owners is not implemented. v1 screens the
  named entity only; it does not trace ownership chains.
- **Prior-case-history retrieval** — the pipeline does not look up or
  incorporate an entity's previous case dispositions. Each case is decided
  independently of the entity's history with the institution.

This is a known gap, not an oversight: both require data integrations and
matching logic beyond what v1's mock-data, single-pass pipeline supports.
They should be revisited for v2 once the core pipeline (intake through audit
logging) is validated end-to-end.

- **Policy retrieval ranking quality** — `all-MiniLM-L6-v2` embeddings can
  misrank semantically-close clauses. In manual testing, a query about a
  92% sanctions match ranked the clause governing the "below 75%" case
  above the clause governing the "90% or greater" case that actually
  applies (see `backend/scripts/query_policy_chunks.py`). This is mitigated
  for now by passing the top-3 retrieved chunks into the decision stage
  rather than relying on the top-1 result alone, so the correct clause is
  still in context even when it isn't ranked first. Reranking or a larger
  embedding model is a candidate improvement to revisit once a golden eval
  set exists to measure retrieval quality against (see `PRD.md`'s citation
  precision criterion).

- **Risk-scoring ML component's training data** — the ML half of the
  hybrid risk-scoring agent (`agents/scoring.py`) is trained on a small
  (90-sample) *synthetic* dataset, since no real historical case data
  exists yet. In manual testing it doesn't perfectly recover the rule-based
  labeling boundary on low-amount/low-similarity cases — it predicts
  "medium" where the generating rule would say "low." This is expected
  behavior for a linear model fit on limited synthetic data, not a
  functional bug: the rule-based floor sits below the ML component in the
  combination logic and only ever raises the final tier, so this
  under-recovery on the low end doesn't produce an incorrect final
  disposition (it can only push a "low" case to "medium," never past the
  rule's own floor). Revisit once a real golden eval set exists per
  `PRD.md`'s consistency criterion.
