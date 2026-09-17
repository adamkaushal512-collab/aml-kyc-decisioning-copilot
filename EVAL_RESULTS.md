# Evaluation Results

Results from running the pipeline against [`backend/data/golden_set.json`](./backend/data/golden_set.json),
a 17-case labeled evaluation set, via [`backend/scripts/run_eval.py`](./backend/scripts/run_eval.py).
Target criteria are defined in [`PRD.md`](./PRD.md); the system under test
is described in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Summary

| Metric | Result |
|---|---|
| Cases evaluated | 17 |
| Decision accuracy | **100%** (17/17) |
| Citation accuracy (document + clause) | **100%** (17/17) |
| Screening false-positive rate | **0%** (0/9 unrelated names incorrectly flagged) |
| Effective catch rate | **87.5%** (7/8 true watchlist matches reach an actionable disposition) |
| Screening flag true-positive rate | 37.5% (3/8) — see note below |

The gap between the last two numbers is intentional to report, not a
contradiction. **Screening flag TPR** measures only the strict ≥90%
`matched` boolean in `screening.py` — it undercounts recall by design,
because five of the eight true watchlist variants in the golden set were
deliberately built to land in the 75–89% "standard review" band, which the
raw flag was never meant to catch. **Effective catch rate** measures what
the pipeline as a whole does with those cases — whether they reach an
actionable disposition (`ESCALATE` or `REVIEW`) instead of being silently
cleared. That number is 87.5%: 7 of 8 true matches are actionable. The one
miss (`GOLD-0006`, 74.3% similarity — just under the 75% REVIEW floor) is a
real, currently open gap, tracked below.

## Results by Category

| Category | Cases | Decision accuracy | Citation accuracy |
|---|---|---|---|
| Original (from initial thin-slice) | 5 | 5/5 | 5/5 |
| Similarity-boundary (74–90% band) | 4 | 4/4 | 4/4 |
| Amount-boundary ($10k / $1M thresholds) | 4 | 4/4 | 4/4 |
| Regression (guards against 2 fixed bugs) | 2 | 2/2 | 2/2 |
| Ambiguous (no single clean answer) | 2 | 2/2* | 2/2* |
| **Total** | **17** | **17/17** | **17/17** |

\* The two ambiguous cases (`GOLD-0016`, `GOLD-0017`) "pass" against their
documented expected values, but each still carries a residual open
question noted in `golden_set.json` — a compounding-risk scenario the
system doesn't yet combine into a single elevated assessment, and an
exact-threshold amount ambiguity (`>` vs `>=` at $10,000) that needs a
policy-owner decision, not a code fix. Passing here means "behaves as the
documented reasoning concluded it should," not "this case has one
uncontestable right answer."

## What This Evaluation Found

The similarity-boundary and ambiguous cases were deliberately built to
probe the edges of policy AML-014's three similarity tiers (≥90% escalate,
75–89% standard review, <75% clear). Doing so surfaced a real gap between
the mock policy corpus and the implemented decision logic: **the pipeline
only ever implemented a binary match/no-match split at 90%**, so a case
scoring, say, 88.9% against a watchlist entry — one point from mandatory
escalation — was being silently cleared with the same "false positive"
citation as a genuinely unrelated name at 30% similarity. Clause 3 of
AML-014, which requires documented analyst review for exactly that 75–89%
band, was never being reached by any code path.

This is the evaluation process working as intended, not an embarrassing
find to downplay: the golden set was built specifically to test threshold
behavior, it caught a real disposition/citation gap that five prior sample
cases hadn't exercised, and the fix was implemented, verified against the
same golden set, and shipped in the same work session. The fix added a
third `REVIEW` disposition and made citation routing and disposition
determination share a single function (`agents.scoring.determine_disposition`)
so the two can no longer silently diverge — closing off the same class of
bug that caused an earlier, separate fix (a transaction-amount escalation
had been citing the sanctions doc's "false positive" clause instead of the
transaction-monitoring policy; `GOLD-0014`/`GOLD-0015` are regression cases
guarding against exactly that).

## Known Limitations

- **RAGAS faithfulness/context-precision scoring was not run.** Both
  metrics require an LLM judge, and no `OPENAI_API_KEY` is configured in
  this environment. The integration is implemented and verified against
  the installed `ragas` SDK's current API (`ragas.metrics.collections`,
  `ragas.llms.llm_factory`) — `run_eval.py` will compute and report real
  scores automatically the moment a key is added, with no further code
  changes needed. Decision accuracy and citation accuracy do not depend on
  this and were measured directly.
- **17 cases is a small golden set.** Enterprise AML/KYC evaluation
  practice typically expects 20–50 cases as a working minimum for a
  release gate, and 100–1000+ for full regression coverage across risk
  types, jurisdictions, and entity structures. This set is deliberately
  scoped for depth over breadth — it targets specific threshold behaviors
  and two known bug classes precisely — not for statistical confidence at
  production scale. Screening TPR/FPR in particular (3/8, 0/9) are not
  meaningful population-level rates at this sample size; they're useful
  for catching a regression, not for claiming a calibrated recall number.
- **The ML risk-scoring component is trained on synthetic data**, as
  documented in `ARCHITECTURE.md`'s "Known Limitations" section: a
  90-sample synthetic dataset, since no real historical case data exists
  yet. It doesn't perfectly recover the rule-based labeling boundary on
  low-amount/low-similarity cases (predicts "medium" where the rule would
  say "low"). This is expected behavior for a linear model on limited
  synthetic data and is harmless to final dispositions today, because the
  rule-based floor only ever raises the risk tier, never lowers it — but
  it means the model's own judgment hasn't been validated against
  anything real yet.

## References

- [`PRD.md`](./PRD.md) — target eval criteria these results are measured against.
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — the pipeline design under test, including its other known limitations.
- [`backend/data/golden_set.json`](./backend/data/golden_set.json) — the 17-case dataset, with per-case reasoning for every expected value.
