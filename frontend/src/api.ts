import type { ClaimDetail, Investigation, MemoryOp, Reflection, Row, Status, Verdict } from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not json */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

const liveApi = {
  status: () => req<Status>("/api/status"),
  claims: (scope: "queue" | "history" = "queue") => req<Row[]>(`/api/claims?scope=${scope}`),
  claim: (id: string) => req<ClaimDetail>(`/api/claims/${id}`),
  investigate: (id: string) => req<Investigation>(`/api/claims/${id}/investigate`, { method: "POST" }),
  briefing: (id: string) => req<Reflection>(`/api/claims/${id}/briefing`, { method: "POST" }),
  decide: (id: string, decision: string, notes: string, investigator: string) =>
    req<{ ok: boolean; verdict: Verdict; memory_ops: MemoryOp[] }>(`/api/claims/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes, investigator }),
    }),
  ask: (question: string) => req<Reflection>("/api/ask", { method: "POST", body: JSON.stringify({ question }) }),
  playbook: () => req<{ name: string; content: string; last_refreshed_at: string | null; is_stale: boolean | null }>(
    "/api/memory/playbook",
  ),
  refreshPlaybook: () => req<{ ok: boolean }>("/api/memory/playbook/refresh", { method: "POST" }),
  ops: () => req<MemoryOp[]>("/api/memory/ops?n=60"),
  evalResults: () => req<any>("/api/eval"),
};


// ---------------------------------------------------------------------------
// Recorded-demo mode (VITE_STATIC=1): the same UI, replaying a real recorded run
// exported by scripts/export_demo.py. No server, no keys, nothing to break.
// ---------------------------------------------------------------------------
export const STATIC = import.meta.env.VITE_STATIC === "1";
const BASE = import.meta.env.BASE_URL || "/";

const cache: Record<string, Promise<any>> = {};
function file<T>(path: string): Promise<T> {
  if (!cache[path]) {
    cache[path] = fetch(`${BASE}demo/${path}`).then((r) => {
      if (!r.ok) throw new Error(`Not part of the recorded demo (${path})`);
      return r.json();
    });
  }
  return cache[path];
}

const session = {
  investigated: new Set<string>(),
  decisions: {} as Record<string, Verdict>,
  briefed: new Set<string>(),
  ops: [] as MemoryOp[],
};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const nowIso = () => new Date().toISOString().slice(0, 19);

async function staticClaim(id: string): Promise<ClaimDetail> {
  const d = await file<ClaimDetail>(`claims/${id}.json`);
  const open = d.claim.status === "open";
  return {
    ...d,
    investigation: session.investigated.has(id) ? d.investigation : null,
    briefing: session.briefed.has(id) ? d.briefing : null,
    decision: open ? session.decisions[id] ?? null : d.decision,
  };
}

async function staticRows(scope: "queue" | "history"): Promise<Row[]> {
  const rows = await file<Row[]>(scope === "queue" ? "queue.json" : "history.json");
  if (scope !== "queue") return rows;
  const out: Row[] = [];
  for (const r of rows) {
    const inv = session.investigated.has(r.claim_id) ? (await file<ClaimDetail>(`claims/${r.claim_id}.json`)).investigation : null;
    out.push({
      ...r,
      risk: inv ? inv.with_memory.risk_score : null,
      band: inv ? inv.with_memory.band : null,
      stateless_risk: inv ? inv.stateless.risk_score : null,
      decision: session.decisions[r.claim_id]?.decision ?? null,
    });
  }
  return out;
}

const staticApi: typeof liveApi = {
  status: async () => ({ ...(await file<Status>("status.json")), recorded: true } as Status),
  claims: (scope = "queue") => staticRows(scope),
  claim: staticClaim,
  investigate: async (id) => {
    const d = await file<ClaimDetail>(`claims/${id}.json`);
    if (!d.investigation) {
      throw new Error("This claim wasn't investigated in the recorded run. Follow the guided demo, or run ClaimLens locally for live investigations.");
    }
    // replay the recorded memory calls into the live panel, then show the result
    const ops = [...(d.investigation.memory_ops || [])];
    const step = Math.max(60, Math.min(160, 2600 / Math.max(ops.length, 1)));
    for (const op of ops) {
      session.ops.unshift({ ...op, at: nowIso() });
      await sleep(step);
    }
    session.investigated.add(id);
    return d.investigation;
  },
  briefing: async (id) => {
    const d = await file<ClaimDetail>(`claims/${id}.json`);
    if (!d.briefing) throw new Error("No recorded briefing for this claim. Try #10595.");
    await sleep(1200);
    session.briefed.add(id);
    return d.briefing;
  },
  decide: async (id, decision, notes, investigator) => {
    await sleep(900);
    const verdict: Verdict = { decision, notes, investigator, closed_on: nowIso().slice(0, 10) };
    session.decisions[id] = verdict;
    const op: MemoryOp = {
      op: "retain", label: `Retain outcome for ${id}: ${decision}`, detail: { recorded: true },
      at: nowIso(), ms: 0, hits: 1, ok: true, error: null,
    };
    session.ops.unshift(op);
    return { ok: true, verdict, memory_ops: [op] };
  },
  ask: async (question) => {
    const asks = await file<Record<string, Reflection>>("asks.json").catch(() => ({} as Record<string, Reflection>));
    await sleep(1000);
    const hit = asks[question.trim()];
    if (hit) return hit;
    return {
      text: "This is a recorded demo, so only the suggested questions have recorded answers. Run ClaimLens locally to ask Hindsight anything.",
      memories: [], directives: [],
    };
  },
  playbook: () => file("playbook.json"),
  refreshPlaybook: async () => ({ ok: true }),
  ops: async () => {
    const recorded = await file<MemoryOp[]>("ops.json").catch(() => [] as MemoryOp[]);
    return [...session.ops, ...recorded].slice(0, 60);
  },
  evalResults: () => file("eval.json"),
};

export const api = STATIC ? staticApi : liveApi;

export const inr = (n: number | null | undefined) =>
  n == null ? "–" : "₹" + Math.round(n).toLocaleString("en-IN");

export const bandLabel: Record<string, string> = {
  fast_track: "Fast-track",
  standard_review: "Standard review",
  refer_to_siu: "Refer to SIU",
};

export const riskTone = (score: number | null | undefined) =>
  score == null ? "none" : score > 60 ? "high" : score > 30 ? "med" : "low";

export const reasonLabel: Record<string, string> = {
  garage: "same garage",
  surveyor: "same surveyor",
  hospital: "same hospital",
  doctor: "same doctor",
  agent: "same agent",
  phone: "shared phone",
  account: "shared bank a/c",
  vehicle: "same vehicle",
  address: "same address",
  narrative: "similar story",
  pattern: "known pattern",
  timeline: "recent activity",
};

export const decisionLabel: Record<string, string> = {
  approved: "Approved",
  cleared: "Cleared",
  referred: "Referred to SIU",
  fraud_confirmed: "Fraud confirmed",
};
