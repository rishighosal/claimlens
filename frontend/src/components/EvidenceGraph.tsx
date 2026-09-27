import { useMemo, useState } from "react";
import type { GraphEdge, GraphNode } from "../types";
import { decisionLabel, reasonLabel } from "../api";

const W = 720;
const H = 440;
const CX = W / 2;
const CY = H / 2;

const PERSONAL = new Set(["phone", "account", "vehicle", "address"]);

function trunc(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export function EvidenceGraph({
  nodes,
  edges,
  onOpen,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onOpen: (id: string) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);

  const pos = useMemo(() => {
    const p: Record<string, { x: number; y: number }> = {};
    const current = nodes.find((n) => n.type === "current");
    if (current) p[current.id] = { x: CX, y: CY };
    const ents = nodes.filter((n) => n.type === "entity");
    const claims = nodes.filter((n) => n.type === "claim");
    ents.forEach((n, i) => {
      const a = (i / Math.max(ents.length, 1)) * Math.PI * 2 - Math.PI / 2;
      p[n.id] = { x: CX + Math.cos(a) * 150, y: CY + Math.sin(a) * 105 };
    });
    // Place each past claim near the angle of the first entity it connects through
    const angleOf: Record<string, number> = {};
    ents.forEach((n, i) => (angleOf[n.id] = (i / Math.max(ents.length, 1)) * Math.PI * 2 - Math.PI / 2));
    const withAngle = claims.map((c, i) => {
      const via = edges.find((e) => e.target === c.id && e.source.startsWith("ent:"));
      const a = via ? angleOf[via.source] : (i / Math.max(claims.length, 1)) * Math.PI * 2;
      return { c, a };
    });
    withAngle.sort((x, y) => x.a - y.a);
    withAngle.forEach(({ c }, i) => {
      const a = (i / Math.max(withAngle.length, 1)) * Math.PI * 2 - Math.PI / 2 + 0.18;
      p[c.id] = { x: CX + Math.cos(a) * 300, y: CY + Math.sin(a) * 180 };
    });
    return p;
  }, [nodes, edges]);

  const active = (id: string) =>
    !hover || hover === id || edges.some((e) => (e.source === hover && e.target === id) || (e.target === hover && e.source === id));

  if (nodes.length <= 1) {
    return <div className="empty small">Memory found no past claims linked to this one.</div>;
  }

  return (
    <div className="graph-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="graph" role="img" aria-label="Links between this claim and past claims">
        {edges.map((e, i) => {
          const a = pos[e.source];
          const b = pos[e.target];
          if (!a || !b) return null;
          const on = active(e.source) && active(e.target);
          if (e.kind === "narrative") {
            const mx = (a.x + b.x) / 2 + (b.y - a.y) * 0.15;
            const my = (a.y + b.y) / 2 - (b.x - a.x) * 0.15;
            return (
              <path
                key={i}
                d={`M${a.x},${a.y} Q${mx},${my} ${b.x},${b.y}`}
                className={`edge narrative ${on ? "" : "dim"}`}
              />
            );
          }
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              className={`edge ${PERSONAL.has(e.kind) ? "personal" : "provider"} ${on ? "" : "dim"}`}
            />
          );
        })}
        {nodes.map((n) => {
          const p = pos[n.id];
          if (!p) return null;
          const on = active(n.id);
          if (n.type === "current") {
            return (
              <g key={n.id} transform={`translate(${p.x},${p.y})`} className="node current">
                <circle r={30} />
                <text y={-2} className="node-id">NEW</text>
                <text y={12} className="node-sub">{n.label.slice(-5)}</text>
              </g>
            );
          }
          if (n.type === "entity") {
            const label = trunc(n.label.replace(/^(surveyor|vehicle|payee account) /, ""), 26);
            const w = Math.max(80, label.length * 6.4 + 18);
            return (
              <g
                key={n.id}
                transform={`translate(${p.x},${p.y})`}
                className={`node entity ${PERSONAL.has(n.kind || "") ? "personal" : "provider"} ${on ? "" : "dim"}`}
                onMouseEnter={() => setHover(n.id)}
                onMouseLeave={() => setHover(null)}
              >
                <rect x={-w / 2} y={-19} width={w} height={38} rx={9} />
                <text y={-4} className="ent-kind">{reasonLabel[n.kind || ""] || n.kind}</text>
                <text y={11} className="ent-label">{label}</text>
              </g>
            );
          }
          const tone = n.decision === "fraud_confirmed" ? "fraud" : n.decision === "referred" ? "ref" : "ok";
          return (
            <g
              key={n.id}
              transform={`translate(${p.x},${p.y})`}
              className={`node claim ${tone} ${on ? "" : "dim"}`}
              onMouseEnter={() => setHover(n.id)}
              onMouseLeave={() => setHover(null)}
              onClick={() => onOpen(n.id)}
              style={{ cursor: "pointer" }}
            >
              <rect x={-54} y={-18} width={108} height={36} rx={8} />
              <text y={-3} className="node-id">{n.label.replace("CLM-2026-", "#")}</text>
              <text y={11} className="node-sub">
                {n.date?.slice(5)} · {n.decision ? decisionLabel[n.decision] || n.decision : "open"}
              </text>
              <title>{`${n.label}\n${n.sub}\nLinked via: ${(n.reasons || []).map((r) => reasonLabel[r] || r).join(", ")}`}</title>
            </g>
          );
        })}
      </svg>
      <div className="legend">
        <span><i className="lg personal" /> shared personal identifier</span>
        <span><i className="lg provider" /> shared provider / agent</span>
        <span><i className="lg narrative" /> similar story</span>
        <span><i className="lg fraud" /> past outcome: fraud confirmed</span>
      </div>
    </div>
  );
}
