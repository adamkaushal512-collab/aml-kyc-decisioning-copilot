"""Evaluates the pipeline against backend/data/golden_set.json.

Runs all 17 golden cases through the pipeline's core stages (screening,
scoring, retrieval, decisioning - calling those stage functions directly
rather than going through agents/graph.py, since this is an eval harness,
not a production case run: it shouldn't write to audit_log or emit
production Langfuse traces). Compares actual output to each case's
ground truth and reports:

- Decision accuracy: % of cases where the actual disposition matches
  expected_disposition (any parenthetical annotation, e.g. "REVIEW
  (partially resolved...)", is stripped to its leading token first).
- Citation accuracy: % of cases where the primary citation's
  (source_file, clause number) matches expected_citation_clause.
- Screening flag TPR/FPR: screening_result["matched"] (the strict >=90%
  boolean) against each case's true_watchlist_match ground truth field -
  i.e. whether the name genuinely is a variant of a real watchlist entity,
  independent of whether it crosses the 90% threshold. Labeled "flag" TPR
  specifically because it understates recall for anything landing in the
  75-89% REVIEW band - see effective catch rate below for that.
- Effective catch rate: among true watchlist matches, the % that reach an
  actionable disposition (ESCALATE or REVIEW) rather than being silently
  cleared - the more meaningful "did the system actually flag this"
  number, since REVIEW-band matches never trip the raw matched flag.
- RAGAS faithfulness and context_precision on the retrieved citation
  chunks vs. the decision text, IF an LLM is configured.

Usage: python scripts/run_eval.py

RAGAS scoring requires OPENAI_API_KEY in the environment (it needs an LLM
to judge faithfulness/context_precision - there's no way to compute these
without one). Without it, decision accuracy, citation accuracy, and
screening TPR/FPR are still computed in full; the RAGAS columns print as
"N/A" with a note on what's needed to enable them.
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from agents.decisioning import decide  # noqa: E402
from agents.intake import load_case  # noqa: E402
from agents.retrieval import PolicyChunk, retrieve_policy_chunks  # noqa: E402
from agents.screening import screen_name  # noqa: E402
from agents.scoring import score_case  # noqa: E402

GOLDEN_SET_PATH = BACKEND_DIR / "data" / "golden_set.json"
RAGAS_MODEL = "gpt-4o-mini"

CITATION_CLAUSE_RE = re.compile(r"([\w.]+\.md)\s+clause\s+(\d+)")
CHUNK_CLAUSE_NUMBER_RE = re.compile(r"^(\d+)\.")


def _parse_expected_disposition(raw: str) -> str:
    """Strips any parenthetical annotation, e.g. 'REVIEW (partially resolved...)' -> 'REVIEW'."""
    return raw.split(" (")[0].strip()


def _parse_expected_citation(raw: str) -> tuple[str, str] | None:
    """Parses 'NN_doc_name.md clause N' -> ('NN_doc_name.md', 'N'). Returns None if unparseable."""
    match = CITATION_CLAUSE_RE.search(raw)
    if not match:
        return None
    return match.group(1), match.group(2)


def _actual_citation(chunk: PolicyChunk) -> tuple[str, str | None]:
    """Extracts (source_file, clause_number) from a retrieved chunk's leading 'N. ' marker."""
    match = CHUNK_CLAUSE_NUMBER_RE.match(chunk["chunk_text"])
    return chunk["source_file"], match.group(1) if match else None


def _try_build_ragas_metrics():
    """Returns (faithfulness_metric, context_precision_metric) if an LLM is configured, else (None, None)."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, None
    try:
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
        from ragas.metrics.collections import ContextPrecisionWithoutReference, Faithfulness

        client = AsyncOpenAI(api_key=api_key)
        llm = llm_factory(RAGAS_MODEL, client=client)
        return Faithfulness(llm=llm), ContextPrecisionWithoutReference(llm=llm)
    except Exception as exc:  # pragma: no cover - defensive; RAGAS is optional here
        print(f"Warning: could not initialize RAGAS metrics ({exc}); continuing without them.\n")
        return None, None


async def _score_ragas(faithfulness_metric, context_precision_metric, user_input, response, contexts):
    from ragas import SingleTurnSample

    sample = SingleTurnSample(user_input=user_input, response=response, retrieved_contexts=contexts)
    faithfulness_score = await faithfulness_metric.single_turn_ascore(sample)
    context_precision_score = await context_precision_metric.single_turn_ascore(sample)
    return faithfulness_score, context_precision_score


async def _evaluate_case(entry: dict, faithfulness_metric, context_precision_metric) -> dict:
    case = load_case(entry["case_id"], path=GOLDEN_SET_PATH)
    screening_result = screen_name(case.customer_name)
    risk_score = score_case(case, screening_result)
    policy_chunks = await retrieve_policy_chunks(screening_result, risk_score)
    decision = decide(case, screening_result, policy_chunks, risk_score)

    expected_disposition = _parse_expected_disposition(entry["expected_disposition"])
    actual_disposition = decision["disposition"]

    expected_citation = _parse_expected_citation(entry["expected_citation_clause"])
    actual_citation = _actual_citation(policy_chunks[0])
    citation_match = expected_citation is not None and expected_citation == actual_citation

    faithfulness_score = None
    context_precision_score = None
    if faithfulness_metric is not None:
        contexts = [chunk["chunk_text"] for chunk in policy_chunks]
        user_input = (
            f"Why was case {case.case_id} for {case.customer_name} "
            f"dispositioned as {actual_disposition}?"
        )
        faithfulness_score, context_precision_score = await _score_ragas(
            faithfulness_metric, context_precision_metric, user_input, decision["text"], contexts
        )

    return {
        "case_id": entry["case_id"],
        "category": entry["category"],
        "expected_disposition": expected_disposition,
        "actual_disposition": actual_disposition,
        "disposition_match": expected_disposition == actual_disposition,
        "citation_match": citation_match,
        "true_watchlist_match": entry["true_watchlist_match"],
        "predicted_matched": screening_result["matched"],
        "faithfulness": faithfulness_score,
        "context_precision": context_precision_score,
    }


def _print_table(results: list[dict]) -> None:
    header = (
        f"{'case_id':12} {'expected':10} {'actual':10} {'match':6} "
        f"{'faithfulness':13} {'ctx_precision':13}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        faith = f"{r['faithfulness']:.3f}" if r["faithfulness"] is not None else "N/A"
        ctxp = f"{r['context_precision']:.3f}" if r["context_precision"] is not None else "N/A"
        match = "yes" if r["disposition_match"] else "NO"
        print(
            f"{r['case_id']:12} {r['expected_disposition']:10} {r['actual_disposition']:10} "
            f"{match:6} {faith:13} {ctxp:13}"
        )
    print()


def _print_aggregates(results: list[dict], ragas_enabled: bool) -> None:
    n = len(results)
    n_disposition_correct = sum(r["disposition_match"] for r in results)
    n_citation_correct = sum(r["citation_match"] for r in results)

    tp = fn = fp = tn = 0
    for r in results:
        truth, predicted = r["true_watchlist_match"], r["predicted_matched"]
        if truth and predicted:
            tp += 1
        elif truth and not predicted:
            fn += 1
        elif not truth and predicted:
            fp += 1
        else:
            tn += 1

    tpr = tp / (tp + fn) if (tp + fn) else float("nan")
    fpr = fp / (fp + tn) if (fp + tn) else float("nan")

    # Effective catch rate: among true watchlist matches, how many end up at
    # an actionable disposition (ESCALATE or REVIEW) rather than CLEAR - this
    # is what the system as a whole actually catches, as distinct from the
    # raw screening_result["matched"] flag above, which only fires at >=90%
    # and so understates recall for anything landing in the REVIEW band.
    true_positives = [r for r in results if r["true_watchlist_match"]]
    n_actionable = sum(r["actual_disposition"] in ("ESCALATE", "REVIEW") for r in true_positives)
    catch_rate = n_actionable / len(true_positives) if true_positives else float("nan")

    print(f"Cases evaluated: {n}")
    print(f"Overall decision accuracy: {n_disposition_correct / n:.1%} ({n_disposition_correct}/{n})")
    print(f"Citation accuracy (doc + clause): {n_citation_correct / n:.1%} ({n_citation_correct}/{n})")

    if ragas_enabled:
        faith_scores = [r["faithfulness"] for r in results if r["faithfulness"] is not None]
        ctxp_scores = [r["context_precision"] for r in results if r["context_precision"] is not None]
        avg_faith = sum(faith_scores) / len(faith_scores) if faith_scores else float("nan")
        avg_ctxp = sum(ctxp_scores) / len(ctxp_scores) if ctxp_scores else float("nan")
        print(f"Average faithfulness: {avg_faith:.3f}")
        print(f"Average context precision: {avg_ctxp:.3f}")
    else:
        print("Average faithfulness: N/A - set OPENAI_API_KEY to enable RAGAS scoring")
        print("Average context precision: N/A - set OPENAI_API_KEY to enable RAGAS scoring")

    print(
        f"Screening flag TPR (90%+ only): {tpr:.1%} "
        f"({tp}/{tp + fn} true watchlist matches with screening_result['matched']=True) "
        f"- NOT the system's overall detection rate, see effective catch rate below"
    )
    print(
        f"Screening flag FPR: {fpr:.1%} "
        f"({fp}/{fp + tn} non-matches incorrectly flagged)"
    )
    print(
        f"Effective catch rate (ESCALATE or REVIEW): {catch_rate:.1%} "
        f"({n_actionable}/{len(true_positives)} true watchlist matches reaching an actionable "
        f"disposition, not silently cleared)"
    )


async def main() -> None:
    cases = json.loads(GOLDEN_SET_PATH.read_text())

    faithfulness_metric, context_precision_metric = _try_build_ragas_metrics()
    ragas_enabled = faithfulness_metric is not None
    if not ragas_enabled:
        print(
            f"RAGAS scoring disabled: set OPENAI_API_KEY in .env to enable "
            f"faithfulness/context_precision scoring against {RAGAS_MODEL}.\n"
        )

    results = [
        await _evaluate_case(entry, faithfulness_metric, context_precision_metric) for entry in cases
    ]

    _print_table(results)
    _print_aggregates(results, ragas_enabled)


if __name__ == "__main__":
    asyncio.run(main())
