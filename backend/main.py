import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.graph import run_pipeline
from db import get_connection

app = FastAPI(title="AML/KYC Decisioning Copilot")

# Local dev only: allows the Vite dev server (a different origin/port) to
# call this API directly, without a proxy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_CASES_PATH = Path(__file__).resolve().parent / "data" / "sample_cases.json"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/cases")
def list_cases() -> list[dict]:
    """Lists the sample cases available to run through the pipeline (for the demo UI's case picker)."""
    cases = json.loads(SAMPLE_CASES_PATH.read_text())
    return [
        {
            "case_id": case["case_id"],
            "customer_name": case["customer_name"],
            "case_type": case["case_type"],
            "transaction_amount": case.get("transaction_amount"),
        }
        for case in cases
    ]


@app.post("/cases/{case_id}/run")
async def run_case(case_id: str) -> dict:
    """Runs one case through the full pipeline and returns the decision plus the persisted audit_log row."""
    try:
        final_state = await run_pipeline(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    conn = await get_connection()
    try:
        audit_row = await conn.fetchrow(
            """
            SELECT id, case_id, customer_name, screening_result, risk_score,
                   primary_citation, disposition, created_at
            FROM audit_log
            WHERE case_id = $1
            ORDER BY id DESC
            LIMIT 1;
            """,
            case_id,
        )
    finally:
        await conn.close()

    audit_log_entry = None
    if audit_row is not None:
        audit_log_entry = dict(audit_row)
        audit_log_entry["screening_result"] = json.loads(audit_log_entry["screening_result"])
        audit_log_entry["risk_score"] = json.loads(audit_log_entry["risk_score"])

    case = final_state["case"]
    return {
        "case": {
            "case_id": case.case_id,
            "customer_name": case.customer_name,
            "customer_id": case.customer_id,
            "case_type": case.case_type,
            "transaction_amount": case.transaction_amount,
            "transaction_type": case.transaction_type,
        },
        "screening_result": final_state["screening_result"],
        "risk_score": final_state["risk_score"],
        "policy_chunks": final_state["policy_chunks"],
        "decision": final_state["decision"],
        "audit_log_entry": audit_log_entry,
    }
