import type { Row } from "../types";

interface Step {
  claim?: string;
  title: string;
  why: string;
  done: (rows: Row[], evalSeen: boolean) => boolean;
}

const find = (rows: Row[], id: string) => rows.find((r) => r.claim_id === id);

const STEPS: Step[] = [
  {
    claim: "CLM-2026-10595",
    title: "Investigate #10595: a night-time hit-and-run",
    why: "Looks routine to a stateless model. Watch what memory finds.",
    done: (r) => find(r, "CLM-2026-10595")?.risk != null,
  },
  {
    claim: "CLM-2026-10595",
    title: "Confirm fraud on #10595",
    why: "One Hindsight retain. Memory just learned something.",
    done: (r) => find(r, "CLM-2026-10595")?.decision === "fraud_confirmed",
  },
  {
    claim: "CLM-2026-10606",
    title: "Investigate #10606: same ring, nine days later",
    why: "Its evidence now includes the case you just closed.",
    done: (r) => find(r, "CLM-2026-10606")?.risk != null,
  },
  {
    claim: "CLM-2026-10614",
    title: "Investigate #10614: an honest claim at the same garage",
    why: "Shares only the garage, so the evidence is WEAK and it isn't flagged.",
    done: (r) => find(r, "CLM-2026-10614")?.risk != null,
  },
  {
    claim: "CLM-2026-10597",
    title: "Investigate #10597: the same Creta, third claim",
    why: "Same vehicle, same damage, new owner.",
    done: (r) => find(r, "CLM-2026-10597")?.risk != null,
  },
  {
    title: "See the learning curve",
    why: "Nine months replayed: same model, with vs without memory.",
    done: (_r, seen) => seen,
  },
];

export function Tour({
  rows,
  evalSeen,
  open,
  setOpen,
  onGo,
  onEval,
  onHide,
}: {
  rows: Row[];
  evalSeen: boolean;
  open: boolean;
  setOpen: (o: boolean) => void;
  onGo: (id: string) => void;
  onEval: () => void;
  onHide: () => void;
}) {
  const status = STEPS.map((s) => s.done(rows, evalSeen));
  const current = status.findIndex((d) => !d);
  const doneCount = status.filter(Boolean).length;
  return (
    <section className={`tour ${open ? "open" : ""}`}>
      <header className="tour-head" onClick={() => setOpen(!open)}>
        <div>
          <span className="tour-kicker">Guided demo</span>
          <span className="tour-title">Fraud rings are invisible one claim at a time. Watch memory find one.</span>
        </div>
        <div className="tour-right">
          <span className="tour-count">{doneCount}/{STEPS.length}</span>
          <div className="tour-bar"><i style={{ width: `${(doneCount / STEPS.length) * 100}%` }} /></div>
          <button className="btn ghost small" onClick={(e) => { e.stopPropagation(); setOpen(!open); }}>
            {open ? "Collapse" : "All steps"}
          </button>
          <button className="icon-x" title="Close guided demo" onClick={(e) => { e.stopPropagation(); onHide(); }}>×</button>
        </div>
      </header>
      {!open && current >= 0 && (
        <div className="tour-next">
          <span className="tour-num now">{current + 1}</span>
          <div className="tour-txt">
            <b>Next: {STEPS[current].title}</b>
            <span>{STEPS[current].why}</span>
          </div>
          <button
            className="btn small primary"
            onClick={() => (STEPS[current].claim ? onGo(STEPS[current].claim!) : onEval())}
          >
            Go
          </button>
        </div>
      )}
      {!open && current < 0 && (
        <div className="tour-next done-all">
          <span className="tour-num">✓</span>
          <div className="tour-txt"><b>You've seen the whole story.</b><span>Explore any claim, or ask memory a question.</span></div>
        </div>
      )}
      {open && (
        <ol className="tour-steps">
          {STEPS.map((s, i) => (
            <li key={i} className={status[i] ? "done" : i === current ? "now" : ""}>
              <span className="tour-num">{status[i] ? "✓" : i + 1}</span>
              <div className="tour-txt">
                <b>{s.title}</b>
                <span>{s.why}</span>
              </div>
              <button
                className={`btn small ${i === current ? "primary" : "ghost"}`}
                onClick={() => (s.claim ? onGo(s.claim) : onEval())}
              >
                {status[i] ? "Open" : "Go"}
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
