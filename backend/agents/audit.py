"""Audit logging stage: persists the full case trace as an append-only, tamper-evident record.

Per SECURITY.md's audit-log integrity requirements, this table is
append-only *at the schema level*, not merely by application convention:
a BEFORE UPDATE OR DELETE trigger rejects any attempt to modify or remove
an existing row, regardless of which code path issues it. Application
code must never attempt to UPDATE or DELETE a row in audit_log - a
correction to a past decision must be recorded as a new row referencing
the original case_id, never as an edit to the original entry.

Because of that, a single case_id can accumulate multiple rows over time -
e.g. if pipeline logic changes and the case is reprocessed. The latest row
per case_id (highest id, or most recent created_at) is the current/
authoritative decision; earlier rows are not wrong, they're the historical
record of what the pipeline decided and why at that point in time. To read
just the current decision per case:

    SELECT DISTINCT ON (case_id) *
    FROM audit_log
    ORDER BY case_id, created_at DESC;
"""

import json

import asyncpg

from agents.decisioning import Decision
from agents.screening import ScreeningResult
from agents.scoring import RiskScore
from data.schema import Case
from db import get_connection

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    case_id TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    screening_result JSONB NOT NULL,
    risk_score JSONB NOT NULL,
    primary_citation TEXT NOT NULL,
    disposition TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Defensive integrity check, distinct from Python's Disposition Literal type:
# a typo'd disposition string should never be silently logged. Applied via
# ALTER rather than a table-definition CHECK so it also backfills onto the
# table created before REVIEW existed; guarded against re-running on an
# existing table below.
ADD_DISPOSITION_CHECK_SQL = """
ALTER TABLE audit_log
ADD CONSTRAINT audit_log_disposition_check
CHECK (disposition IN ('ESCALATE', 'REVIEW', 'CLEAR'));
"""

# Enforces the append-only invariant in Postgres itself: no UPDATE or DELETE
# on audit_log is permitted, from any caller, ever.
CREATE_TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION audit_log_prevent_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

CREATE_TRIGGER_SQL = """
CREATE TRIGGER audit_log_append_only
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_modification();
"""


async def _ensure_schema(conn) -> None:
    await conn.execute(CREATE_TABLE_SQL)
    try:
        await conn.execute(ADD_DISPOSITION_CHECK_SQL)
    except asyncpg.exceptions.DuplicateObjectError:
        pass  # constraint already exists from a prior run
    await conn.execute(CREATE_TRIGGER_FUNCTION_SQL)
    await conn.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log;")
    await conn.execute(CREATE_TRIGGER_SQL)


async def log_decision(
    case: Case,
    screening_result: ScreeningResult,
    risk_score: RiskScore,
    decision: Decision,
) -> None:
    """Inserts one append-only audit_log row for a completed case decision."""
    conn = await get_connection()
    try:
        await _ensure_schema(conn)
        await conn.execute(
            """
            INSERT INTO audit_log
                (case_id, customer_name, screening_result, risk_score, primary_citation, disposition)
            VALUES ($1, $2, $3, $4, $5, $6);
            """,
            case.case_id,
            case.customer_name,
            json.dumps(screening_result),
            json.dumps(risk_score),
            decision["primary_citation"],
            decision["disposition"],
        )
    finally:
        await conn.close()
