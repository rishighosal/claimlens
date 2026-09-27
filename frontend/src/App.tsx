import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { MemoryOp, Row, Status } from "./types";
import { ClaimView } from "./components/ClaimView";
import { Drawer } from "./components/Drawer";
import { EvalView } from "./components/EvalView";
import { MemoryPanel } from "./components/MemoryPanel";
import { Queue } from "./components/Queue";
import { Story } from "./components/Story";
import { Tour } from "./components/Tour";

const store = {
  get(k: string, d: string) {
    try {
      return window.localStorage.getItem(k) ?? d;
    } catch {
      return d;
    }
  },
  set(k: string, v: string) {
    try {
      window.localStorage.setItem(k, v);
    } catch {
      /* private mode: keep in memory only */
    }
  },
};

export default function App() {
  // First visit opens on the problem story; after that, straight to the workbench.
  const [view, setViewRaw] = useState<"story" | "work" | "eval">(
    store.get("cl.storySeen", "0") === "1" ? "work" : "story",
  );
  const setView = (v: "story" | "work" | "eval") => {
    if (v !== "story") store.set("cl.storySeen", "1");
    setViewRaw(v);
  };
  const [scope, setScope] = useState<"queue" | "history">("queue");
  const [rows, setRows] = useState<Row[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<string | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [fresh, setFresh] = useState<MemoryOp[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [evalSeen, setEvalSeen] = useState(store.get("cl.evalSeen", "0") === "1");
  const [tourShown, setTourShown] = useState(store.get("cl.tour", "1") === "1");
  const [tourOpen, setTourOpen] = useState(store.get("cl.tourOpen", "0") === "1");

  const showEval = () => {
    setView("eval");
    setEvalSeen(true);
    store.set("cl.evalSeen", "1");
  };
  const go = (id: string) => {
    setView("work");
    if (scope !== "queue") setScope("queue");
    setSel(id);
  };

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
          <button className={view === "story" ? "on" : ""} onClick={() => setView("story")}>The problem</button>
          <button className={view === "work" ? "on" : ""} onClick={() => setView("work")}>Investigate</button>
          <button className={view === "eval" ? "on" : ""} onClick={showEval}>Does memory help?</button>
          {!tourShown && (
            <button onClick={() => { setTourShown(true); setTourOpen(true); store.set("cl.tour", "1"); }}>
              Guided demo
            </button>
          )}
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
      {view === "story" ? (
        <main className="story-main">
          <Story
            onStart={() => {
              setTourShown(true);
              store.set("cl.tour", "1");
              go("CLM-2026-10595");
            }}
            onEval={showEval}
          />
        </main>
      ) : view === "eval" ? (
        <main className="eval-main">
          <EvalView />
        </main>
      ) : (
        <main className="work">
          <Queue rows={rows} scope={scope} setScope={(s) => { setScope(s); setSel(null); }} selected={sel} onSelect={setSel} />
          <div className="center">
            {tourShown && scope === "queue" && (
              <Tour
                rows={rows}
                evalSeen={evalSeen}
                open={tourOpen}
                setOpen={(o) => { setTourOpen(o); store.set("cl.tourOpen", o ? "1" : "0"); }}
                onGo={go}
                onEval={showEval}
                onHide={() => { setTourShown(false); store.set("cl.tour", "0"); }}
              />
            )}
            {sel ? (
              <ClaimView key={sel} id={sel} onOpen={setDrawer} onChanged={load} onOps={setFresh} onBusy={setBusy} />
            ) : (
              <div className="empty">Select a claim</div>
            )}
          </div>
          <MemoryPanel status={status} fresh={fresh} live={busy} onOpen={setDrawer} />
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
