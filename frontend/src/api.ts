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

export const api = {
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
