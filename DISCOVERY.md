# Discovery: AML/KYC Decisioning Copilot

## Origin

> "Our analysts are drowning. Every alert that comes out of transaction
> monitoring or the KYC refresh queue takes 30-60 minutes to work manually —
> pulling sanctions lists, adverse media, prior SARs, entity structures —
> and then writing up a rationale from scratch. Two analysts can look at the
> same file and reach different conclusions, and when the examiners show up
> asking us to justify a decision from eight months ago, we're stuck
> reconstructing what someone was thinking. We need this faster and we need
> it defensible."
>
> — Head of Compliance Operations, raised in AML/KYC operations review

## Problem Statement

Compliance teams currently perform AML/KYC (Anti-Money Laundering / Know Your
Customer) risk review largely by hand: analysts manually gather evidence
(sanctions/PEP/watchlist hits, adverse media, transaction history, beneficial
ownership data), weigh it against policy, and write a narrative justifying an
escalate/clear/investigate-further decision.

This manual process has two compounding failure modes:

- **It's slow.** Case turnaround is bounded by analyst hours, not case
  complexity, which creates backlog risk during volume spikes and delays
  time-sensitive filings (e.g., SAR deadlines).
- **It's inconsistent.** Decision quality depends on the individual analyst's
  experience, attention, and interpretation of policy on a given day. Similar
  cases can receive different dispositions, and the reasoning behind a
  decision is often thin, undocumented, or hard to reconstruct after the
  fact — which becomes a liability the moment an auditor or examiner asks
  "why was this cleared?"

## Who's Affected

- **Compliance analysts** — the people doing the review today. They need
  relief from repetitive evidence-gathering so they can spend their time on
  judgment calls, not data assembly.
- **Auditors / examiners (internal and regulatory)** — the people who need
  to reconstruct and validate past decisions. They need every decision to
  come with a clear, traceable evidentiary trail, not a memory of what an
  analyst was thinking.
- **Compliance leadership** — the people accountable for program
  effectiveness and regulatory standing. They need consistent decisioning
  across analysts, visibility into throughput and quality, and confidence
  that the program will hold up under regulatory scrutiny.

## Definition of Done

Done is an **agentic decisioning pipeline**, not a static rules engine or a
freeform chatbot. Specifically:

- The system ingests a case (alert, KYC refresh, onboarding review) and
  autonomously gathers and synthesizes the relevant evidence — sanctions/PEP
  screening, adverse media, transaction patterns, beneficial ownership,
  prior case history.
- It produces a **risk decision recommendation** (e.g., clear / escalate /
  file SAR / request more info), not just a data summary.
- Every decision is **cited** — each material claim in the rationale is
  traceable to a specific source document, record, or data point the system
  actually consulted, so a human can verify the reasoning without redoing
  the work.
- The output is **auditable end-to-end**: an examiner or auditor can, months
  later, reconstruct exactly what evidence existed, what the system
  concluded, and why — without relying on an analyst's memory.
- A human analyst remains in the loop to review and approve/override the
  recommendation; the system accelerates and standardizes the work, it does
  not remove accountability.

## Target Success Metrics

| Metric | What it measures | Why it matters |
|---|---|---|
| **Decision accuracy** | Agreement rate between the copilot's recommended disposition and the final validated disposition (post human review / QA sample) | Directly measures whether the system is making sound risk calls, not just fast ones |
| **Citation precision** | Share of cited claims in a decision rationale that are verifiably supported by the source they cite | Determines whether the audit trail is trustworthy — a wrong or fabricated citation is worse than no citation |
| **Screening false-positive rate** | Share of flagged hits (sanctions/PEP/adverse media) that are dismissed as not-a-match after review | High false-positive rates are the main driver of analyst fatigue and backlog; reducing this is where a lot of the time savings comes from |
| **Turnaround time** | Time from case creation to decision-ready-for-review | The direct measure of whether backlog and SAR-deadline risk actually improve |

Together these metrics are meant to guard against optimizing for speed at
the expense of correctness and defensibility: a faster system that is wrong
or uncitable is not a win for this team.
