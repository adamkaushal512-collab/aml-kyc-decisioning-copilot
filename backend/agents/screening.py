"""Sanctions/PEP screening stage: screens the resolved entity against the local mock watchlist.

Uses rapidfuzz's token_sort_ratio, which tokenizes and sorts each name
before comparing, so it isn't thrown off by reordering (e.g. "Bramholt,
Viktor" vs "Viktor Bramholt") the way a plain character-sequence match
would be. See ARCHITECTURE.md stage 3/4 for the full design intent.
"""

import json
from pathlib import Path
from typing import TypedDict

from rapidfuzz import fuzz, utils

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
    return fuzz.token_sort_ratio(a, b, processor=utils.default_process) / 100.0


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
