"""End-to-end API flow on the offline stand-ins: investigate -> decide -> memory used next time."""

from fastapi.testclient import TestClient

from claimlens.api import app


def test_investigate_and_record_outcome():
    with TestClient(app) as client:
        client.post("/api/admin/reset-ui")
        s = client.get("/api/status").json()
        assert s["memory_backend"] == "offline-standin"

        queue = client.get("/api/claims?scope=queue").json()
        assert queue and all(r["status"] == "open" for r in queue)
        cid = queue[0]["claim_id"]

        detail = client.get(f"/api/claims/{cid}").json()
        assert "_truth" not in detail["claim"]

        inv = client.post(f"/api/claims/{cid}/investigate").json()
        for arm in ("with_memory", "stateless"):
            a = inv[arm]
            assert 0 <= a["risk_score"] <= 100
            assert a["band"] in ("fast_track", "standard_review", "refer_to_siu")
        assert inv["probes"] and inv["memory_ops"]
        assert inv["stats"]["recalls"] >= 15 and inv["stats"]["model_calls"] == 2
        assert all(lc["grade"] in ("STRONG", "WEAK") and lc["grade_reason"] for lc in inv["linked_claims"])
        grades = [lc["grade"] for lc in inv["linked_claims"]]
        assert grades == sorted(grades, key=lambda g: g != "STRONG"), "STRONG links are listed first"
        assert any(o["op"] == "retain" for o in inv["memory_ops"]), "claim must be committed to memory at intake"
        allowed = {lc["claim_id"] for lc in inv["linked_claims"]}
        for f in inv["with_memory"]["red_flags"]:
            assert set(f["evidence_claim_ids"]) <= allowed

        r = client.post(f"/api/claims/{cid}/decision",
                        json={"decision": "fraud_confirmed", "notes": "field visit", "investigator": "T"}).json()
        assert r["ok"] and r["memory_ops"][0]["op"] == "retain"
        rows = client.get("/api/claims?scope=queue").json()
        assert next(x for x in rows if x["claim_id"] == cid)["risk"] is not None

        assert client.post("/api/claims/CLM-0000-00000/investigate").status_code == 404
        assert client.post(f"/api/claims/{cid}/decision", json={"decision": "maybe"}).status_code == 422
        assert client.get("/api/memory/playbook").status_code == 200
        assert client.post("/api/ask", json={"question": "who is K. Venkat Rao?"}).status_code == 200
        client.post("/api/admin/reset-ui")
