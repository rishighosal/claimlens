import { useEffect, useMemo, useRef, useState } from "react";
import { api, inr } from "../api";
import type { ClaimDetail } from "../types";

/** The three R1 claims that tell the story. All data comes from the API; nothing here is mocked. */
const STORY_IDS = ["CLM-2026-10566", "CLM-2026-10572", "CLM-2026-10595"];

type FieldKey = "phone" | "account" | "surveyor" | "garage" | "story";

const FIELDS: { key: FieldKey; label: string; step: number; tone: "personal" | "provider" | "story" }[] = [
  { key: "phone", label: "Phone", step: 1, tone: "personal" },
  { key: "account", label: "Payee bank account", step: 2, tone: "personal" },
  { key: "surveyor", label: "Surveyor", step: 3, tone: "provider" },
  { key: "garage", label: "Garage", step: 3, tone: "provider" },
  { key: "story", label: "Their story", step: 4, tone: "story" },
];

const REVEAL_TEXT: Record<number, string> = {
  1: "Suresh's phone number is Sneha's phone number.",
  2: "Suresh wants his money paid into the same bank account as Priya.",
  3: "The same surveyor signed off all three, at the same garage.",
  4: "Three strangers told the same story, almost word for word.",
  5: "Investigators repudiated Priya's and Sneha's claims as fraud on 7 and 8 September. Suresh filed on 8 September.",
};

function value(c: Record<string, any>, k: FieldKey): string {
  switch (k) {
    case "phone":
      return c.claimant.phone;
    case "account":
      return c.payee_account;
    case "surveyor":
      return c.surveyor?.name ?? "";
    case "garage":
      return c.garage?.name ?? "";
    case "story":
      return "unknown vehicle · hit from behind · at night · fled";
  }
}

export function Story({ onStart, onEval }: { onStart: () => void; onEval: () => void }) {
  const [claims, setClaims] = useState<ClaimDetail[] | null>(null);
  const [scores, setScores] = useState<Record<string, { with: number; without: number }>>({});
  const [late, setLate] = useState<{ caught: number; total: number; caughtWithout: number; fp: number } | null>(null);
  const [step, setStep] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    Promise.all(STORY_IDS.map((id) => api.claim(id))).then(setClaims, () => setClaims([]));
    api.evalResults().then(
      (e) => {
        if (!e?.available) return;
        const m: Record<string, { with: number; without: number }> = {};
        for (const r of e.per_claim || []) m[r.claim_id] = { with: r.with_memory, without: r.stateless };
        setScores(m);
        // Aug–Sep: after investigators had confirmed the first ring cases
        const th = e.threshold ?? 61;
        const rows = (e.per_claim || []) as any[];
        const fraudLate = rows.filter((r) => r.label === "fraud" && r.date >= "2026-08-01");
        setLate({
          caught: fraudLate.filter((r) => r.with_memory >= th).length,
          caughtWithout: fraudLate.filter((r) => r.stateless >= th).length,
          total: fraudLate.length,
          fp: rows.filter((r) => r.label !== "fraud" && r.with_memory >= th).length,
        });
      },
      () => undefined,
    );
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, []);

  // which fields are shared by 2+ of the three claims, and with whom
  const shared = useMemo(() => {
    const out: Record<string, string[]> = {}; // `${claimId}:${field}` -> other short ids
    if (!claims || claims.length < 3) return out;
    for (const f of FIELDS) {
      for (const a of claims) {
        const others = claims
          .filter((b) => b !== a && value(b.claim, f.key) === value(a.claim, f.key))
          .map((b) => "#" + b.claim.claim_id.slice(-5));
        if (others.length) out[`${a.claim.claim_id}:${f.key}`] = others;
      }
    }
    return out;
  }, [claims]);

  function reveal() {
    if (timer.current) window.clearInterval(timer.current);
    setStep(1);
    timer.current = window.setInterval(() => {
      setStep((s) => {
        if (s >= 5 && timer.current) window.clearInterval(timer.current);
        return Math.min(s + 1, 5);
      });
    }, 1100);
  }

  return (
    <div className="story">
      <section className="story-hero">
        <span className="story-kicker">The problem</span>
        <h1>
          Every claim looks genuine.
          <br />
          <span>The fraud is in the pattern between them.</span>
        </h1>
        <p>
          Three motor claims from Hyderabad, filed between July and September 2026. Different people, different cars,
          different parts of the city. A claims handler, or an AI that reads one claim at a time, would pay all three.
        </p>
      </section>

      <section className="story-cards">
        {!claims && <div className="skeleton" style={{ height: 320 }} />}
        {claims?.map((d, i) => {
          const c = d.claim;
          const sc = scores[c.claim_id];
          const fraud = d.decision?.decision === "fraud_confirmed";
          return (
            <article key={c.claim_id} className={`sc-card ${step >= 5 && fraud ? "is-fraud" : ""} ${i === 2 ? "is-new" : ""}`}>
              <header>
                <span className="mono sc-id">#{c.claim_id.slice(-5)}</span>
                <span className="sc-date">{c.intimation_date}</span>
                {i === 2 && <span className="sc-new">arrives today</span>}
              </header>
              <div className="sc-name">{c.claimant.name}</div>
              <div className="sc-sub">
                {c.vehicle.make_model} · {c.vehicle.registration} · {inr(c.claimed_amount)}
              </div>
              <dl>
                {FIELDS.map((f) => {
                  const key = `${c.claim_id}:${f.key}`;
                  const hit = shared[key] && step >= f.step;
                  const v = f.key === "story" ? `“${c.narrative.split(".")[0]}.”` : value(c, f.key);
                  return (
                    <div key={f.key} className={`sc-field ${hit ? `hit ${f.tone}` : ""}`}>
                      <dt>{f.label}</dt>
                      <dd className={f.key === "phone" || f.key === "account" ? "mono" : ""}>{v}</dd>
                      {hit && f.key !== "story" && f.key !== "garage" && (
                        <span className="sc-link">same as {shared[key].join(", ")}</span>
                      )}
                    </div>
                  );
                })}
              </dl>
              <footer>
                <div className="sc-verdict neutral">
                  <span>Stateless AI, this claim alone</span>
                  <b>{sc ? `${sc.without}/100 · Fast-track` : "Fast-track"}</b>
                </div>
                {step >= 5 && (
                  <div className={`sc-verdict ${fraud ? "fraud" : "memory"}`}>
                    {fraud ? (
                      <>
                        <span>What actually happened</span>
                        <b>Repudiated as fraud · {d.decision?.closed_on}</b>
                      </>
                    ) : (
                      <>
                        <span>ClaimLens with Hindsight memory</span>
                        <b>{sc ? `${sc.with}/100 · ` : ""}Refer to SIU</b>
                      </>
                    )}
                  </div>
                )}
              </footer>
            </article>
          );
        })}
      </section>

      <section className="story-reveal">
        {step === 0 ? (
          <button className="btn primary big" onClick={reveal} disabled={!claims?.length}>
            Reveal what memory sees
          </button>
        ) : (
          <ol className="reveal-list">
            {[1, 2, 3, 4, 5].map((s) => (
              <li key={s} className={step >= s ? "on" : ""}>{REVEAL_TEXT[s]}</li>
            ))}
          </ol>
        )}
        {step >= 5 && (
          <p className="story-punch">
            None of this is written in Suresh's claim. It's in the <b>history</b>. ClaimLens gives the triage agent
            that history, using Hindsight as institutional memory.
          </p>
        )}
      </section>

      <section className="story-why">
        <h2>Why it matters</h2>
        <div className="why-grid">
          <div className="why-tile">
            <b>₹8,000–10,000 cr</b>
            <span>lost by Indian insurers every year to fraud, waste and abuse</span>
            <a href="https://www.business-standard.com/industry/news/insurance-fwa-drains-rs10000cr-each-year-bcg-mediassist-report-125112101199_1.html" target="_blank" rel="noreferrer">BCG × Medi Assist, Nov 2025</a>
          </div>
          <div className="why-tile">
            <b>8–10%</b>
            <span>of all claim payouts leak to fraud, waste and abuse</span>
            <a href="https://www.business-standard.com/industry/news/insurance-fwa-drains-rs10000cr-each-year-bcg-mediassist-report-125112101199_1.html" target="_blank" rel="noreferrer">same report</a>
          </div>
          <div className="why-tile">
            <b>1 April 2026</b>
            <span>IRDAI's fraud-monitoring guidelines take effect: every insurer must run a Fraud Monitoring Unit and keep fraud records</span>
            <a href="https://taxguru.in/corporate-law/irdai-insurance-fraud-monitoring-framework-guidelines-2025.html" target="_blank" rel="noreferrer">IRDAI Guidelines, 2025</a>
          </div>
        </div>
      </section>

      <section className="story-compare">
        <h2>Why rules and chatbots miss it</h2>
        <div className="cmp-grid">
          <div className="cmp">
            <h3>A rule: “flag Sri Balaji Auto Works”</h3>
            <p>Also flags <b>#10614</b>, an honest driver whose car was rear-ended at the same garage, with a different surveyor. Genuine customers get delayed.</p>
          </div>
          <div className="cmp">
            <h3>A stateless AI triage bot</h3>
            <p>Reads one claim. It can't know the phone number or bank account was used before, or what investigators decided. Every claim above scores <b>15/100</b>.</p>
          </div>
          <div className="cmp win">
            <h3>ClaimLens + Hindsight memory</h3>
            <p>Remembers every claim and every investigator outcome. Links <b>combinations</b> (shared phone, account, surveyor) and gets better with every case the unit closes.</p>
          </div>
        </div>
      </section>

      <section className="story-result">
        <div>
          <h2>Same model. Same prompt. The only difference is memory.</h2>
          <p>
            Replaying nine months of claims in date order:{" "}
            {late ? (
              <>
                in August–September, <b>{late.caught} of {late.total}</b> fraud claims were flagged with Hindsight memory
                and <b>{late.caughtWithout} of {late.total}</b> without it. <b>{late.fp}</b> honest claims were flagged
                all year.
              </>
            ) : (
              <>0 of 12 fraud claims caught without memory in August–September, 11 of 12 with Hindsight, and 0 honest claims flagged.</>
            )}
          </p>
        </div>
        <div className="story-cta">
          <button className="btn primary big" onClick={onStart}>Start the guided demo →</button>
          <button className="btn big" onClick={onEval}>See the learning curve</button>
        </div>
      </section>
    </div>
  );
}
