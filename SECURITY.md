# Security

This document sets out the security and governance principles the AML/KYC
Decisioning Copilot is designed to follow. It expands on the "Security &
Governance" section of [`ARCHITECTURE.md`](./ARCHITECTURE.md) — that section
states *what* the architecture does at each layer; this document covers the
policies and practices behind those choices in more depth. It does not
claim any certification (SOC 2 or otherwise) — the checklist below is a set
of design principles this project holds itself to, not an attestation.

## PII Handling Policy

Case data is customer PII by nature — names, government IDs, addresses,
transaction details, and in some cases beneficial-ownership or KYC
onboarding documents. The policy for handling it:

- **Classify before you store.** Every field the pipeline touches is either
  PII or not; normalization (stage 2 of the pipeline) is where this
  classification happens, so downstream stages don't have to guess.
- **Encrypt at rest and in transit.** No case data is stored or transmitted
  unencrypted, including in the RDS/pgvector store and any intermediate
  queues or caches.
- **Least-privilege access.** Each pipeline stage and each human role
  (analyst, auditor, admin) gets access to the PII fields it actually needs
  to do its job — not the full case record by default.
- **Minimize what reaches observability tooling.** Langfuse traces exist to
  debug and monitor pipeline behavior, not to be a second copy of customer
  PII. Raw PII should be masked or redacted in traces wherever the raw value
  isn't itself the thing being debugged (e.g., trace that a name-match
  occurred and its score, not necessarily the full document that produced
  it).
- **Retention has an end.** PII is retained only as long as regulatory
  record-keeping requirements and active case needs require, not
  indefinitely by default.

## Prompt-Injection Defense

The pipeline puts LLMs in contact with content the system does not
control — free-text alert notes, adverse-media snippets, and retrieved
policy passages (stage 5) can all carry text engineered to look like
instructions. The defense approach:

- **Treat ingested and retrieved content as data, never as instructions.**
  Alert text, screening results, and retrieved policy passages are passed
  to the LLM as content to reason *about*, kept structurally separate from
  the system prompt that defines the LLM's task and constraints.
- **Constrain the blast radius of any single LLM stage.** An LLM-facing
  stage (policy retrieval synthesis, hybrid decisioning) can produce a
  recommendation and a rationale — it cannot alter pipeline control flow,
  invoke arbitrary tools, or trigger side effects outside its declared
  scope. LangGraph's explicit stage boundaries are what make this
  enforceable: an injected instruction in a document has no path to
  "become" a graph transition.
- **Sanitize before an LLM ever sees it.** Document normalization (stage 2)
  is the checkpoint where inbound text is parsed into structured fields —
  this is also where obviously anomalous content (e.g., text that looks
  like a system-prompt override attempt) can be flagged rather than passed
  through silently.
- **Assume adversarial input in tests.** Prompt-injection test cases
  (adversarial alert notes, poisoned policy snippets) belong in the same
  evaluation loop as RAGAS quality scoring — a robustness regression is a
  regression, not a separate concern.

## Audit-Log Integrity

The audit log produced at the end of the pipeline (stage 8) is the record
an examiner or auditor relies on to reconstruct and defend a decision made
months or years earlier. Requirements:

- **Append-only.** Once written, an audit-log entry has no update or delete
  path. Corrections to a case's disposition are recorded as new entries
  referencing the original, never as edits to it.
- **Complete by construction.** An entry captures the full decision
  context — inputs, intermediate stage outputs, screening hits, retrieved
  policy citations, and the final decision with rationale — at the moment
  the decision is made, not reconstructed after the fact from other
  systems.
- **Independent of operational tracing.** The audit log is a distinct,
  durable system from Langfuse's tracing. Langfuse can be sampled, rotated,
  or have shorter retention because it serves debugging; the audit log
  cannot, because it serves the institution's regulatory obligations.
- **Retention outlives the case.** The audit log's retention policy is set
  by regulatory record-keeping requirements, not by operational convenience
  — an entry must still be reconstructable long after the case itself is
  closed.
- **Tamper-evidence, not just tamper-resistance.** Where feasible, entries
  should be verifiable as unaltered (e.g., via hashing or a write-once
  storage guarantee), so integrity isn't just a matter of trusting that no
  one used the delete path.

## Governance Checklist (SOC 2–Inspired Design Principles)

These are design principles this project follows, organized loosely around
the SOC 2 trust services categories. **This is not a certification claim** —
no formal SOC 2 audit has been performed or is implied.

- **Security**
  - [ ] Least-privilege access enforced between pipeline stages and human
        roles
  - [ ] PII encrypted at rest and in transit
  - [ ] Prompt-injection defenses applied at every LLM-facing stage
- **Availability**
  - [ ] Pipeline failures in one stage do not silently drop a case; failed
        cases are surfaced, not lost
- **Processing Integrity**
  - [ ] Every decision's rationale is traceable to specific cited evidence
        (screening hits, policy passages) — no uncited claims in a
        disposition
  - [ ] RAG quality (retrieval + generation) is continuously evaluated via
        RAGAS, not assumed
- **Confidentiality**
  - [ ] Case data access is scoped by role; observability tooling does not
        become a secondary store of raw PII
- **Privacy**
  - [ ] PII retention has a defined, regulation-driven end date, not an
        indefinite default
  - [ ] Data subject and regulatory record-keeping obligations are
        considered explicitly, not left implicit in the code

This checklist should evolve as the pipeline moves from v1 (mock data,
single-pass) toward production use — see `ARCHITECTURE.md`'s "Known
Limitations" section for what else is still out of scope.
