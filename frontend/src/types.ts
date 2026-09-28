export type Band = "fast_track" | "standard_review" | "refer_to_siu";

export interface Row {
  claim_id: string;
  line: "motor" | "health";
  intimation_date: string;
  claimant: string;
  summary: string;
  claimed_amount: number;
  status: "open" | "closed";
  risk: number | null;
  band: Band | null;
  stateless_risk: number | null;
  decision: string | null;
}

export interface RedFlag {
  title: string;
  detail: string;
  severity: "high" | "medium" | "low";
  evidence_claim_ids: string[];
}

export interface Assessment {
  risk_score: number;
  band: Band;
  headline: string;
  reasoning: string;
  red_flags: RedFlag[];
  mitigating_factors: string[];
  next_steps: string[];
  questions_for_claimant: string[];
  uncited_ids_removed: number;
  model: string;
}

export interface MemoryOp {
  op: "retain" | "recall" | "reflect" | "mental_model" | "setup";
  label: string;
  detail: Record<string, unknown>;
  at: string;
  ms: number;
  hits: number | null;
  ok: boolean;
  error: string | null;
}

export interface GraphNode {
  id: string;
  type: "current" | "claim" | "entity";
  label: string;
  sub?: string;
  kind?: string;
  date?: string;
  decision?: string | null;
  strength?: number;
  reasons?: string[];
  grade?: "STRONG" | "WEAK";
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface LinkedClaim {
  claim_id: string;
  strength: number;
  reasons: string[];
  grade?: "STRONG" | "WEAK";
  grade_reason?: string;
  outcome_label?: string;
  facts: string[];
  outcome: string[];
}

export interface Investigation {
  claim_id: string;
  with_memory: Assessment;
  stateless: Assessment;
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  linked_claims: LinkedClaim[];
  insights: string[];
  probes: { reason: string; label: string; hits: number; linked_claims: string[]; entity: string | null }[];
  memory_ops: MemoryOp[];
  stats?: {
    recalls: number;
    recall_hits: number;
    model_calls: number;
    strong_links: number;
    weak_links: number;
    seconds: number;
  };
}

export interface Verdict {
  decision: string;
  notes?: string;
  investigator?: string | null;
  closed_on?: string;
  paid_amount?: number;
}

export interface Reflection {
  text: string;
  memories: { text: string; document_id: string | null; type: string | null }[];
  directives: string[];
}

export interface ClaimDetail {
  claim: Record<string, any>;
  rendered: string;
  investigation: Investigation | null;
  briefing: Reflection | null;
  decision: Verdict | null;
}

export interface Status {
  memory_backend: "hindsight" | "offline-standin";
  hindsight_url: string | null;
  hindsight_reachable: boolean;
  bank_id: string;
  llm_model: string;
  memory_stats: Record<string, number | null | string>;
  history_claims: number;
  queue_claims: number;
  recorded?: boolean;
  recorded_at?: string;
}
