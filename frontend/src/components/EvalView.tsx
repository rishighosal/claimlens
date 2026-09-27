import { useEffect, useState } from "react";
import { api, inr } from "../api";

type Arm = { precision: number; recall: number; f1: number; tp: number; fp: number; fn: number; flagged: number; fraud_amount_caught: number };
type Win = { label: string; n: number; fraud: number; with_memory_recall: number | null; stateless_recall: number | null; with_memory_fp: number; stateless_fp: number };
type PC = { claim_id: string; date: string; label: string; ring: string | null; with_memory: number; stateless: number };

const RING_NAME: Record<string, string> = {
  R1: "Garage + surveyor collusion",
  R2: "Hospital admission ring",
  R3: "Early-claim intermediary",
  R4: "Recycled vehicle damage",
};

function pct(x: number | null | undefined) {
  return x == null ? "–" : `${Math.round(x * 100)}%`;
}

function RecallChart({ windows }: { windows: Win[] }) {
  const W = 640, H = 250, L = 44, R = 16, T = 30, B = 34;
  const pts = windows.filter((w) => w.fraud > 0);
  const x = (i: number) => L + (i * (W - L - R)) / Math.max(pts.length - 1, 1);
  const y = (v: number) => T + (1 - v) * (H - T - B);
  const line = (k: "with_memory_recall" | "stateless_recall") =>
    pts.map((w, i) => `${i ? "L" : "M"}${x(i)},${y(w[k] ?? 0)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Share of fraud caught per month, with and without memory">
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <g key={g}>
          <line x1={L} x2={W - R} y1={y(g)} y2={y(g)} className="grid" />
          <text x={L - 8} y={y(g)} className="axis" textAnchor="end" dominantBaseline="central">{Math.round(g * 100)}%</text>
        </g>
      ))}
      {pts.map((w, i) => (
        <text key={w.label} x={x(i)} y={H - 12} className="axis" textAnchor="middle">{w.label}</text>
      ))}
      <path d={line("stateless_recall")} className="series stateless" />
      <path d={line("with_memory_recall")} className="series memory" />
      {pts.map((w, i) => (
        <g key={w.label + "p"}>
          <circle cx={x(i)} cy={y(w.stateless_recall ?? 0)} r={4} className="pt stateless"><title>{`${w.label}: ${pct(w.stateless_recall)} without memory`}</title></circle>
          <circle cx={x(i)} cy={y(w.with_memory_recall ?? 0)} r={4.5} className="pt memory"><title>{`${w.label}: ${pct(w.with_memory_recall)} with memory (${w.fraud} fraud claims)`}</title></circle>
        </g>
      ))}
      <g transform={`translate(${L + 8}, 12)`}>
        <line x1={0} x2={18} y1={0} y2={0} className="series memory" />
        <text x={24} y={0} dominantBaseline="central" className="series-label memory">with Hindsight</text>
        <line x1={130} x2={148} y1={0} y2={0} className="series stateless" />
        <text x={154} y={0} dominantBaseline="central" className="series-label stateless">without memory</text>
      </g>
    </svg>
  );
}

function RingTimeline({ claims, threshold }: { claims: PC[]; threshold: number }) {
  const rings = ["R1", "R2", "R3", "R4"].filter((r) => claims.some((c) => c.ring === r));
  return (
    <div className="rings">
      {rings.map((r) => {
        const cs = claims.filter((c) => c.ring === r).sort((a, b) => a.date.localeCompare(b.date));
        return (
          <div key={r} className="ring-row">
            <div className="ring-name">
              <b>{RING_NAME[r]}</b>
              <span className="muted small">{cs.length} claims</span>
            </div>
            <div className="ring-dots">
              {cs.map((c, i) => {
                const caught = c.with_memory >= threshold;
                return (
                  <span
                    key={c.claim_id}
                    className={`rdot ${caught ? "caught" : "missed"} ${c.stateless >= threshold ? "both" : ""}`}
                    title={`${c.claim_id} · ${c.date}\nwith memory ${c.with_memory} · without ${c.stateless}`}
                  >
                    {i + 1}
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}
      <div className="legend">
        <span><i className="lg caught" /> flagged with memory</span>
        <span><i className="lg missed" /> not flagged</span>
        <span><i className="lg both" /> also flagged without memory</span>
      </div>
    </div>
  );
}

export function EvalView() {
  const [d, setD] = useState<any>(null);
  useEffect(() => {
    api.evalResults().then(setD, () => setD({ available: false }));
  }, []);
  if (!d) return <div className="panel pad"><div className="skeleton" /></div>;
  if (!d.available) {
    return (
      <div className="panel pad eval-empty">
        <h2>Does memory actually help? Measure it.</h2>
        <p>
          The replay evaluation plays nine months of claims through ClaimLens in date order. Each claim is scored twice by
          the same model: once alone, once with Hindsight memory. After each claim it is retained, and investigator
          outcomes are retained on the day they were decided, so memory only ever knows the past.
        </p>
        <pre>python scripts/replay_eval.py --sample 70</pre>
      </div>
    );
  }
  const m: Arm = d.summary.with_memory;
  const s: Arm = d.summary.stateless;
  return (
    <div className="eval">
      {d.mode !== "hindsight" && (
        <div className="banner warn">
          These numbers come from the offline stand-in (no Hindsight, rule-based model). They only check that the
          pipeline runs. Run the replay with Hindsight and a real model for real results.
        </div>
      )}
      <section className="panel pad">
        <h2>Replay: {d.n_total} claims, {d.n_scored} scored, in date order</h2>
        <p className="muted">
          Same model ({d.model}), same prompt. The only difference is Hindsight memory. A claim is “flagged” at risk ≥{" "}
          {d.threshold}.
        </p>
        <div className="kpis">
          <div className="kpi memory">
            <span className="k">Fraud caught with memory</span>
            <b>{pct(m.recall)}</b>
            <span className="small">{m.tp} of {m.tp + m.fn} fraud claims · precision {pct(m.precision)}</span>
          </div>
          <div className="kpi">
            <span className="k">Fraud caught without memory</span>
            <b>{pct(s.recall)}</b>
            <span className="small">{s.tp} of {s.tp + s.fn} · precision {pct(s.precision)}</span>
          </div>
          <div className="kpi">
            <span className="k">Fraud value stopped</span>
            <b>{inr(m.fraud_amount_caught)}</b>
            <span className="small">vs {inr(s.fraud_amount_caught)} without memory</span>
          </div>
          <div className="kpi">
            <span className="k">Genuine claims flagged</span>
            <b>{m.fp}</b>
            <span className="small">vs {s.fp} without memory</span>
          </div>
        </div>
      </section>
      <section className="two-col">
        <div className="panel pad">
          <h2>Fraud caught, month by month</h2>
          <RecallChart windows={d.windows} />
        </div>
        <div className="panel pad">
          <h2>Each fraud ring, claim by claim</h2>
          <p className="muted small">The first claims of a new ring are missed; nothing is in memory yet. The rest are caught once memory links them.</p>
          <RingTimeline claims={d.per_claim} threshold={d.threshold} />
        </div>
      </section>
    </div>
  );
}
