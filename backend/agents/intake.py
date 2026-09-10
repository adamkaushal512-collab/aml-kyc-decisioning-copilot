"""Intake stage: receives a case (alert or KYC refresh trigger) and its raw supporting data."""

import json
from pathlib import Path

from data.schema import Case

SAMPLE_CASES_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_cases.json"


def load_case(case_id: str, path: Path = SAMPLE_CASES_PATH) -> Case:
    """Loads and validates a single case by case_id from a cases JSON file."""
    cases = json.loads(path.read_text())
    for raw in cases:
        if raw["case_id"] == case_id:
            return Case(**raw)
    raise ValueError(f"No case found with case_id={case_id!r} in {path}")
