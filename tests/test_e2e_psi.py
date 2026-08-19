"""
E2E PSI tests against live Azure Container Apps deployment.
Covers: health, PSI architecture, dimensions, security, decision pipeline,
PSI audit/persistence, portable identity, cognitive right-to-forget,
crisis routing, RAG consent gate, engines, and Project4D endpoint.

Run: python3 -m pytest tests/test_e2e_psi.py -v
"""
import os
import json
import hmac
import hashlib
import time
import uuid
import urllib.request
import urllib.error

import pytest

APP_URL = os.environ.get(
    "U_BRAIN_API_URL",
    "https://u-jarvis-api.ashytree-79de396a.eastus.azurecontainerapps.io",
)
SECRET = os.environ.get("U_SHARED_SECRET", "")


def _signed_request(path: str, body_dict: dict, method: str = "POST"):
    """Send a signed request to the live API."""
    body = json.dumps(body_dict)
    request_id = str(uuid.uuid4())
    timestamp = str(int(time.time()))
    msg = f"{timestamp}.{request_id}.{body}".encode()
    sig = hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()
    headers = {
        "x-u-request-id": request_id,
        "x-u-timestamp": timestamp,
        "x-u-signature": sig,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        f"{APP_URL}{path}", data=body.encode(), headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else {}
        except (json.JSONDecodeError, ValueError):
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def _get(path: str):
    req = urllib.request.Request(f"{APP_URL}{path}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except Exception as e:
        return 0, {"error": str(e)}


def _unsigned_post(path: str, body_dict: dict):
    """Send an unsigned POST — should be rejected by signing middleware."""
    body = json.dumps(body_dict)
    req = urllib.request.Request(
        f"{APP_URL}{path}", data=body.encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read()) if r.read() else {}
    except urllib.error.HTTPError as e:
        return e.code, {}


@pytest.fixture
def unique_user():
    return f"e2e-psi-{int(time.time())}-{uuid.uuid4().hex[:6]}"


@pytest.fixture
def user_with_3_decisions(unique_user):
    """Create a user and run 3 decisions through the PSI pipeline."""
    for i in range(3):
        _signed_request("/api/jarvis", {
            "title": f"Integration Test {i+1}",
            "situation": f"Career change scenario with financial implications, round {i+1}",
            "desired_outcome": "Clear recommendation",
            "pillars": ["career", "finance"],
            "facts": ["Current role is stable", "New offer is 20% higher"],
            "unknowns": ["Team culture", "Commute impact"],
            "constraints": ["Family time priority"],
            "values": ["growth", "security"],
            "horizon_days": 90,
            "consent": {"analyze": True, "memory": False, "research": False,
                        "external_actions": False, "sensitive_data": False},
            "user_id": unique_user,
            "command": "decide",
        })
    return unique_user


# ── 1. Health & Config ───────────────────────────────────────────────

class TestHealthConfig:
    def test_health_200(self):
        s, _ = _get("/api/health")
        assert s == 200

    def test_version_is_project4d(self):
        s, d = _get("/api/health")
        assert "project4d" in d.get("version", "")

    def test_signing_configured(self):
        s, d = _get("/api/health")
        assert d["signing"]["signing_key_configured"] is True

    def test_signing_required(self):
        s, d = _get("/api/health")
        assert d["signing"]["signing_required"] is True

    def test_signing_valid(self):
        s, d = _get("/api/health")
        assert d["signing"]["signing_key_valid"] is True

    def test_signing_status_ready(self):
        s, d = _get("/api/health")
        assert d["signing"]["status"] == "ready"


# ── 2. PSI Architecture ───────────────────────────────────────────────

class TestPSIArchitecture:
    def test_psi_status_200(self):
        s, _ = _get("/api/psi")
        assert s == 200

    def test_paradigm_is_project4d(self):
        s, d = _get("/api/psi")
        assert "Project4D" in d["paradigm"]

    def test_d1_active(self):
        s, d = _get("/api/psi")
        assert d["dimensions"]["d1_cognitive_persistence"]["active"] is True

    def test_d2_active(self):
        s, d = _get("/api/psi")
        assert d["dimensions"]["d2_portable_directive"]["active"] is True

    def test_d3_active(self):
        s, d = _get("/api/psi")
        assert d["dimensions"]["d3_multi_agent_governance"]["active"] is True

    def test_d4_active(self):
        s, d = _get("/api/psi")
        assert d["dimensions"]["d4_emergent_identity"]["active"] is True

    def test_d1_persisted(self):
        s, d = _get("/api/psi")
        assert d["dimensions"]["d1_cognitive_persistence"]["persisted"] is True

    def test_d4_persisted(self):
        s, d = _get("/api/psi")
        assert d["dimensions"]["d4_emergent_identity"]["persisted"] is True

    def test_8_lifecycle_steps(self):
        s, d = _get("/api/psi")
        assert len(d["lifecycle_steps"]) == 8

    def test_persistence_is_sqlite(self):
        s, d = _get("/api/psi")
        assert "SQLite" in d["persistence"]


# ── 3. Dimensions Detail ─────────────────────────────────────────────

class TestDimensionsDetail:
    def test_dimensions_200(self):
        s, _ = _get("/api/psi/dimensions")
        assert s == 200

    def test_d1_patterns_count_4(self):
        s, d = _get("/api/psi/dimensions")
        assert len(d["d1_cognitive_persistence"]["patterns_tracked"]) == 4

    def test_d1_persistence_sqlite(self):
        s, d = _get("/api/psi/dimensions")
        assert "SQLite" in d["d1_cognitive_persistence"]["persistence"]

    def test_d2_at_least_5_substrates(self):
        s, d = _get("/api/psi/dimensions")
        assert len(d["d2_portable_directive"]["supported_substrates"]) >= 5

    def test_d2_current_substrate_set(self):
        s, d = _get("/api/psi/dimensions")
        assert "current_substrate" in d["d2_portable_directive"]

    def test_d3_lenses_20(self):
        s, d = _get("/api/psi/dimensions")
        assert d["d3_multi_agent_governance"]["total_lenses"] == 20

    def test_d3_has_4_agents(self):
        s, d = _get("/api/psi/dimensions")
        assert len(d["d3_multi_agent_governance"]["agents"]) == 4

    def test_d3_persistence_sqlite(self):
        s, d = _get("/api/psi/dimensions")
        assert "SQLite" in d["d3_multi_agent_governance"]["persistence"]

    def test_d4_immutable_dna_8(self):
        s, d = _get("/api/psi/dimensions")
        assert d["d4_emergent_identity"]["immutable_dna"] == 8

    def test_d4_evolvable_traits_8(self):
        s, d = _get("/api/psi/dimensions")
        assert d["d4_emergent_identity"]["evolvable_traits"] == 8

    def test_d4_persistence_sqlite(self):
        s, d = _get("/api/psi/dimensions")
        assert "SQLite" in d["d4_emergent_identity"]["persistence"]

    def test_lifecycle_8_steps_and_sqlite(self):
        s, d = _get("/api/psi/dimensions")
        assert len(d["lifecycle"]["steps"]) == 8
        assert "SQLite" in d["lifecycle"]["persistence_layer"]


# ── 4. Security ───────────────────────────────────────────────────────

class TestSecurity:
    def test_unsigned_rejected_401(self):
        s, _ = _unsigned_post("/api/jarvis", {
            "title": "x", "situation": "x", "desired_outcome": "x",
            "pillars": ["career"], "consent": {"analyze": True},
        })
        assert s == 401

    def test_tampered_signature_rejected_401(self):
        body = json.dumps({
            "title": "x", "situation": "x", "desired_outcome": "x",
            "pillars": ["career"], "consent": {"analyze": True}, "user_id": "e2e",
        })
        req = urllib.request.Request(
            f"{APP_URL}/api/jarvis", data=body.encode(),
            headers={
                "x-u-request-id": str(uuid.uuid4()),
                "x-u-timestamp": str(int(time.time())),
                "x-u-signature": "deadbeef",
                "Content-Type": "application/json",
            }, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 401

    def test_expired_timestamp_rejected_401(self):
        old_ts = str(int(time.time()) - 600)
        body = json.dumps({
            "title": "x", "situation": "x", "desired_outcome": "x",
            "pillars": ["career"], "consent": {"analyze": True}, "user_id": "e2e",
        })
        msg = f"{old_ts}.{uuid.uuid4()}.{body}".encode()
        sig = hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()
        req = urllib.request.Request(
            f"{APP_URL}/api/jarvis", data=body.encode(),
            headers={
                "x-u-request-id": str(uuid.uuid4()),
                "x-u-timestamp": old_ts,
                "x-u-signature": sig,
                "Content-Type": "application/json",
            }, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 401

    def test_unsigned_reset_rejected_401(self, unique_user):
        s, _ = _unsigned_post(f"/api/psi/reset/{unique_user}", {})
        assert s == 401


# ── 5. Decision Pipeline (3 decisions × 5 assertions each) ────────────

class TestDecisionPipeline:
    @pytest.fixture
    def decision_results(self, unique_user):
        results = []
        for i in range(3):
            s, d = _signed_request("/api/jarvis", {
                "title": f"Pipeline Decision {i+1}",
                "situation": f"Career change with financial impact, round {i+1}",
                "desired_outcome": "Clear recommendation",
                "pillars": ["career", "finance"],
                "facts": ["Current role is stable", "New offer is 20% higher"],
                "unknowns": ["Team culture", "Commute impact"],
                "constraints": ["Family time priority"],
                "values": ["growth", "security"],
                "horizon_days": 90,
                "consent": {"analyze": True, "memory": False, "research": False,
                            "external_actions": False, "sensitive_data": False},
                "user_id": unique_user,
                "command": "decide",
            })
            results.append((s, d, i + 1))
        return results

    def test_decision_1_returns_200(self, decision_results):
        assert decision_results[0][0] == 200

    def test_decision_1_has_stay_change_pause(self, decision_results):
        env = decision_results[0][1].get("decision", {})
        assert len(env.get("options", [])) >= 3

    def test_decision_1_has_psi_embed(self, decision_results):
        traces = decision_results[0][1]["decision"]["engine_trace"]
        assert any("psi_embed" in t.get("engine", "") for t in traces)

    def test_decision_1_has_psi_engage(self, decision_results):
        traces = decision_results[0][1]["decision"]["engine_trace"]
        assert any("psi_engage" in t.get("engine", "") for t in traces)

    def test_decision_1_has_cognitive_mode(self, decision_results):
        traces = decision_results[0][1]["decision"]["engine_trace"]
        assert any("cognitive_mode" in t.get("engine", "") for t in traces)

    def test_decision_1_approval_required(self, decision_results):
        env = decision_results[0][1].get("decision", {})
        assert env.get("approval_required") is True

    def test_decision_2_returns_200(self, decision_results):
        assert decision_results[1][0] == 200

    def test_decision_2_has_stay_change_pause(self, decision_results):
        env = decision_results[1][1].get("decision", {})
        assert len(env.get("options", [])) >= 3

    def test_decision_2_has_psi_embed(self, decision_results):
        traces = decision_results[1][1]["decision"]["engine_trace"]
        assert any("psi_embed" in t.get("engine", "") for t in traces)

    def test_decision_2_has_psi_engage(self, decision_results):
        traces = decision_results[1][1]["decision"]["engine_trace"]
        assert any("psi_engage" in t.get("engine", "") for t in traces)

    def test_decision_2_has_cognitive_mode(self, decision_results):
        traces = decision_results[1][1]["decision"]["engine_trace"]
        assert any("cognitive_mode" in t.get("engine", "") for t in traces)

    def test_decision_2_approval_required(self, decision_results):
        env = decision_results[1][1].get("decision", {})
        assert env.get("approval_required") is True

    def test_decision_3_returns_200(self, decision_results):
        assert decision_results[2][0] == 200

    def test_decision_3_has_stay_change_pause(self, decision_results):
        env = decision_results[2][1].get("decision", {})
        assert len(env.get("options", [])) >= 3

    def test_decision_3_has_psi_embed(self, decision_results):
        traces = decision_results[2][1]["decision"]["engine_trace"]
        assert any("psi_embed" in t.get("engine", "") for t in traces)

    def test_decision_3_has_psi_engage(self, decision_results):
        traces = decision_results[2][1]["decision"]["engine_trace"]
        assert any("psi_engage" in t.get("engine", "") for t in traces)

    def test_decision_3_has_cognitive_mode(self, decision_results):
        traces = decision_results[2][1]["decision"]["engine_trace"]
        assert any("cognitive_mode" in t.get("engine", "") for t in traces)

    def test_decision_3_approval_required(self, decision_results):
        env = decision_results[2][1].get("decision", {})
        assert env.get("approval_required") is True


# ── 6. PSI Audit & Persistence ─────────────────────────────────────────

class TestPSIAudit:
    def test_audit_returns_200(self, user_with_3_decisions):
        s, _ = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert s == 200

    def test_cognitive_profile_exists(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["cognitive_profile_exists"] is True

    def test_interaction_count_ge_3(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["interaction_count"] >= 3

    def test_cognitive_depth_gt_0(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["cognitive_depth"] > 0

    def test_embedding_logs_ge_3(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["embedding_logs"] >= 3

    def test_identity_generation_ge_1(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["identity_generation"] >= 1

    def test_total_embeddings_ge_3(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["total_embeddings"] >= 3

    def test_multi_agent_logs_ge_3(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["multi_agent_logs"] >= 3


# ── 7. Portable Identity Export ──────────────────────────────────────

class TestPortableIdentity:
    @pytest.fixture
    def identity_export(self, user_with_3_decisions):
        s, d = _get(f"/api/psi/identity/{user_with_3_decisions}")
        return s, d

    def test_export_returns_200(self, identity_export):
        assert identity_export[0] == 200

    def test_portable_is_true(self, identity_export):
        assert identity_export[1]["portable"] is True

    def test_has_cognitive_profile(self, identity_export):
        assert "cognitive_profile" in identity_export[1]

    def test_has_identity_block(self, identity_export):
        assert "identity" in identity_export[1]

    def test_identity_generation_ge_1(self, identity_export):
        assert identity_export[1]["identity"]["generation"] >= 1

    def test_identity_has_hash(self, identity_export):
        assert len(identity_export[1]["identity"]["hash"]) > 0

    def test_identity_has_traits(self, identity_export):
        assert len(identity_export[1]["identity"]["traits"]) > 0

    def test_identity_has_immutable_principles(self, identity_export):
        assert len(identity_export[1]["identity"]["immutable_principles"]) > 0


# ── 8. Cognitive Right-to-Forget ──────────────────────────────────────

class TestCognitiveReset:
    def test_signed_reset_returns_200(self, user_with_3_decisions):
        s, d = _signed_request(f"/api/psi/reset/{user_with_3_decisions}", {})
        assert s == 200

    def test_reset_confirmed(self, user_with_3_decisions):
        s, d = _signed_request(f"/api/psi/reset/{user_with_3_decisions}", {})
        assert d["reset"] is True

    def test_post_reset_profile_cleared(self, user_with_3_decisions):
        _signed_request(f"/api/psi/reset/{user_with_3_decisions}", {})
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["cognitive_profile_exists"] is False

    def test_post_reset_embeddings_zero(self, user_with_3_decisions):
        _signed_request(f"/api/psi/reset/{user_with_3_decisions}", {})
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["embedding_logs"] == 0

    def test_post_reset_interactions_zero(self, user_with_3_decisions):
        _signed_request(f"/api/psi/reset/{user_with_3_decisions}", {})
        s, d = _get(f"/api/psi/audit/{user_with_3_decisions}")
        assert d["interaction_count"] == 0


# ── 9. Crisis Safety Gate ─────────────────────────────────────────────

class TestCrisisSafety:
    def test_crisis_decision_returns_200(self):
        s, _ = _signed_request("/api/jarvis", {
            "title": "I want to end my life",
            "situation": "I can't take it anymore, everything is too much",
            "desired_outcome": "relief from pain",
            "pillars": ["health"],
            "consent": {"analyze": True, "memory": False, "research": False,
                        "external_actions": False, "sensitive_data": False},
            "command": "decide",
        })
        assert s == 200

    def test_crisis_risk_is_crisis(self):
        s, d = _signed_request("/api/jarvis", {
            "title": "I want to end my life",
            "situation": "I can't take it anymore, everything is too much",
            "desired_outcome": "relief from pain",
            "pillars": ["health"],
            "consent": {"analyze": True, "memory": False, "research": False,
                        "external_actions": False, "sensitive_data": False},
            "command": "decide",
        })
        assert d["decision"]["risk"] == "crisis"

    def test_crisis_has_safety_message(self):
        s, d = _signed_request("/api/jarvis", {
            "title": "I want to end my life",
            "situation": "I can't take it anymore, everything is too much",
            "desired_outcome": "relief from pain",
            "pillars": ["health"],
            "consent": {"analyze": True, "memory": False, "research": False,
                        "external_actions": False, "sensitive_data": False},
            "command": "decide",
        })
        assert len(d["decision"]["safety_message"]) > 0

    def test_emergency_returns_200(self):
        s, _ = _signed_request("/api/emergency", {
            "user_id": "e2e-crisis-test",
            "message": "I'm having thoughts of self harm and need help",
            "immediate_danger": True,
        })
        assert s == 200

    def test_emergency_risk_is_crisis(self):
        s, d = _signed_request("/api/emergency", {
            "user_id": "e2e-crisis-test",
            "message": "I'm having thoughts of self harm and need help",
            "immediate_danger": True,
        })
        assert d["risk"] == "crisis"

    def test_emergency_analysis_stopped(self):
        s, d = _signed_request("/api/emergency", {
            "user_id": "e2e-crisis-test",
            "message": "I'm having thoughts of self harm and need help",
            "immediate_danger": True,
        })
        assert d["analysis_stopped"] is True


# ── 10. RAG Consent Gate ─────────────────────────────────────────────

class TestRagConsent:
    def test_rag_search_without_consent_rejected(self):
        s, _ = _signed_request("/api/rag/search", {
            "user_id": "e2e-rag-test",
            "query": "career guidance",
        })
        assert s in (401, 403)

    def test_rag_ingest_with_consent_accepted(self):
        s, _ = _signed_request("/api/rag/ingest", {
            "user_id": "e2e-rag-test",
            "source_id": "test-doc",
            "text": "Test content for RAG testing",
            "consent": {"memory": True},
        })
        assert s == 200


# ── 11. Engines ───────────────────────────────────────────────────────

class TestEngines:
    def test_engines_returns_200(self):
        s, _ = _get("/api/engines")
        assert s == 200

    def test_engine_count_is_18(self):
        s, d = _get("/api/engines")
        assert d["count"] == 18

    def test_governance_field_present(self):
        s, d = _get("/api/engines")
        assert "governance" in d
        assert len(d["governance"]) > 10


# ── 12. Project4D Endpoint ────────────────────────────────────────────

class TestProject4D:
    def test_project4d_returns_200(self):
        s, _ = _get("/api/project4d")
        assert s == 200

    def test_project4d_paradigm(self):
        s, d = _get("/api/project4d")
        assert "Project4D" in d["paradigm"]

    def test_project4d_has_4_dimensions(self):
        s, d = _get("/api/project4d")
        assert len(d["dimensions"]) == 4
