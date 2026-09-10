"""Runs the thin-slice pipeline end-to-end on a single case.

Usage: python run_pipeline.py [case_id]  (defaults to CASE-0003)
"""

import sys

from agents.graph import run_pipeline

if __name__ == "__main__":
    case_id = sys.argv[1] if len(sys.argv) > 1 else "CASE-0003"
    final_state = run_pipeline(case_id)
    print(final_state["decision"])
