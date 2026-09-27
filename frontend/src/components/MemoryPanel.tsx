import { useEffect, useState } from "react";
import { api } from "../api";
import type { MemoryOp, Reflection, Status } from "../types";

const OP_LABEL: Record<string, string> = {
  retain: "RETAIN",
  recall: "RECALL",
  reflect: "REFLECT",
  mental_model: "MODEL",
  setup: "SETUP",
};

function Op({ o }: { o: MemoryOp }) {
  const q = (o.detail?.query as string) || "";
  const tags = (o.detail?.tags as string[] | null) || null;
  return (
    <li className={`op ${o.op} ${o.ok ? "" : "failed"}`}>
      <div className="op-head">
        <span className={`op-pill ${o.op}`}>{OP_LABEL[o.op] || o.op}</span>
        <span className="op-label">{o.label}</span>
      </div>
      <div className="op-meta">
        {tags && <span className="mono">tags={tags.join(",")}</span>}
        {!tags && q && <span className="op-q">“{q.slice(0, 90)}{q.length > 90 ? "…" : ""}”</span>}
        <span className="op-num">
          {o.hits != null && <>{o.hits} {o.op === "retain" ? "docs" : "hits"} · </>}
          {o.ms} ms
        </span>
      </div>
      {o.error && <div className="op-err">{o.error}</div>}
    </li>
  );
}

export function MemoryPanel({ status, fresh }: { status: Status | null; fresh: MemoryOp[] }) {
  const [tab, setTab] = useState<"activity" | "playbook" | "ask">("activity");
  const [ops, setOps] = useState<MemoryOp[]>([]);
  const [pb, setPb] = useState<{ content: string; last_refreshed_at: string | null } | null>(null);
  const [pbErr, setPbErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [ans, setAns] = useState<Reflection | null>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    const load = () => api.ops().then(setOps).catch(() => undefined);
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [fresh]);

  useEffect(() => {
    if (tab !== "playbook") return;
    setPbErr(null);
    api.playbook().then(setPb, (e) => setPbErr(e.message));
  }, [tab]);

  async function ask(question: string) {
    setQ(question);
    setAsking(true);
    setAns(null);
    try {
      setAns(await api.ask(question));
    } catch (e: any) {
      setAns({ text: `Error: ${e.message}`, memories: [], directives: [] });
    } finally {
      setAsking(false);
    }
  }

  const s = status?.memory_stats || {};
  return (
    <aside className="mem-panel">
      <div className="mem-head">
        <div className="mem-title">
          <span className="logo-dot" /> Institutional memory
        </div>
        <div className="mem-sub">
          {status?.memory_backend === "hindsight" ? "Hindsight" : "Offline stand-in"} · bank{" "}
          <span className="mono">{status?.bank_id}</span>
        </div>
        <div className="mem-stats">
          <div><b>{s.world ?? "–"}</b><span>facts</span></div>
          <div><b>{s.observation ?? "–"}</b><span>observations</span></div>
          <div><b>{status?.history_claims ?? "–"}</b><span>past claims</span></div>
        </div>
      </div>
      <div className="tabs">
        {(["activity", "playbook", "ask"] as const).map((t) => (
          <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>
            {t === "activity" ? "Live activity" : t === "playbook" ? "Playbook" : "Ask memory"}
          </button>
        ))}
      </div>
      <div className="mem-body">
        {tab === "activity" && (
          <ul className="ops">
            {ops.length === 0 && <li className="empty small">Memory calls will appear here as they happen.</li>}
            {ops.map((o, i) => <Op key={o.at + o.label + i} o={o} />)}
          </ul>
        )}
        {tab === "playbook" && (
          <div className="playbook">
            <p className="muted small">
              A Hindsight <b>mental model</b> that re-synthesises itself as investigators close cases. Nobody wrote
              this; the memory learned it.
            </p>
            {pbErr && <div className="error">{pbErr}</div>}
            {pb ? <div className="pb-text">{pb.content || "Not generated yet. Refresh after seeding."}</div> : !pbErr && <div className="skeleton" />}
            <div className="row-between">
              <span className="muted small">{pb?.last_refreshed_at ? `Refreshed ${pb.last_refreshed_at.slice(0, 16).replace("T", " ")}` : ""}</span>
              <button
                className="btn ghost small"
                onClick={() => api.refreshPlaybook().then(() => setTimeout(() => api.playbook().then(setPb), 4000))}
              >
                Refresh
              </button>
            </div>
          </div>
        )}
        {tab === "ask" && (
          <div className="ask">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (q.trim().length > 2) ask(q.trim());
              }}
            >
              <textarea value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask anything the unit has seen…" rows={3} />
              <button className="btn primary small" disabled={asking}>{asking ? "Reflecting…" : "Ask"}</button>
            </form>
            <div className="suggest">
              {[
                "Which surveyors appear most often in claims we later repudiated?",
                "Is Lakshmi Hyundai, Kondapur a fraud risk?",
                "What do the Lifeline Multispeciality claims have in common?",
                "Has vehicle TS08FK4521 been claimed before?",
              ].map((s) => (
                <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>
              ))}
            </div>
            {ans && (
              <div className="answer">
                <div className="brief">{ans.text}</div>
                <p className="footnote">Grounded in {ans.memories.length} memories</p>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
