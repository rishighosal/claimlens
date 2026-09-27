import { useEffect, useState } from "react";
import { api, bandLabel, decisionLabel, inr, reasonLabel } from "../api";
import type { ClaimDetail, Investigation, MemoryOp, Reflection } from "../types";
import { RedFlags, VerdictCard } from "./Assessment";
import { EvidenceGraph } from "./EvidenceGraph";

function Field({ k, v, mono }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="field">
      <span className="k">{k}</span>
      <span className={`v ${mono ? "mono" : ""}`}>{v ?? "–"}</span>
    </div>
  );
}

function daysBetween(a: string, b: string) {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86400000);
}

export function ClaimFacts({ c }: { c: Record<string, any> }) {
  const sinceStart = daysBetween(c.policy_start, c.incident_date);
  return (
    <div className="facts">
      <div className="facts-grid">
        <Field k="Claimant" v={c.claimant.name} />
        <Field k="Phone" v={c.claimant.phone} mono />
        <Field k="Address" v={c.claimant.address} />
        <Field k="Payee account" v={c.payee_account} mono />
        <Field k="Policy" v={`${c.policy_no}`} mono />
        <Field
          k="Policy start → incident"
          v={
            <>
              {c.policy_start} → {c.incident_date}{" "}
              <span className={`pill ${sinceStart < 30 ? "warn" : ""}`}>{sinceStart} days</span>
            </>
          }
        />
        <Field k="Intermediary" v={`${c.intermediary.agent_code} · ${c.intermediary.agent_name}`} />
        {c.line === "motor" ? (
          <>
            <Field k="Vehicle" v={`${c.vehicle.registration} · ${c.vehicle.make_model} (${c.vehicle.year})`} />
            <Field k="IDV" v={inr(c.vehicle.idv)} />
            <Field k="Garage" v={c.garage.name} />
            <Field k="Surveyor" v={c.surveyor ? `${c.surveyor.name} (${c.surveyor.id})` : "–"} />
            <Field
              k="Police report"
              v={c.police_report ? `${c.police_report.station} · FIR ${c.police_report.fir_no}` : "None filed"}
            />
          </>
        ) : (
          <>
            <Field k="Hospital" v={c.hospital.name} />
            <Field k="Doctor" v={c.treating_doctor} />
            <Field k="Diagnosis" v={c.diagnosis} />
            <Field k="Stay" v={`${c.admission_date} → ${c.discharge_date} (${c.length_of_stay_days}d)`} />
            <Field k="Sum insured" v={inr(c.sum_insured)} />
          </>
        )}
      </div>
      <blockquote className="narrative">“{c.narrative}”</blockquote>
    </div>
  );
}

const PROBE_STEPS = [
  "Checking every phone number, bank account, vehicle and address against memory",
  "Looking up the garage / hospital, surveyor / doctor and agent history",
  "Searching for claims that tell the same story",
  "Pulling consolidated fraud patterns and recent activity",
  "Weighing evidence with and without memory",
];

export function ClaimView({
  id,
  onOpen,
  onChanged,
  onOps,
}: {
  id: string;
  onOpen: (id: string) => void;
  onChanged: () => void;
  onOps: (ops: MemoryOp[]) => void;
}) {
  const [d, setD] = useState<ClaimDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [brief, setBrief] = useState<Reflection | null>(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const [notes, setNotes] = useState("");
  const [who, setWho] = useState("A. Srilatha (SIU)");
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    setD(null);
    setErr(null);
    setSaved(null);
    setNotes("");
    setBrief(null);
    api.claim(id).then((x) => {
      setD(x);
      setBrief(x.briefing);
    }, (e) => setErr(String(e.message || e)));
  }, [id]);

  useEffect(() => {
    if (!busy) return;
    setStep(0);
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PROBE_STEPS.length - 1)), 1400);
    return () => clearInterval(t);
  }, [busy]);

  if (err && !d) return <div className="panel pad error">{err}</div>;
  if (!d) return <div className="panel pad"><div className="skeleton" /></div>;
  const c = d.claim;
  const inv: Investigation | null = d.investigation;

  async function run() {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.investigate(id);
      setD((x) => (x ? { ...x, investigation: r } : x));
      onOps(r.memory_ops);
      onChanged();
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  async function getBrief() {
    setBriefBusy(true);
    try {
      setBrief(await api.briefing(id));
    } catch (e: any) {
      setErr(e.message || String(e));
    } finally {
      setBriefBusy(false);
    }
  }

  async function decide(decision: string) {
    try {
      const r = await api.decide(id, decision, notes, who);
      setD((x) => (x ? { ...x, decision: r.verdict } : x));
      onOps(r.memory_ops);
      setSaved(decision);
      onChanged();
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  }

  const changed = inv && inv.stateless.band !== inv.with_memory.band;

  return (
    <div className="claim-view">
      <section className="panel">
        <header className="claim-head">
          <div>
            <div className="eyebrow">
              <span className={`pill line ${c.line}`}>{c.line}</span>
              <span>Intimated {c.intimation_date}</span>
              {c.incident_type && <span>· {String(c.incident_type).replace(/_/g, " ")}</span>}
            </div>
            <h1 className="mono">{c.claim_id}</h1>
          </div>
          <div className="amount">
            <span className="k">Claimed</span>
            <span className="big">{inr(c.claimed_amount)}</span>
          </div>
        </header>
        <ClaimFacts c={c} />
        <div className="actions">
          <button className="btn primary" onClick={run} disabled={busy}>
            {busy ? "Investigating…" : inv ? "Re-run investigation" : "Investigate with memory"}
          </button>
          <span className="hint">
            Runs the same model twice: once on the claim alone, once with everything Hindsight remembers.
          </span>
        </div>
        {busy && (
          <ol className="progress">
            {PROBE_STEPS.map((s, i) => (
              <li key={s} className={i < step ? "done" : i === step ? "now" : ""}>{s}</li>
            ))}
          </ol>
        )}
        {err && <div className="error">{err}</div>}
      </section>

      {inv && (
        <>
          <section className="compare">
            <VerdictCard a={inv.stateless} title="Without memory" />
            <div className={`delta ${changed ? "changed" : ""}`}>
              <span className="arrow">→</span>
              <span>{changed ? "Memory changed the call" : "Same call"}</span>
              <span className="delta-num">
                {inv.with_memory.risk_score - inv.stateless.risk_score > 0 ? "+" : ""}
                {inv.with_memory.risk_score - inv.stateless.risk_score}
              </span>
            </div>
            <VerdictCard a={inv.with_memory} title="With Hindsight memory" memory />
          </section>

          <section className="panel pad">
            <h2>Why: evidence from memory</h2>
            <RedFlags a={inv.with_memory} onOpen={onOpen} />
            {inv.with_memory.uncited_ids_removed > 0 && (
              <p className="footnote">
                {inv.with_memory.uncited_ids_removed} claim reference(s) the model produced were not in recalled
                memory and were removed.
              </p>
            )}
          </section>

          <section className="panel pad">
            <div className="row-between">
              <h2>How this claim connects to the past</h2>
              <span className="muted small">
                {inv.linked_claims.length} linked claims · {inv.probes.length} memory probes
              </span>
            </div>
            <EvidenceGraph nodes={inv.graph.nodes} edges={inv.graph.edges} onOpen={onOpen} />
            {inv.linked_claims.length > 0 && (
              <table className="links">
                <thead>
                  <tr>
                    <th>Past claim</th>
                    <th>Linked via</th>
                    <th>What memory recalled</th>
                  </tr>
                </thead>
                <tbody>
                  {inv.linked_claims.slice(0, 8).map((l) => (
                    <tr key={l.claim_id}>
                      <td>
                        <button className="chip link" onClick={() => onOpen(l.claim_id)}>{l.claim_id}</button>
                      </td>
                      <td>
                        {l.reasons.filter((r) => r !== "timeline").map((r) => (
                          <span key={r} className={`chip reason ${r}`}>{reasonLabel[r] || r}</span>
                        ))}
                      </td>
                      <td className="recalled">
                        {l.outcome[0] && <div><b>{l.outcome[0]}</b></div>}
                        {l.facts[0] && <div>{l.facts[0]}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="two-col">
            <div className="panel pad">
              <h2>Verify next</h2>
              <ol className="steps">{inv.with_memory.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              {inv.with_memory.questions_for_claimant.length > 0 && (
                <>
                  <h3>Ask the claimant</h3>
                  <ul className="qs">{inv.with_memory.questions_for_claimant.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </>
              )}
              {inv.with_memory.mitigating_factors.length > 0 && (
                <>
                  <h3>In the claimant's favour</h3>
                  <ul className="qs">{inv.with_memory.mitigating_factors.map((s, i) => <li key={i}>{s}</li>)}</ul>
                </>
              )}
            </div>
            <div className="panel pad">
              <div className="row-between">
                <h2>Investigator briefing</h2>
                <button className="btn ghost" onClick={getBrief} disabled={briefBusy}>
                  {briefBusy ? "Reflecting…" : brief ? "Regenerate" : "Generate with Hindsight reflect"}
                </button>
              </div>
              {brief ? (
                <>
                  <div className="brief">{brief.text}</div>
                  <p className="footnote">
                    Grounded in {brief.memories.length} memories
                    {brief.directives.length > 0 && <> · directives applied: {brief.directives.join(", ")}</>}
                  </p>
                </>
              ) : (
                <p className="muted">
                  Hindsight <code>reflect</code> reasons over the whole memory bank, using the SIU mission and
                  rules of evidence, and writes a briefing for the field investigator.
                </p>
              )}
            </div>
          </section>
        </>
      )}

      <section className="panel pad decision">
        <div className="row-between">
          <h2>Outcome</h2>
          {d.decision && (
            <span className={`pill dec ${d.decision.decision}`}>
              {decisionLabel[d.decision.decision] || d.decision.decision}
              {d.decision.closed_on && <> · {d.decision.closed_on}</>}
            </span>
          )}
        </div>
        {c.status === "closed" && !saved ? (
          <p className="muted">
            Closed historical claim. {d.decision?.notes}
          </p>
        ) : (
          <>
            <p className="muted small">
              Recording an outcome writes it to Hindsight. The next claim that touches the same people, providers or
              story will be judged with this outcome in memory.
            </p>
            <div className="decide-row">
              <input value={who} onChange={(e) => setWho(e.target.value)} placeholder="Investigator" />
              <input
                className="grow"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Findings (e.g. field visit, documents, what didn't add up)"
              />
            </div>
            <div className="decide-row">
              <button className="btn ok" onClick={() => decide("approved")}>Approve</button>
              <button className="btn" onClick={() => decide("cleared")}>Cleared after check</button>
              <button className="btn warn" onClick={() => decide("referred")}>Refer to SIU</button>
              <button className="btn danger" onClick={() => decide("fraud_confirmed")}>Confirm fraud</button>
            </div>
            {saved && (
              <div className="saved">
                Retained in Hindsight: <b>{decisionLabel[saved]}</b>. Memory will use this for the next claim.
              </div>
            )}
          </>
        )}
        {inv && (
          <p className="footnote">
            Recommendation: <b>{bandLabel[inv.with_memory.band]}</b>. ClaimLens recommends; people decide.
          </p>
        )}
      </section>
    </div>
  );
}
