import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { MemoryOp, Row, Status } from "./types";
import { ClaimView } from "./components/ClaimView";
import { Drawer } from "./components/Drawer";
import { EvalView } from "./components/EvalView";
import { MemoryPanel } from "./components/MemoryPanel";
import { Queue } from "./components/Queue";

export default function App() {
  const [view, setView] = useState<"work" | "eval">("work");
  const [scope, setScope] = useState<"queue" | "history">("queue");
  const [rows, setRows] = useState<Row[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [fresh, setFresh] = useState<MemoryOp[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    api.claims(scope).then(
      (r) => {
        setRows(r);
        setSel((s) => s ?? r[0]?.claim_id ?? null);
      },
      (e) => setErr(e.message),
    );
    api.status().then(setStatus, () => undefined);
  }, [scope]);

  useEffect(load, [load]);

  const flagged = rows.filter((r) => (r.risk ?? 0) > 60).length;
  const reviewed = rows.filter((r) => r.risk != null).length;

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
            <circle cx="11" cy="11" r="8" fill="none" stroke="currentColor" strokeWidth="2.4" />
            <circle cx="11" cy="11" r="3" fill="currentColor" />
            <line x1="17" y1="17" x2="23.5" y2="23.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
          </svg>
          <span>ClaimLens</span>
          <span className="tagline">claims triage that remembers every claim</span>
        </div>
        <nav className="views">
          <button className={view === "work" ? "on" : ""} onClick={() => setView("work")}>Investigate</button>
          <button className={view === "eval" ? "on" : ""} onClick={() => setView("eval")}>Does memory help?</button>
        </nav>
        <div className="top-stats">
          {scope === "queue" && (
            <span>
              <b>{reviewed}</b>/{rows.length} reviewed · <b className="red">{flagged}</b> referred
            </span>
          )}
          <span className={`conn ${status?.memory_backend === "hindsight" ? (status.hindsight_reachable ? "ok" : "bad") : "dev"}`}>
            {status?.memory_backend === "hindsight"
              ? status.hindsight_reachable ? "Hindsight connected" : "Hindsight unreachable"
              : "Offline stand-in"}
          </span>
        </div>
      </header>
      {status?.memory_backend === "offline-standin" && (
        <div className="banner warn">
          Offline development mode: memory is a naive in-process stand-in, not Hindsight. Set HINDSIGHT_API_KEY and
          unset CLAIMLENS_FAKE_MEMORY for the real system.
        </div>
      )}
      {err && <div className="banner error">{err}</div>}
      {view === "eval" ? (
        <main className="eval-main">
          <EvalView />
        </main>
      ) : (
        <main className="work">
          <Queue rows={rows} scope={scope} setScope={(s) => { setScope(s); setSel(null); }} selected={sel} onSelect={setSel} />
          <div className="center">
            {sel ? (
              <ClaimView key={sel} id={sel} onOpen={setDrawer} onChanged={load} onOps={setFresh} />
            ) : (
              <div className="empty">Select a claim</div>
            )}
          </div>
          <MemoryPanel status={status} fresh={fresh} />
        </main>
      )}
      {drawer && (
        <Drawer
          id={drawer}
          onClose={() => setDrawer(null)}
          onOpenFull={(id) => {
            setDrawer(null);
            setSel(id);
          }}
        />
      )}
    </div>
  );
}
