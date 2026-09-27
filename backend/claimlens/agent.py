"""The ClaimLens investigator agent.

For every incoming claim it produces two assessments with the *same* model and
the *same* instructions:

* **stateless** - the claim on its own (what a normal LLM triage bot sees)
* **ClaimLens** - the claim plus everything Hindsight recalls about the people,
  providers, stories and patterns connected to it

The only difference between the two is memory, which is what makes the
before/after in the UI and the replay evaluation honest.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import claims as C
from .llm import LLM
from .memory import ClaimMemory, Link, MemoryOp, gather_evidence

# --------------------------------------------------------------------------- #
# Prompting                                                                    #
# --------------------------------------------------------------------------- #

SYSTEM = """You are a claims fraud triage analyst at an Indian general insurer (motor and health).
Decide how much scrutiny a new claim needs. Output ONLY a JSON object with this shape:
{
  "risk_score": integer 0-100,
  "band": "fast_track" | "standard_review" | "refer_to_siu",
  "headline": "one line, max 18 words",
  "reasoning": "2-4 sentences",
  "red_flags": [{"title": "short", "detail": "one sentence", "severity": "high"|"medium"|"low", "evidence_claim_ids": ["CLM-..."]}],
  "mitigating_factors": ["..."],
  "next_steps": ["concrete verification step", "..."],
  "questions_for_claimant": ["..."]
}
Calibration: 0-30 fast_track (genuine-looking, pay quickly), 31-60 standard_review, 61-100 refer_to_siu.
Rules:
- Most claims are genuine. Do not invent suspicion; a claim with no concrete red flags should score low.
- evidence_claim_ids may ONLY contain claim IDs that appear in the HISTORY section. If there is no history, leave them empty.
- High volume at one garage, hospital or agent is not suspicious by itself. Shared personal identifiers
  (phone, bank account, vehicle, address) across different claimants, near-identical narratives,
  a provider pair previously confirmed as fraud, or claims very soon after policy start are strong signals.
- If history shows similar claims were investigated and cleared as genuine, treat that as mitigating.
- Fraud rings are combinations. A past fraud claim that shares ONLY the garage or hospital (and/or a similar
  story) with this claim, with a different surveyor/doctor and no shared personal identifiers, is weak context,
  not a red flag. Honest claimants use the same garages. Each HISTORY entry is labelled STRONG or WEAK; respect it.
- The same phone, bank account or vehicle appearing under a DIFFERENT claimant or policy is strong evidence even if
  those earlier claims were approved: early ring claims are usually paid before anyone notices. The same vehicle
  claiming the same damage again is a classic recycled-damage pattern.
- Score from STRONG evidence: no STRONG links -> normally fast_track; exactly one STRONG link that is not
  confirmed fraud -> standard_review; one STRONG link to a confirmed-fraud claim, or two or more STRONG links
  -> refer_to_siu (score above 60). A vehicle, phone or bank account is a personal identifier: if the HISTORY
  says one is shared, never state that no personal identifiers are shared.
- When you cite a past claim, state its recorded outcome exactly (approved, cleared or confirmed fraud). Never call an approved claim fraudulent.
- An intermediary (agent) shared with past claims is weak evidence unless those claims were confirmed fraud through that same agent.
- A pattern is a lead, not proof: recommend verification, never accuse."""

NO_HISTORY = "HISTORY: none available. You are seeing this claim in isolation."


def _history_block(claim: dict, links: list[tuple[Link, float]], insights: list[str]) -> str:
    if not links and not insights:
        return "HISTORY (from institutional memory): nothing related found."
    graded = [(ln, strength, grade(ln)) for ln, strength in links]
    n_strong = sum(g[0] == "STRONG" for _, _, g in graded)
    n_strong_fraud = sum(g[0] == "STRONG" and _is_fraud(ln) for ln, _, g in graded)
    out = ["HISTORY (recalled from institutional memory; each entry is a past claim linked to this one):",
           f"Summary: {n_strong} STRONG links ({n_strong_fraud} to confirmed-fraud claims), "
           f"{len(graded) - n_strong} WEAK links."]
    graded.sort(key=lambda x: (x[2][0] != "STRONG", -x[1]))
    for ln, strength, (label, why) in graded:
        reasons = ", ".join(sorted(C.KIND_LABEL.get(r, r) for r in ln.reasons if r != "timeline"))
        out.append(f"\n[{ln.claim_id}] {label}: {why}. Linked via: {reasons}.")
        for t in ln.verdict_facts[:2]:
            out.append(f"  - OUTCOME: {_clip(t)}")
        if not ln.verdict_facts:
            out.append("  - OUTCOME: none recorded in memory")
        for t in ln.facts[:2]:
            out.append(f"  - {_clip(t)}")
    if insights:
        out.append("\nConsolidated observations from memory:")
        out.extend(f"  - {_clip(t, 300)}" for t in insights[:4])
    return "\n".join(out)


def _clip(t: str, n: int = 240) -> str:
    t = " ".join(t.split())
    return t if len(t) <= n else t[: n - 1] + "…"


def _claim_block(claim: dict) -> str:
    return "NEW CLAIM:\n" + C.render(claim)


# --------------------------------------------------------------------------- #
# Link scoring                                                                 #
# --------------------------------------------------------------------------- #

REASON_WEIGHT = {
    "phone": 3.0, "account": 3.0, "vehicle": 3.0, "address": 1.2,  # people do share apartment blocks
    "surveyor": 1.0, "garage": 0.6, "hospital": 0.6, "doctor": 0.8, "agent": 0.7,
    "narrative": 1.5, "timeline": 0.3, "pattern": 0.5,
}


def link_strength(ln: Link) -> float:
    s = sum(REASON_WEIGHT.get(r, 0.5) for r in ln.reasons)
    joined = " ".join(ln.verdict_facts).lower()
    if "confirmed fraud" in joined or "repudiated" in joined:
        s += 2.5
    elif "cleared as genuine" in joined:
        s -= 1.0
    return round(s, 2)


def rank_links(links: dict[str, Link], k: int = 10) -> list[tuple[Link, float]]:
    # A claim that only co-occurs in time (or only in a generic pattern recall)
    # is noise, not a link.
    real = [ln for ln in links.values() if ln.reasons - {"timeline", "pattern"}]
    ranked = sorted(((ln, link_strength(ln)) for ln in real), key=lambda x: -x[1])
    return ranked[:k]


# --------------------------------------------------------------------------- #
# Validation + deterministic fallback                                          #
# --------------------------------------------------------------------------- #

BANDS = ("fast_track", "standard_review", "refer_to_siu")


def band_for(score: int) -> str:
    return "fast_track" if score <= 30 else "standard_review" if score <= 60 else "refer_to_siu"


def make_validator(allowed_ids: set[str]):
    def validate(d: dict) -> dict:
        score = int(max(0, min(100, round(float(d.get("risk_score", 0))))))
        removed = 0
        flags = []
        for f in (d.get("red_flags") or [])[:8]:
            if not isinstance(f, dict):
                continue
            ids = [i for i in (f.get("evidence_claim_ids") or []) if isinstance(i, str)]
            kept = [i for i in ids if i in allowed_ids]
            removed += len(ids) - len(kept)
            sev = f.get("severity") if f.get("severity") in ("high", "medium", "low") else "medium"
            flags.append({"title": str(f.get("title", ""))[:90], "detail": str(f.get("detail", ""))[:400],
                          "severity": sev, "evidence_claim_ids": kept})
        return {
            "risk_score": score,
            "band": band_for(score),  # band is always derived from the score, never trusted blindly
            "headline": str(d.get("headline", ""))[:160],
            "reasoning": str(d.get("reasoning", ""))[:1200],
            "red_flags": flags,
            "mitigating_factors": [str(x)[:240] for x in (d.get("mitigating_factors") or [])][:5],
            "next_steps": [str(x)[:240] for x in (d.get("next_steps") or [])][:6],
            "questions_for_claimant": [str(x)[:240] for x in (d.get("questions_for_claimant") or [])][:5],
            "uncited_ids_removed": removed,
        }

    return validate


STRONG_PERSONAL = {"phone", "account", "vehicle"}
PAIRING = {"surveyor", "doctor", "phone", "account", "vehicle", "address", "agent"}


def _is_fraud(ln: Link) -> bool:
    j = " ".join(ln.verdict_facts).lower()
    return "confirmed fraud" in j or "repudiated" in j or "fraud_confirmed" in j


def evidence_points(ln: Link) -> int:
    """Conservative evidence score for one linked claim (used only when no LLM is reachable).

    Shared providers, a similar story or a busy garage alone score ~nothing:
    that is exactly how honest claims at a fraud-ring garage look."""
    pts = 0
    if ln.reasons & STRONG_PERSONAL:
        pts += 4
    if _is_fraud(ln) and ln.reasons & PAIRING:
        pts += 3
    elif _is_fraud(ln) and "narrative" in ln.reasons and ln.reasons & {"garage", "hospital"}:
        pts += 1
    return pts


def grade(ln: Link) -> tuple[str, str]:
    """Label a link STRONG or WEAK with a plain reason, so the model weighs combinations, not topics."""
    personal = sorted(ln.reasons & STRONG_PERSONAL)
    fraud = _is_fraud(ln)
    if personal:
        what = ", ".join(C.KIND_LABEL[k] for k in personal)
        return "STRONG", f"{what} (a personal identifier) appears on a different claim/policy" + (
            " that SIU confirmed as fraud" if fraud else f"; that claim's outcome: {_outcome(ln)}, which does not clear this one")
    pairs = sorted(ln.reasons & {"surveyor", "doctor"})
    if fraud and pairs:
        return "STRONG", f"{C.KIND_LABEL[pairs[0]]} as a claim SIU confirmed as fraud"
    if fraud and "address" in ln.reasons:
        return "STRONG", "same address block as a claim SIU confirmed as fraud"
    shared = ", ".join(sorted(C.KIND_LABEL.get(r, r) for r in ln.reasons if r not in ("timeline", "pattern")))
    return "WEAK", f"shares only {shared or 'context'}; no personal identifier in common (outcome: {_outcome(ln)})"


def _outcome(ln: Link) -> str:
    if _is_fraud(ln):
        return "confirmed fraud"
    j = " ".join(ln.verdict_facts).lower()
    if "cleared" in j:
        return "cleared as genuine"
    if "approved" in j or "paid" in j:
        return "approved"
    if "referred" in j:
        return "referred to SIU"
    return "none recorded"


def heuristic_assessment(claim: dict, ranked: list[tuple[Link, float]]) -> dict:
    """Used only if every model is unreachable, so the investigator is never left empty-handed."""
    scored = sorted(((ln, evidence_points(ln)) for ln, _ in ranked), key=lambda x: -x[1])
    score = int(min(95, 12 + 7 * sum(p for _, p in scored[:5])))
    flags = []
    for ln, p in scored[:4]:
        if p < 3:
            continue
        what = ", ".join(sorted(C.KIND_LABEL.get(r, r) for r in ln.reasons if r != "timeline"))
        outcome = "confirmed fraud" if _is_fraud(ln) else "no fraud finding recorded"
        flags.append({"title": f"Linked to {ln.claim_id} ({outcome})", "detail": f"Shared: {what}.",
                      "severity": "high" if p >= 6 else "medium", "evidence_claim_ids": [ln.claim_id]})
    return {"risk_score": score, "band": band_for(score),
            "headline": "Link analysis only: the language model was unreachable",
            "reasoning": "Scored from shared personal identifiers and links to confirmed-fraud claims that "
                         "Hindsight recalled. Shared providers or similar stories alone are not counted.",
            "red_flags": flags, "mitigating_factors": [], "next_steps": ["Review the linked claims manually."],
            "questions_for_claimant": [], "uncited_ids_removed": 0}


def stateless_fallback(claim: dict) -> dict:
    return {"risk_score": 20, "band": "fast_track", "headline": "No LLM available; no red flags on the face of it",
            "reasoning": "Fallback assessment.", "red_flags": [], "mitigating_factors": [], "next_steps": [],
            "questions_for_claimant": [], "uncited_ids_removed": 0}


# --------------------------------------------------------------------------- #
# Evidence graph for the UI                                                    #
# --------------------------------------------------------------------------- #


def evidence_graph(claim: dict, ranked: list[tuple[Link, float]], repo: C.ClaimRepo,
                   decisions: dict[str, dict] | None = None) -> dict:
    decisions = decisions or {}
    ents = {e.kind: e for e in C.entities(claim)}
    nodes: list[dict] = [{"id": claim["claim_id"], "type": "current", "label": claim["claim_id"],
                          "sub": C.summary(claim)}]
    edges: list[dict] = []
    ent_nodes: set[str] = set()
    for ln, strength in ranked[:10]:
        past = repo.get(ln.claim_id)
        # Draw each past claim through its two strongest connections only;
        # the full reason list stays on the node and in the table.
        top = sorted((r for r in ln.reasons if r in REASON_WEIGHT and r not in ("timeline", "pattern")),
                     key=lambda r: -REASON_WEIGHT[r])[:2]
        verdict = decisions.get(ln.claim_id) or (past or {}).get("verdict") or {}
        nodes.append({"id": ln.claim_id, "type": "claim", "label": ln.claim_id,
                      "sub": C.summary(past) if past else "",
                      "date": (past or {}).get("intimation_date"),
                      "decision": verdict.get("decision"), "strength": strength,
                      "reasons": sorted(ln.reasons)})
        for r in top:
            if r in ents:  # shared hard identifier -> route through an entity node
                e = ents[r]
                nid = f"ent:{e.tag}"
                if nid not in ent_nodes:
                    ent_nodes.add(nid)
                    nodes.append({"id": nid, "type": "entity", "kind": r, "label": e.label})
                    edges.append({"source": claim["claim_id"], "target": nid, "kind": r})
                edges.append({"source": nid, "target": ln.claim_id, "kind": r})
            elif r == "narrative":
                edges.append({"source": claim["claim_id"], "target": ln.claim_id, "kind": "narrative"})
    return {"nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- #
# Agent                                                                        #
# --------------------------------------------------------------------------- #


@dataclass
class Investigator:
    memory: ClaimMemory
    llm: LLM
    strict: bool = False  # replay evaluation: never substitute the deterministic fallback

    async def assess_stateless(self, claim: dict) -> dict:
        user = f"{_claim_block(claim)}\n\n{NO_HISTORY}"
        data, source = await self.llm.json(SYSTEM, user, validate=make_validator(set()),
                                           fallback=lambda: stateless_fallback(claim), strict=self.strict)
        data["model"] = source
        return data

    async def assess_with_memory(self, claim: dict, *, sink: list[MemoryOp] | None = None,
                                 exclude: set[str] | None = None,
                                 query_time: str | None = None) -> tuple[dict, dict]:
        ev = await gather_evidence(self.memory, claim, sink=sink, exclude=exclude, query_time=query_time)
        ranked = rank_links(ev["links"])
        user = f"{_claim_block(claim)}\n\n{_history_block(claim, ranked, ev['insights'])}"
        allowed = {ln.claim_id for ln, _ in ranked}
        data, source = await self.llm.json(SYSTEM, user, validate=make_validator(allowed),
                                           fallback=lambda: heuristic_assessment(claim, ranked),
                                           strict=self.strict)
        data["model"] = source
        ev["ranked"] = ranked
        return data, ev

    async def investigate(self, claim: dict, repo: C.ClaimRepo, *, decisions: dict[str, dict] | None = None,
                          retain: bool = True) -> dict[str, Any]:
        """Full intake: both assessments in parallel, then commit the claim to memory."""
        sink: list[MemoryOp] = []
        now = datetime.now(timezone.utc).isoformat()
        # Live use: memory is recalled as of now, so outcomes recorded today count.
        (mem_assessment, ev), baseline = await asyncio.gather(
            self.assess_with_memory(claim, sink=sink, query_time=now),
            self.assess_stateless(claim),
        )
        if retain:
            try:
                await self.memory.retain_claim(claim, sink=sink)
            except Exception:
                pass  # logged in the op trace; the assessment is still valid
        ranked = ev["ranked"]
        return {
            "claim_id": claim["claim_id"],
            "with_memory": mem_assessment,
            "stateless": baseline,
            "graph": evidence_graph(claim, ranked, repo, decisions),
            "linked_claims": [
                {"claim_id": ln.claim_id, "strength": s, "reasons": sorted(ln.reasons),
                 "facts": ln.facts[:4], "outcome": ln.verdict_facts[:2]}
                for ln, s in ranked
            ],
            "insights": ev["insights"],
            "probes": ev["probes"],
            "memory_ops": [o.to_dict() for o in sink],
        }

    async def briefing(self, claim: dict) -> dict:
        """Hindsight reflect: a narrative investigator briefing grounded in memory."""
        return await self.memory.reflect(
            f"Brief an SIU investigator on claim {claim['claim_id']}. Which past claims, people, providers or "
            f"confirmed patterns connect to it? What was decided about them? What should be verified first?",
            label=f"Investigator briefing for {claim['claim_id']}",
            context=C.render(claim), budget="mid",
        )
