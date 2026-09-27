import { decisionLabel, inr, riskTone } from "../api";
import type { Row } from "../types";

export function Queue({
  rows,
  scope,
  setScope,
  selected,
  onSelect,
}: {
  rows: Row[];
  scope: "queue" | "history";
  setScope: (s: "queue" | "history") => void;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <nav className="queue">
      <div className="tabs">
        <button className={scope === "queue" ? "on" : ""} onClick={() => setScope("queue")}>
          Review queue
        </button>
        <button className={scope === "history" ? "on" : ""} onClick={() => setScope("history")}>
          Closed history
        </button>
      </div>
      <ul>
        {rows.map((r) => (
          <li
            key={r.claim_id}
            className={`q-item ${selected === r.claim_id ? "sel" : ""}`}
            onClick={() => onSelect(r.claim_id)}
          >
            <div className="q-top">
              <span className="mono q-id">{r.claim_id.replace("CLM-2026-", "#")}</span>
              <span className={`pill line ${r.line}`}>{r.line}</span>
              <span className="q-date">{r.intimation_date.slice(5)}</span>
            </div>
            <div className="q-sum">{r.summary}</div>
            <div className="q-bottom">
              <span className="muted">{r.claimant}</span>
              {r.risk != null ? (
                <span className={`risk-chip ${riskTone(r.risk)}`} title={`Stateless: ${r.stateless_risk}`}>
                  {r.stateless_risk}→{r.risk}
                </span>
              ) : r.decision ? (
                <span className={`pill dec ${r.decision}`}>{decisionLabel[r.decision] || r.decision}</span>
              ) : (
                <span className="muted">{inr(r.claimed_amount)}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </nav>
  );
}
