"""Risk scoring stage: combines a deterministic rule floor with an ML risk model.

Rules handle unambiguous cases (a confirmed sanctions/PEP match, or a
transaction size clearly over a policy threshold) by setting a minimum risk
tier that the ML model cannot score below. The ML model (a small scikit-learn
classifier trained on synthetic data, since no real historical case data
exists yet) supplies the more nuanced judgment in between, and can push the
score *above* the rule floor when its signal warrants it. This mirrors
ARCHITECTURE.md's stated hybrid design for stage 7, applied one stage earlier
at the risk-scoring step.
"""

from typing import Literal, TypedDict

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from agents.screening import REVIEW_THRESHOLD, ScreeningResult
from data.schema import Case

Disposition = Literal["ESCALATE", "REVIEW", "CLEAR"]

TIER_ORDER = ["low", "medium", "high"]

# A numeric anchor per tier, used both to bucket the ML model's class
# probabilities into a single continuous score and to give each rule-based
# floor a comparable score on the same scale.
TIER_ANCHOR_SCORE = {"low": 0.15, "medium": 0.55, "high": 0.92}

# Score thresholds for turning a continuous risk_score back into a tier.
# Chosen so each tier's anchor score falls inside its own band.
MEDIUM_SCORE_THRESHOLD = 0.35
HIGH_SCORE_THRESHOLD = 0.75

# Rule-based transaction_amount thresholds (see policy 05_transaction_monitoring_red_flags.md).
ELEVATED_AMOUNT_THRESHOLD = 10_000
HIGH_AMOUNT_THRESHOLD = 1_000_000

RANDOM_SEED = 42
N_SYNTHETIC_SAMPLES = 90


class RiskScore(TypedDict):
    risk_score: float
    risk_tier: str
    rule_tier: str
    ml_tier: str


def _rule_based_tier(case: Case, screening_result: ScreeningResult) -> str:
    """Deterministic risk floor: unambiguous cases get a fixed minimum tier."""
    if screening_result["matched"]:
        return "high"

    amount = case.transaction_amount or 0.0
    if amount > HIGH_AMOUNT_THRESHOLD:
        return "high"
    if amount > ELEVATED_AMOUNT_THRESHOLD:
        return "medium"
    return "low"


def _tier_from_score(score: float) -> str:
    if score >= HIGH_SCORE_THRESHOLD:
        return "high"
    if score >= MEDIUM_SCORE_THRESHOLD:
        return "medium"
    return "low"


def _generate_synthetic_training_data(
    n: int = N_SYNTHETIC_SAMPLES, seed: int = RANDOM_SEED
) -> tuple[np.ndarray, np.ndarray]:
    """Generates a small synthetic labeled dataset: no real historical case data exists yet.

    Features: transaction_amount, screening_similarity_score, is_transaction_alert.
    Labels are assigned from the same thresholds the rule component uses,
    with a little label noise so the model learns a soft decision boundary
    rather than just memorizing the rule.
    """
    rng = np.random.default_rng(seed)

    third = n // 3
    amounts = np.concatenate(
        [
            rng.uniform(0, ELEVATED_AMOUNT_THRESHOLD, size=third),
            rng.uniform(ELEVATED_AMOUNT_THRESHOLD, 200_000, size=third),
            rng.uniform(200_000, 5_000_000, size=n - 2 * third),
        ]
    )
    rng.shuffle(amounts)

    half = n // 2
    similarities = np.concatenate(
        [
            rng.uniform(0.0, 0.5, size=half),
            rng.uniform(0.5, 1.0, size=n - half),
        ]
    )
    rng.shuffle(similarities)

    is_transaction_alert = rng.integers(0, 2, size=n)

    labels = []
    for amount, similarity in zip(amounts, similarities):
        if similarity >= 0.90 or amount > HIGH_AMOUNT_THRESHOLD:
            tier = "high"
        elif similarity >= 0.75 or amount > ELEVATED_AMOUNT_THRESHOLD:
            tier = "medium"
        else:
            tier = "low"

        if rng.random() < 0.08:
            tier = rng.choice([t for t in TIER_ORDER if t != tier])

        labels.append(tier)

    features = np.column_stack([amounts, similarities, is_transaction_alert])
    return features, np.array(labels)


_ml_pipeline: Pipeline | None = None


def _get_ml_pipeline() -> Pipeline:
    global _ml_pipeline
    if _ml_pipeline is None:
        features, labels = _generate_synthetic_training_data()
        pipeline = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000),
        )
        pipeline.fit(features, labels)
        _ml_pipeline = pipeline
    return _ml_pipeline


def score_case(case: Case, screening_result: ScreeningResult) -> RiskScore:
    """Combines the rule-based floor and the ML model's prediction into a final risk score/tier."""
    rule_tier = _rule_based_tier(case, screening_result)

    pipeline = _get_ml_pipeline()
    amount = case.transaction_amount or 0.0
    similarity = screening_result["similarity"]
    is_transaction_alert = 1 if case.case_type == "transaction_alert" else 0
    features = [[amount, similarity, is_transaction_alert]]

    proba = pipeline.predict_proba(features)[0]
    class_labels = list(pipeline.classes_)
    ml_score = float(sum(p * TIER_ANCHOR_SCORE[label] for p, label in zip(proba, class_labels)))
    ml_tier = class_labels[int(proba.argmax())]

    rule_score = TIER_ANCHOR_SCORE[rule_tier]
    risk_score = max(rule_score, ml_score)
    risk_tier = _tier_from_score(risk_score)

    return {
        "risk_score": round(risk_score, 4),
        "risk_tier": risk_tier,
        "rule_tier": rule_tier,
        "ml_tier": ml_tier,
    }


def determine_disposition(screening_result: ScreeningResult, risk_score: RiskScore) -> Disposition:
    """Determines the case's final disposition - the single source of truth for both
    retrieval.py (which document/clause to cite) and decisioning.py (the decision
    text), so they can't silently diverge the way they did before the CASE-0004
    citation-routing bug was fixed.

    A HIGH risk tier always escalates, regardless of what drove it (sanctions
    match, transaction-amount rule, or in principle the ML model alone) - a
    REVIEW-band similarity score never overrides that. Only once risk_tier is
    not HIGH does the 75-89% "standard analyst review" band (policy AML-014
    clause 3) apply; below that is a genuine false positive (clause 4).
    """
    if risk_score["risk_tier"] == "high":
        return "ESCALATE"
    if screening_result["similarity"] >= REVIEW_THRESHOLD:
        return "REVIEW"
    return "CLEAR"
