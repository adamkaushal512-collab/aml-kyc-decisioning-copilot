import { useEffect, useState } from 'react'
import './App.css'

const API_BASE = 'http://localhost:8000'

interface CaseSummary {
  case_id: string
  customer_name: string
  case_type: string
  transaction_amount: number | null
}

interface ScreeningResult {
  matched: boolean
  matched_name: string | null
  matched_source: string | null
  similarity: number
}

interface RiskScore {
  risk_score: number
  risk_tier: string
  rule_tier: string
  ml_tier: string
}

interface PolicyChunk {
  source_file: string
  chunk_text: string
  similarity: number
}

interface Decision {
  text: string
  disposition: 'ESCALATE' | 'REVIEW' | 'CLEAR'
  primary_citation: string
}

interface AuditLogEntry {
  id: number
  case_id: string
  customer_name: string
  screening_result: ScreeningResult
  risk_score: RiskScore
  primary_citation: string
  disposition: string
  created_at: string
}

interface RunResult {
  case: {
    case_id: string
    customer_name: string
    customer_id: string
    case_type: string
    transaction_amount: number | null
    transaction_type: string | null
  }
  screening_result: ScreeningResult
  risk_score: RiskScore
  policy_chunks: PolicyChunk[]
  decision: Decision
  audit_log_entry: AuditLogEntry | null
}

const DISPOSITION_STYLES: Record<string, { bg: string; fg: string }> = {
  ESCALATE: { bg: '#fee2e2', fg: '#991b1b' },
  REVIEW: { bg: '#fef3c7', fg: '#92400e' },
  CLEAR: { bg: '#dcfce7', fg: '#166534' },
}

function parseCitation(citation: string): { source: string; text: string } {
  const match = citation.match(/^\[(.+?)\]\s*([\s\S]*)$/)
  if (!match) return { source: '', text: citation }
  return { source: match[1], text: match[2] }
}

function formatAmount(amount: number | null): string {
  if (amount == null) return 'n/a'
  return `$${amount.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

function App() {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [selectedCaseId, setSelectedCaseId] = useState('')
  const [result, setResult] = useState<RunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/cases`)
      .then((res) => {
        if (!res.ok) throw new Error(`GET /cases failed with ${res.status}`)
        return res.json() as Promise<CaseSummary[]>
      })
      .then((data) => {
        setCases(data)
        if (data.length > 0) setSelectedCaseId(data[0].case_id)
      })
      .catch(() => setError('Could not load cases from the backend. Is it running on localhost:8000?'))
  }, [])

  async function runPipeline() {
    if (!selectedCaseId) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch(`${API_BASE}/cases/${selectedCaseId}/run`, { method: 'POST' })
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string }
        throw new Error(body.detail ?? `Request failed with status ${res.status}`)
      }
      setResult((await res.json()) as RunResult)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong running the pipeline.')
    } finally {
      setLoading(false)
    }
  }

  const dispositionStyle = result ? DISPOSITION_STYLES[result.decision.disposition] : undefined
  const citation = result ? parseCitation(result.decision.primary_citation) : null

  return (
    <div className="page">
      <header className="page-header">
        <h1>AML/KYC Decisioning Copilot</h1>
        <p className="subtitle">
          Pick a case, run it through the pipeline, and see the decision, its citation, and the
          audit record it produced.
        </p>
      </header>

      <section className="controls">
        <label htmlFor="case-select">Case</label>
        <select
          id="case-select"
          value={selectedCaseId}
          onChange={(e) => setSelectedCaseId(e.target.value)}
          disabled={cases.length === 0}
        >
          {cases.map((c) => (
            <option key={c.case_id} value={c.case_id}>
              {c.case_id} — {c.customer_name}
              {c.transaction_amount != null ? ` (${formatAmount(c.transaction_amount)})` : ''}
            </option>
          ))}
        </select>
        <button onClick={runPipeline} disabled={loading || !selectedCaseId}>
          {loading ? 'Running…' : 'Run Pipeline'}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      {result && (
        <section className="results">
          <div className="disposition-row">
            <span className="disposition-badge" style={{ background: dispositionStyle?.bg, color: dispositionStyle?.fg }}>
              {result.decision.disposition}
            </span>
            <span className="disposition-case">
              {result.case.case_id} — {result.case.customer_name}
            </span>
          </div>

          <div className="grid">
            <div className="card">
              <h2>Case</h2>
              <dl>
                <dt>Customer</dt>
                <dd>
                  {result.case.customer_name} ({result.case.customer_id})
                </dd>
                <dt>Case type</dt>
                <dd>{result.case.case_type}</dd>
                <dt>Transaction amount</dt>
                <dd>{formatAmount(result.case.transaction_amount)}</dd>
              </dl>
            </div>

            <div className="card">
              <h2>Risk</h2>
              <dl>
                <dt>Risk tier</dt>
                <dd>
                  {result.risk_score.risk_tier.toUpperCase()} (score {result.risk_score.risk_score.toFixed(2)})
                </dd>
                <dt>Rule / ML components</dt>
                <dd>
                  rule: {result.risk_score.rule_tier}, ml: {result.risk_score.ml_tier}
                </dd>
                <dt>Screening match</dt>
                <dd>
                  {result.screening_result.matched
                    ? `Yes — ${result.screening_result.matched_name} (${result.screening_result.matched_source}), ${(result.screening_result.similarity * 100).toFixed(1)}% similarity`
                    : `No match (best: ${(result.screening_result.similarity * 100).toFixed(1)}% similarity)`}
                </dd>
              </dl>
            </div>

            <div className="card citation-card">
              <h2>Primary Policy Citation</h2>
              <p className="citation-source">{citation?.source}</p>
              <p className="citation-text">{citation?.text}</p>
            </div>

            <div className="card">
              <h2>Decision Rationale</h2>
              <p className="decision-text">{result.decision.text}</p>
            </div>
          </div>

          <div className="card">
            <h2>Audit Trail Entry</h2>
            {result.audit_log_entry ? (
              <pre className="audit-json">{JSON.stringify(result.audit_log_entry, null, 2)}</pre>
            ) : (
              <p>No audit log entry was found for this case.</p>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

export default App
