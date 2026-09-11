# Discovery Brief: Where We Landed, and Why

**Prepared for:** Compliance Operations Leadership
**Purpose:** Summarize the discovery session findings and the reasoning behind
what we chose to build first.

## Where This Started

The ask that kicked off this work was intentionally broad: *"our AML/KYC
review process is too slow and inconsistent."* That's a real and important
problem, but it's also a starting point, not a scope — "slow and
inconsistent" shows up in several places across the compliance function, not
just one. So before committing to a build, we ran a discovery session to lay
out the realistic candidate use cases, size each one up, and make a
deliberate call on where to start.

Below are the four candidates we evaluated, followed by the prioritization
decision and the reasoning behind it.

## Candidate Use Cases

### 1. AML/KYC Decisioning Copilot

An agentic pipeline that takes in an alert or KYC refresh case, gathers the
relevant evidence (sanctions/PEP screening, policy guidance), and produces a
cited, auditable risk decision recommendation for an analyst to review.

- **Impact estimate:** Meaningful reduction in per-case handling time (cases
  currently running 30-60 minutes of manual evidence-gathering), which
  compounds directly into backlog reduction and faster SAR-deadline turnaround.
- **Effort/complexity estimate:** Moderate. The pipeline has clear, well-
  bounded stages, and a v1 can run against mock screening data before any
  production data integration is needed.
- **Why prioritized:** Directly targets the stated pain point (speed *and*
  consistency) with a scope that's buildable and demonstrable quickly.

### 2. Regulatory Reporting Automation

An assistant that drafts CCAR/SAR-style regulatory reports and flags
discrepancies against source data before submission.

- **Impact estimate:** High potential value — reporting cycles are labor-
  intensive and error-prone — but the benefit is concentrated in periodic
  crunch periods rather than steady weekly relief.
- **Effort/complexity estimate:** High. Report formats are rigid and
  regulator-specific, and getting discrepancy-flagging right requires deep
  integration with source-of-truth systems we don't yet have reliable access
  to.
- **Why not prioritized (yet):** The effort-to-impact ratio is worse right
  now than the decisioning copilot, and it depends on data integrations that
  aren't in place. Worth revisiting once core case data flows exist.

### 3. Fraud/Transaction Monitoring Assistant with LLM-Generated Explanations

A layer on top of existing transaction monitoring that generates plain-
language explanations for why a transaction was flagged, to speed up analyst
triage.

- **Impact estimate:** Solid, incremental time savings on triage — but this
  assumes a mature transaction-monitoring system already producing
  structured flags to explain, which reduces how much net-new value this
  adds on its own.
- **Effort/complexity estimate:** Moderate, but overlaps heavily with the
  decisioning copilot's screening and reasoning components rather than
  standing apart from it.
- **Why not prioritized (yet):** It's closer to a feature extension of the
  decisioning copilot than an independent first build. Makes more sense as a
  v2 capability once the core pipeline exists.

### 4. Internal Knowledge Copilot for Compliance Policy Q&A

A Q&A assistant that lets analysts and compliance staff ask natural-language
questions against the institution's AML/KYC policy corpus.

- **Impact estimate:** Useful, but diffuse — it saves lookup time across many
  small interactions rather than removing a concentrated bottleneck, so it's
  harder to point to a specific backlog or turnaround-time number it moves.
- **Effort/complexity estimate:** Low to moderate — largely a retrieval
  problem over existing policy documents.
- **Why not prioritized (yet):** Genuinely useful, but on its own it doesn't
  address the "slow and inconsistent decisions" pain point directly — it
  supports the person making the decision without producing one. It's also
  a natural building block *inside* the decisioning copilot's policy
  retrieval stage, so it isn't wasted effort — it's just sequenced later as
  a shared capability rather than a standalone product.

## The Decision

**We're building the AML/KYC Decisioning Copilot first.**

Of the four candidates, it has the strongest impact-to-effort ratio and the
most direct line to the problem as stated: it attacks both halves of "slow
*and* inconsistent" at once, it's scoped tightly enough to build and prove
out quickly with mock data before touching production systems, and — unlike
the other three — it isn't waiting on a separate system's maturity or a data
integration we don't have yet. The other three candidates aren't off the
table; reporting automation and the transaction-monitoring assistant are
reasonable next steps once this pipeline is proven, and the policy Q&A
capability effectively gets built anyway as part of this pipeline's
retrieval stage.

For the full problem statement, affected stakeholders, and target success
metrics behind the selected use case, see [`DISCOVERY.md`](../DISCOVERY.md).
