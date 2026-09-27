import { useEffect, useState } from "react";
import { api, decisionLabel } from "../api";
import type { ClaimDetail } from "../types";
import { ClaimFacts } from "./ClaimView";

export function Drawer({ id, onClose, onOpenFull }: { id: string; onClose: () => void; onOpenFull: (id: string) => void }) {
  const [d, setD] = useState<ClaimDetail | null>(null);
  useEffect(() => {
    setD(null);
    api.claim(id).then(setD, () => undefined);
  }, [id]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="drawer-bg" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="row-between">
          <h2 className="mono">{id}</h2>
          <button className="btn ghost small" onClick={onClose}>Close</button>
        </div>
        {!d ? (
          <div className="skeleton" />
        ) : (
          <>
            <p className="muted small">
              Intimated {d.claim.intimation_date} · {d.claim.line} · status {d.claim.status}
            </p>
            {d.decision && (
              <div className={`outcome ${d.decision.decision}`}>
                <b>{decisionLabel[d.decision.decision] || d.decision.decision}</b>
                {d.decision.closed_on && <> on {d.decision.closed_on}</>}
                {d.decision.investigator && <> by {d.decision.investigator}</>}
                {d.decision.notes && <p>{d.decision.notes}</p>}
              </div>
            )}
            <ClaimFacts c={d.claim} />
            <button className="btn ghost" onClick={() => onOpenFull(id)}>Open full claim</button>
          </>
        )}
      </aside>
    </div>
  );
}
