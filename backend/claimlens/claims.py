"""Claims system of record: loading, rendering claims as memory documents, and
extracting the hard identifiers that let Hindsight link claims together.

Ground-truth fields (keys starting with ``_``) are stripped before a claim is
ever shown to the agent, the LLM, the UI or Hindsight.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .config import settings

IST = timezone.utc  # dates are day-granular; UTC midnight keeps them stable


@dataclass(frozen=True)
class Entity:
    """A hard identifier on a claim that can link it to other claims."""

    kind: str   # garage | surveyor | hospital | doctor | agent | phone | account | vehicle | address
    key: str    # normalised id, used as a Hindsight tag suffix
    label: str  # human readable

    @property
    def tag(self) -> str:
        return f"{self.kind}:{self.key}"


# Identifiers that are personal to a claimant. Two *different* claimants
# sharing one of these is a strong signal on its own.
PERSONAL_KINDS = {"phone", "account", "vehicle", "address"}
# Identifiers of service providers / intermediaries. Sharing one is normal;
# it only matters in combination with other signals.
PROVIDER_KINDS = {"garage", "surveyor", "hospital", "doctor", "agent"}

KIND_LABEL = {
    "garage": "same garage",
    "surveyor": "same surveyor",
    "hospital": "same hospital",
    "doctor": "same treating doctor",
    "agent": "same intermediary",
    "phone": "shared phone number",
    "account": "shared payee account",
    "vehicle": "same vehicle",
    "address": "same address block",
    "narrative": "similar story",
    "pattern": "matches known pattern",
    "timeline": "recent activity",
}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _address_key(addr: str) -> str:
    # "Flat 301, Plot 42, Sai Enclave, Miyapur, Hyderabad" -> "plot-42-sai-enclave-miyapur"
    a = re.sub(r"^\s*(flat|door|h\.?no\.?)\s*[\w/-]+\s*,\s*", "", addr, flags=re.I)
    a = re.sub(r",\s*hyderabad\s*$", "", a, flags=re.I)
    return _slug(a)


def public(claim: dict) -> dict:
    """Strip evaluation-only ground truth."""
    return {k: v for k, v in claim.items() if not k.startswith("_")}


def entities(claim: dict) -> list[Entity]:
    out: list[Entity] = []
    c = claim
    if g := c.get("garage"):
        out.append(Entity("garage", g["id"], g["name"]))
    if s := c.get("surveyor"):
        out.append(Entity("surveyor", s["id"], f"surveyor {s['name']}"))
    if h := c.get("hospital"):
        out.append(Entity("hospital", h["id"], h["name"]))
    if d := c.get("treating_doctor"):
        out.append(Entity("doctor", _slug(d), d))
    if a := c.get("intermediary"):
        out.append(Entity("agent", a["agent_code"], f"{a['agent_code']} ({a['agent_name']})"))
    cl = c.get("claimant") or {}
    if p := cl.get("phone"):
        out.append(Entity("phone", re.sub(r"\D", "", p)[-10:], p))
    if acct := c.get("payee_account"):
        out.append(Entity("account", _slug(acct), f"payee account {acct}"))
    if v := c.get("vehicle"):
        out.append(Entity("vehicle", v["registration"].upper(), f"vehicle {v['registration']}"))
    if addr := cl.get("address"):
        out.append(Entity("address", _address_key(addr), addr))
    return out


def as_datetime(d: str) -> datetime:
    return datetime.combine(date.fromisoformat(d), time(9, 0), tzinfo=IST)


def _inr(x: int | float | None) -> str:
    if x is None:
        return "-"
    return f"Rs {int(x):,}"


def render(claim: dict) -> str:
    """Render a claim as the plain-text file an investigator would read.

    This is what gets retained into Hindsight. Identifiers are written
    exactly, so entity extraction and keyword search can link on them.
    """
    c = public(claim)
    cl = c["claimant"]
    lines = [
        f"Insurance claim {c['claim_id']} ({c['line']} line)",
        f"Policy {c['policy_no']} started {c['policy_start']}; claim intimated {c['intimation_date']}; incident on {c['incident_date']}.",
        f"Claimant: {cl['name']}, phone {cl['phone']}, address {cl['address']}.",
        f"Payee bank account: {c['payee_account']}.",
        f"Sourced by intermediary {c['intermediary']['agent_code']} - {c['intermediary']['agent_name']}.",
    ]
    if c["line"] == "motor":
        v = c["vehicle"]
        lines.append(f"Vehicle {v['registration']}, {v['make_model']} ({v['year']}), insured declared value {_inr(v['idv'])}.")
        lines.append(f"Incident type: {c['incident_type'].replace('_', ' ')}.")
        lines.append(f"Repairing garage: {c['garage']['name']} ({c['garage']['id']}).")
        if c.get("surveyor"):
            lines.append(f"Surveyor: {c['surveyor']['name']} ({c['surveyor']['id']}).")
        pr = c.get("police_report")
        lines.append(f"Police report: {pr['station']} FIR {pr['fir_no']}." if pr else "Police report: none filed.")
    else:
        lines.append(f"Hospital: {c['hospital']['name']} ({c['hospital']['id']}); treating doctor {c['treating_doctor']}.")
        lines.append(f"Diagnosis: {c['diagnosis']}. Admitted {c['admission_date']}, discharged {c['discharge_date']} ({c['length_of_stay_days']} day stay).")
        lines.append(f"Sum insured {_inr(c['sum_insured'])}; processed by {c['tpa']}.")
    lines.append(f"Claimed amount: {_inr(c['claimed_amount'])}.")
    lines.append(f"Claimant's account of events: \"{c['narrative']}\"")
    return "\n".join(lines)


def render_verdict(claim: dict, verdict: dict) -> str:
    decision = verdict["decision"]
    head = {
        "fraud_confirmed": "SIU CONFIRMED FRAUD and repudiated",
        "approved": "was approved and paid",
        "cleared": "was investigated and cleared as genuine",
        "referred": "was referred to SIU for field investigation",
    }.get(decision, decision)
    who = verdict.get("investigator") or "claims desk"
    paid = verdict.get("paid_amount")
    lines = [
        f"Outcome of claim {claim['claim_id']}: the claim {head} on {verdict.get('closed_on', 'unknown date')} by {who}.",
    ]
    if paid:
        lines.append(f"Amount paid: {_inr(paid)} against {_inr(claim['claimed_amount'])} claimed.")
    # Carry the key identifiers so the verdict is linked to the same entities.
    ents = ", ".join(e.label for e in entities(claim))
    lines.append(f"Parties on this claim: {ents}.")
    if verdict.get("notes"):
        lines.append(f"Investigator notes: {verdict['notes']}")
    return "\n".join(lines)


def summary(claim: dict) -> str:
    c = claim
    if c["line"] == "motor":
        return (f"{c['incident_type'].replace('_', ' ')} on {c['vehicle']['make_model']} {c['vehicle']['registration']}, "
                f"{c['garage']['name']}, {_inr(c['claimed_amount'])}")
    return f"{c['diagnosis']} at {c['hospital']['name']}, {c['length_of_stay_days']}d stay, {_inr(c['claimed_amount'])}"


class ClaimRepo:
    """Read-only view over the claims dataset."""

    def __init__(self, path: Path):
        raw = json.loads(Path(path).read_text())
        self.meta: dict[str, Any] = raw.get("meta", {})
        self._claims: list[dict] = raw["claims"]
        self._by_id = {c["claim_id"]: c for c in self._claims}

    def all(self) -> list[dict]:
        return list(self._claims)

    def get(self, claim_id: str) -> dict | None:
        return self._by_id.get(claim_id)

    def history(self) -> list[dict]:
        return [c for c in self._claims if c["status"] == "closed"]

    def open_queue(self) -> list[dict]:
        return [c for c in self._claims if c["status"] == "open"]

    def ids(self) -> Iterable[str]:
        return self._by_id.keys()

    def add(self, claim: dict) -> None:
        self._claims.append(claim)
        self._by_id[claim["claim_id"]] = claim


@lru_cache(maxsize=1)
def repo() -> ClaimRepo:
    return ClaimRepo(settings.claims_path)
