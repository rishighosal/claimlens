import { useEffect, useState } from "react";
import type { Assessment as A } from "../types";
import { bandLabel, riskTone } from "../api";

function useCountUp(target: number, ms = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms);
      setV(Math.round(target * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}

export function Gauge({ score: target, size = 92 }: { score: number; size?: number }) {
  const score = useCountUp(target);
  const r = size / 2 - 8;
  const c = 2 * Math.PI * r;
  const tone = riskTone(target);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className={`gauge ${tone}`}>
      <circle cx={size / 2} cy={size / 2} r={r} className="track" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        className="fill"
        strokeDasharray={`${(score / 100) * c} ${c}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="gauge-num">
        {score}
      </text>
    </svg>
  );
}

export function VerdictCard({ a, title, memory }: { a: A; title: string; memory?: boolean }) {
  return (
    <div className={`verdict-card ${memory ? "memory" : "stateless"}`}>
      <div className="vc-top">
        <span className="vc-title">
          {memory ? <span className="dot violet" /> : <span className="dot grey" />}
          {title}
        </span>
        <span className="vc-model" title="Model that produced this assessment">{a.model}</span>
      </div>
      <div className="vc-body">
        <Gauge score={a.risk_score} />
        <div>
          <span className={`band ${riskTone(a.risk_score)}`}>{bandLabel[a.band]}</span>
          <p className="vc-headline">{a.headline}</p>
        </div>
      </div>
      <p className="vc-reason">{a.reasoning}</p>
      {!memory && a.red_flags.length > 0 && (
        <ul className="mini-flags">
          {a.red_flags.map((f, i) => (
            <li key={i}>{f.title}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RedFlags({ a, onOpen }: { a: A; onOpen: (id: string) => void }) {
  if (!a.red_flags.length) {
    return <div className="empty small">No red flags. Memory found nothing that raises suspicion.</div>;
  }
  return (
    <ul className="flags">
      {a.red_flags.map((f, i) => (
        <li key={i} className={`flag ${f.severity}`}>
          <div className="flag-head">
            <span className={`sev ${f.severity}`}>{f.severity}</span>
            <strong>{f.title}</strong>
          </div>
          <p>{f.detail}</p>
          {f.evidence_claim_ids.length > 0 && (
            <div className="chips">
              <span className="chips-label">Evidence from memory:</span>
              {f.evidence_claim_ids.map((id) => (
                <button key={id} className="chip link" onClick={() => onOpen(id)}>
                  {id}
                </button>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
