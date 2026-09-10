"""Sanctions/PEP screening stage: screens the resolved entity against the local mock watchlist.

Uses simple stdlib fuzzy string matching (difflib) as a v1 stand-in for a real
fuzzy-matching library; see ARCHITECTURE.md stage 3/4 for the full design intent.
"""

import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import TypedDict

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "mock_watchlist.json"

# Aligned with the placeholder policy snippet in retrieval.py, which cites a
# 90% similarity threshold for escalation.
MATCH_THRESHOLD = 0.90


class ScreeningResult(TypedDict):
    matched: bool
    matched_name: str | None
    matched_source: str | None
    similarity: float


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def screen_name(name: str, path: Path = WATCHLIST_PATH) -> ScreeningResult:
    """Fuzzy-matches a name against the mock watchlist and returns the best hit."""
    watchlist = json.loads(path.read_text())

    best_entry = None
    best_score = 0.0
    for entry in watchlist:
        score = _similarity(name, entry["name"])
        if score > best_score:
            best_score = score
            best_entry = entry

    return {
        "matched": best_score >= MATCH_THRESHOLD,
        "matched_name": best_entry["name"] if best_entry else None,
        "matched_source": best_entry["source"] if best_entry else None,
        "similarity": round(best_score, 4),
    }
