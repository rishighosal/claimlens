import json
from collections import Counter

from claimlens import claims as C


def test_dataset_shape():
    repo = C.repo()
    assert len(repo.history()) > 150
    assert 15 <= len(repo.open_queue()) <= 40
    rings = Counter(c["_truth"]["ring"] for c in repo.all() if c["_truth"]["ring"])
    assert set(rings) == {"R1", "R2", "R3", "R4"}
    # every open-queue ring has history to learn from, except the ones designed to be caught cold
    assert all(c["verdict"] is None for c in repo.open_queue())


def test_ground_truth_never_rendered():
    for c in C.repo().all():
        text = C.render(c)
        assert "_truth" not in text
        assert c["_truth"]["pattern"] is None or c["_truth"]["pattern"][:40] not in text
        assert "_truth" not in json.dumps(C.public(c))


def test_entity_tags_link_ring_members():
    repo = C.repo()
    r1 = [c for c in repo.all() if c["_truth"]["ring"] == "R1"]
    tags = [set(e.tag for e in C.entities(c)) for c in r1]
    assert all("surveyor:SV12" in t and "garage:G07" in t for t in tags)
    phones = Counter(t for ts in tags for t in ts if t.startswith("phone:"))
    assert phones.most_common(1)[0][1] >= 3, "R1 claimants should share a phone number"

    r3 = [c for c in repo.all() if c["_truth"]["ring"] == "R3"]
    addr = {e.tag for c in r3 for e in C.entities(c) if e.kind == "address"}
    assert addr == {"address:plot-42-sai-enclave-miyapur"}


def test_personal_identifiers_rarely_collide_by_chance():
    """Random genuine claimants must not share phones/accounts, or links would be noise."""
    repo = C.repo()
    genuine = [c for c in repo.all() if c["_truth"]["label"] == "legit" and c["_truth"]["ring"] is None]
    for kind in ("phone", "account"):
        seen = Counter(e.tag for c in genuine for e in C.entities(c) if e.kind == kind)
        assert max(seen.values()) == 1, f"accidental {kind} collision among genuine claims"


def test_render_verdict_mentions_decision_and_entities():
    c = next(x for x in C.repo().history() if x["verdict"]["decision"] == "fraud_confirmed")
    text = C.render_verdict(c, c["verdict"])
    assert c["claim_id"] in text and "CONFIRMED FRAUD" in text
    assert c["claimant"]["phone"] in text
