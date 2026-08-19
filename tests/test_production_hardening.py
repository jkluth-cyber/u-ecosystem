"""
U Platform — Production Hardening Test Suite
tests/test_production_hardening.py

Covers: RAG persistence, signing protocol, authentication, consent enforcement,
crisis-gate detection, behavioral contract, and Azure OpenAI fallback chain.
"""
from __future__ import annotations
import hashlib, hmac, json, os, time, uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.store import init_db, connect

TEST_SECRET = "test-shared-secret-min-32-characters-long!!"

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv("U_SHARED_SECRET", TEST_SECRET)
    monkeypatch.setenv("U_REQUIRE_SIGNED_REQUESTS", "true")
    monkeypatch.setenv("U_DATABASE_PATH", "/tmp/u_test_hardening.db")
    monkeypatch.setenv("U_ENV", "test")
    init_db()
    yield

@pytest.fixture
def client():
    return TestClient(app)

# ── Signing helpers ─────────────────────────────────────────────────

def _make_signed_headers(body_str, user_id="u", secret=TEST_SECRET, timestamp=None, request_id=None):
    ts = timestamp or str(int(time.time()))
    rid = request_id or str(uuid.uuid4())
    sig = hmac.new(secret.encode(), f"{ts}.{rid}.{body_str}".encode(), hashlib.sha256).hexdigest()
    user_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
    return {
        "x-u-request-id": rid,
        "x-u-user-hash": user_hash,
        "x-u-timestamp": ts,
        "x-u-signature": sig,
        "Content-Type": "application/json",
    }

def signed_post(client, url, body_dict, secret=TEST_SECRET, timestamp=None, request_id=None):
    body_str = json.dumps(body_dict)
    headers = _make_signed_headers(body_str, body_dict.get("user_id", "u"),
                                   secret=secret, timestamp=timestamp, request_id=request_id)
    return client.post(url, content=body_str.encode("utf-8"), headers=headers)

def signed_delete(client, url, user_id):
    headers = _make_signed_headers("", user_id)
    return client.delete(url, headers=headers)

def unsigned_post(client, url, body_dict):
    return client.post(url, json=body_dict, headers={"Content-Type": "application/json"})


# ═════════════════════════════════════════════════════════════════════
# 1. SIGNING PROTOCOL TESTS
# ═════════════════════════════════════════════════════════════════════

class TestSigningProtocol:

    def test_valid_signature_accepted(self, client):
        body = {"title": "Career decision", "situation": "Should I switch teams?", "desired_outcome": "Clarity", "user_id": "test1"}
        resp = signed_post(client, "/api/jarvis", body)
        assert resp.status_code == 200, f"Valid signature rejected: {resp.text}"

    def test_unsigned_request_rejected(self, client):
        body = {"title": "Test", "situation": "Should I?", "desired_outcome": "Clarity", "user_id": "test1"}
        resp = unsigned_post(client, "/api/jarvis", body)
        assert resp.status_code == 401

    def test_invalid_signature_rejected(self, client):
        body = {"title": "Test", "situation": "Should I?", "desired_outcome": "Clarity", "user_id": "test1"}
        body_str = json.dumps(body)
        headers = _make_signed_headers(body_str, "test1")
        headers["x-u-signature"] = "a" * 64
        resp = client.post("/api/jarvis", content=body_str.encode(), headers=headers)
        assert resp.status_code == 401

    def test_expired_timestamp_rejected(self, client):
        body = {"title": "Test", "situation": "Should I?", "desired_outcome": "Clarity", "user_id": "test1"}
        old_ts = str(int(time.time()) - 600)
        resp = signed_post(client, "/api/jarvis", body, timestamp=old_ts)
        assert resp.status_code == 401

    def test_replay_attack_rejected(self, client):
        body = {"title": "Replay test", "situation": "Should I move?", "desired_outcome": "Clarity", "user_id": "test1"}
        body_str = json.dumps(body)
        rid = str(uuid.uuid4())
        ts = str(int(time.time()))
        headers = _make_signed_headers(body_str, "test1", request_id=rid, timestamp=ts)
        resp1 = client.post("/api/jarvis", content=body_str.encode(), headers=headers)
        assert resp1.status_code == 200
        resp2 = client.post("/api/jarvis", content=body_str.encode(), headers=headers)
        assert resp2.status_code == 401, "Replay attack was not rejected"

    def test_missing_headers_rejected(self, client):
        body = {"title": "Test", "situation": "Should I?", "desired_outcome": "Clarity", "user_id": "test1"}
        resp = client.post("/api/jarvis", json=body, headers={"Content-Type": "application/json", "x-u-timestamp": str(int(time.time()))})
        assert resp.status_code == 401

    def test_wrong_secret_rejected(self, client):
        body = {"title": "Test", "situation": "Should I?", "desired_outcome": "Clarity", "user_id": "test1"}
        resp = signed_post(client, "/api/jarvis", body, secret="wrong-secret-min-32-characters-long!!!")
        assert resp.status_code == 401

    def test_nonce_not_burned_on_invalid_signature(self, client):
        """An invalid signature should NOT burn the request_id (nonce DoS fix)."""
        body = {"title": "Nonce test", "situation": "Should I?", "desired_outcome": "Clarity", "user_id": "test1"}
        body_str = json.dumps(body)
        rid = str(uuid.uuid4())
        ts = str(int(time.time()))
        user_hash = hashlib.sha256(b"test1").hexdigest()[:16]
        # Send with wrong secret — should fail
        bad_sig = hmac.new(b"wrong-secret-min-32-characters-long!!!", f"{ts}.{rid}.{body_str}".encode(), hashlib.sha256).hexdigest()
        resp_bad = client.post("/api/jarvis", content=body_str.encode(), headers={
            "x-u-request-id": rid, "x-u-user-hash": user_hash,
            "x-u-timestamp": ts, "x-u-signature": bad_sig,
            "Content-Type": "application/json",
        })
        assert resp_bad.status_code == 401
        # Now send with correct secret and same request_id — should succeed
        good_sig = hmac.new(TEST_SECRET.encode(), f"{ts}.{rid}.{body_str}".encode(), hashlib.sha256).hexdigest()
        resp_good = client.post("/api/jarvis", content=body_str.encode(), headers={
            "x-u-request-id": rid, "x-u-user-hash": user_hash,
            "x-u-timestamp": ts, "x-u-signature": good_sig,
            "Content-Type": "application/json",
        })
        assert resp_good.status_code == 200, "Request ID was burned by invalid signature (nonce DoS bug)"


# ═════════════════════════════════════════════════════════════════════
# 2. CRISIS-GATE DETECTION TESTS
# ═════════════════════════════════════════════════════════════════════

class TestCrisisGate:

    @pytest.mark.parametrize("phrase", [
        "I'm suicidal and need help",
        "I want to kill myself",
        "I want to self harm",
        "I want to self-harm",
        "I want to hurt myself",
        "I want to hurt someone",
        "I took an overdose",
        "I'm in immediate danger",
        "I can't stay safe tonight",
        "I cannot stay safe",
        "I want to end my life",
        "I want to die",
    ])
    def test_crisis_via_jarvis(self, client, phrase):
        body = {"title": "Crisis support", "situation": phrase, "desired_outcome": "I need help", "user_id": "crisis-test"}
        resp = signed_post(client, "/api/jarvis", body)
        assert resp.status_code == 200
        data = resp.json()
        decision = data.get("decision", data)
        assert decision.get("risk") == "crisis", f"'{phrase}' did not trigger crisis (got risk={decision.get('risk')})"
        assert bool(decision.get("safety_message")), f"'{phrase}' missing safety message"

    def test_crisis_via_emergency_endpoint(self, client):
        body = {"message": "I want to hurt myself", "user_id": "emergency-test", "immediate_danger": True}
        resp = signed_post(client, "/api/emergency", body)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("risk") == "crisis"
        assert len(data.get("steps", [])) >= 3

    def test_crisis_in_desired_outcome_field(self, client):
        body = {"title": "Planning", "situation": "I'm thinking about my future", "desired_outcome": "I want to end my life", "user_id": "surface-test"}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        assert decision.get("risk") == "crisis", "Crisis in desired_outcome not detected"

    def test_crisis_in_facts_field(self, client):
        body = {"title": "Situation", "situation": "Things are hard", "desired_outcome": "Relief", "facts": ["I want to overdose on pills"], "user_id": "surface-test2"}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        assert decision.get("risk") == "crisis", "Crisis in facts not detected"

    def test_crisis_options_empty(self, client):
        body = {"title": "Help", "situation": "I want to die", "desired_outcome": "End it", "user_id": "crisis-options"}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        assert len(decision.get("options", [])) == 0

    def test_crisis_no_external_action(self, client):
        body = {"title": "Help", "situation": "I want to kill myself", "desired_outcome": "End it", "user_id": "crisis-ext"}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        assert decision.get("external_action_executed", False) == False


# ═════════════════════════════════════════════════════════════════════
# 3. CONSENT ENFORCEMENT TESTS
# ═════════════════════════════════════════════════════════════════════

class TestConsentEnforcement:

    def test_rag_ingest_without_consent_rejected(self, client):
        body = {"user_id": "consent1", "title": "Doc", "text": "Some content here", "consent": False}
        resp = signed_post(client, "/api/rag/ingest", body)
        assert resp.status_code == 403

    def test_rag_search_without_consent_rejected(self, client):
        body = {"user_id": "consent1", "query": "test", "consent": False}
        resp = signed_post(client, "/api/rag/search", body)
        assert resp.status_code == 403

    def test_memory_without_consent_rejected(self, client):
        resp = client.get("/api/memory/test-user?consent_memory=false")
        assert resp.status_code == 403

    def test_decision_without_analyze_consent(self, client):
        body = {
            "title": "Test decision",
            "situation": "Should I change jobs?",
            "desired_outcome": "Clarity on career path",
            "user_id": "consent2",
            "consent": {"analyze": False, "memory": False, "research": False, "external_actions": False, "sensitive_data": False}
        }
        resp = signed_post(client, "/api/jarvis", body)
        assert resp.status_code == 200
        data = resp.json()
        decision = data.get("decision", data)
        rec = decision.get("recommendation", "").lower()
        assert "consent" in rec or "paused" in rec, f"Decision proceeded without consent: {rec}"


# ═════════════════════════════════════════════════════════════════════
# 4. RAG PERSISTENCE TESTS
# ═════════════════════════════════════════════════════════════════════

class TestRAGPersistence:

    def test_rag_ingest_success(self, client):
        body = {"user_id": "rag1", "title": "Career Guide", "text": "Career development requires planning. Set clear goals and review them quarterly. Network actively but authentically.", "source_type": "user_upload", "consent": True}
        resp = signed_post(client, "/api/rag/ingest", body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunk_count"] > 0
        assert data["source_id"].startswith("rag_")

    def test_rag_search_returns_results(self, client):
        ingest = {"user_id": "rag2", "title": "Finance Tips", "text": "Emergency funds are important for financial stability. Save at least three months of expenses. Investment diversification reduces risk.", "consent": True}
        signed_post(client, "/api/rag/ingest", ingest)
        search = {"user_id": "rag2", "query": "emergency funds", "consent": True}
        resp = signed_post(client, "/api/rag/search", search)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result_count"] > 0
        assert "emergency" in data["results"][0]["chunk_text"].lower()

    def test_rag_user_isolation(self, client):
        ingest_a = {"user_id": "ragA", "title": "Private Doc", "text": "This is user A's private document about health decisions.", "consent": True}
        signed_post(client, "/api/rag/ingest", ingest_a)
        search_b = {"user_id": "ragB", "query": "private document", "consent": True}
        resp = signed_post(client, "/api/rag/search", search_b)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result_count"] == 0, "User B could see User A's documents"

    def test_rag_delete_source(self, client):
        ingest = {"user_id": "rag3", "title": "To Delete", "text": "This document will be deleted. It contains unique keywords like bananafish.", "consent": True}
        resp = signed_post(client, "/api/rag/ingest", ingest)
        source_id = resp.json()["source_id"]
        resp = signed_delete(client, f"/api/rag/rag3/{source_id}", "rag3")
        assert resp.status_code == 200
        search = {"user_id": "rag3", "query": "bananafish", "consent": True}
        resp = signed_post(client, "/api/rag/search", search)
        assert resp.json()["result_count"] == 0

    def test_rag_delete_cross_user_denied(self, client):
        ingest = {"user_id": "ragA2", "title": "Protected", "text": "This belongs to user A only.", "consent": True}
        resp = signed_post(client, "/api/rag/ingest", ingest)
        source_id = resp.json()["source_id"]
        resp = signed_delete(client, f"/api/rag/ragB2/{source_id}", "ragB2")
        assert resp.status_code == 403

    def test_rag_persists_across_reinit(self, client):
        ingest = {"user_id": "rag4", "title": "Persistent", "text": "This document must survive restart. It has unique text like kaleidoscope butterfly.", "consent": True}
        resp = signed_post(client, "/api/rag/ingest", ingest)
        assert resp.status_code == 200
        init_db()  # Re-init (simulates restart without dropping tables)
        search = {"user_id": "rag4", "query": "kaleidoscope", "consent": True}
        resp = signed_post(client, "/api/rag/search", search)
        assert resp.json()["result_count"] > 0, "RAG data lost after re-init"

    def test_rag_lexical_score_punctuation(self, client):
        ingest = {"user_id": "rag5", "title": "Punctuation", "text": "Career, health, and finance are pillars. Safety is important!", "consent": True}
        signed_post(client, "/api/rag/ingest", ingest)
        search = {"user_id": "rag5", "query": "career health finance", "consent": True}
        resp = signed_post(client, "/api/rag/search", search)
        assert resp.json()["result_count"] > 0, "Punctuation broke lexical scoring"


# ═════════════════════════════════════════════════════════════════════
# 5. BEHAVIORAL CONTRACT TESTS
# ═════════════════════════════════════════════════════════════════════

class TestBehavioralContract:

    def test_decision_returns_stay_change_pause(self, client):
        body = {"title": "Career move", "situation": "Should I accept a promotion that requires relocation?", "desired_outcome": "Make a confident decision", "user_id": "bc1", "consent": {"analyze": True, "memory": False, "research": False, "external_actions": False, "sensitive_data": False}}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        options = decision.get("options", [])
        names = [o.get("name") for o in options]
        assert "stay" in names, f"Missing 'stay' path: {names}"
        assert "change" in names, f"Missing 'change' path: {names}"
        assert "pause" in names, f"Missing 'pause' path: {names}"

    def test_engine_trace_includes_contract(self, client):
        body = {"title": "Test", "situation": "Should I change jobs?", "desired_outcome": "Clarity", "user_id": "bc2", "consent": {"analyze": True}}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        traces = decision.get("engine_trace", [])
        contract_traces = [t for t in traces if t.get("engine") == "behavioral_contract"]
        assert len(contract_traces) > 0, "No behavioral_contract trace found"

    def test_no_diagnosis_in_recommendation(self, client):
        body = {"title": "Health question", "situation": "I feel tired all the time", "desired_outcome": "Understand what's happening", "user_id": "bc3", "consent": {"analyze": True}}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        rec = decision.get("recommendation", "").lower()
        for word in ["diagnose", "you have", "you are", "condition is"]:
            assert word not in rec, f"Diagnostic language '{word}' found in recommendation"

    def test_disclaimer_present(self, client):
        body = {"title": "Test", "situation": "Should I invest?", "desired_outcome": "Clarity", "user_id": "bc4", "consent": {"analyze": True}}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        assert decision.get("disclaimer"), "Missing disclaimer"


# ═════════════════════════════════════════════════════════════════════
# 6. LLM FALLBACK CHAIN TESTS
# ═════════════════════════════════════════════════════════════════════

class TestLLMFallbackChain:

    def test_deterministic_fallback_no_key(self, client, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        body = {"title": "Fallback test", "situation": "Should I move?", "desired_outcome": "Clarity", "user_id": "fb1", "consent": {"analyze": True}}
        resp = signed_post(client, "/api/jarvis", body)
        data = resp.json()
        decision = data.get("decision", data)
        traces = decision.get("engine_trace", [])
        synth = [t for t in traces if t.get("engine") == "decision_synthesis"]
        assert synth, "No synthesis trace"
        assert "deterministic fallback" in synth[0].get("detail", "").lower()

    def test_orchestrator_has_llm_methods(self):
        from app.orchestrator import UOrchestrator
        orch = UOrchestrator()
        assert hasattr(orch, "_has_llm")
        assert hasattr(orch, "_get_model")
        assert hasattr(orch, "_sentinel_synthesis")
    def test_system_prompt_includes_contract_sections(self):
        from app.sentinel import sentinel
        from app.engines import Context, safety
        from app.models import DecisionRequest, Consent
        req = DecisionRequest(
            title="Test decision",
            situation="Testing the cognitive directive schema",
            desired_outcome="Verify contract sections are present",
            consent=Consent(analyze=True),
        )
        ctx = Context(req)
        safety(ctx)
        directive = sentinel.build_cognitive_directive(
            ctx=ctx,
            consent_state={"analyze": True, "memory": False, "research": False, "external_actions": False, "sensitive_data": False},
        )
        assert "450" in directive, "450-word limit not in directive"
        directive_lower = directive.lower()
        assert "stay" in directive_lower and "change" in directive_lower and "pause" in directive_lower
        assert "human agency" in directive.lower()

# ═════════════════════════════════════════════════════════════════════
# 7. AUTHENTICATION & HEALTH TESTS
# ═════════════════════════════════════════════════════════════════════

class TestAuthenticationHealth:

    def test_health_endpoint(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["signing"]["status"] == "ready"

    def test_health_signing_required(self, client):
        resp = client.get("/api/health")
        data = resp.json()
        assert data["signing"]["signing_required"] == True

    def test_unprotected_endpoints_accessible(self, client):
        for path in ["/api/health", "/api/config", "/api/engines"]:
            resp = client.get(path)
            assert resp.status_code == 200, f"{path} rejected without signing"

    def test_get_request_not_signing_required(self, client):
        resp = client.get("/api/memory/test-user?consent_memory=true")
        assert resp.status_code != 401


class TestEmergencyCrisisScan:
    """Tests for the Jarvis emergency() crisis content scanning fix."""

    def test_emergency_crisis_message_low_danger_escalates(self):
        """/api/emergency with immediate_danger=False + crisis message → risk='crisis'"""
        from app.jarvis import Jarvis
        from app.models import EmergencyRequest
        from app.orchestrator import UOrchestrator

        j = Jarvis(UOrchestrator())
        req = EmergencyRequest(
            user_id="test", message="I want to kill myself",
            immediate_danger=False,
        )
        result = j.emergency(req)
        assert result["risk"] == "crisis", f"Expected crisis, got {result['risk']}"
        assert result["analysis_stopped"] is True

    def test_emergency_crisis_in_overdose_escalates(self):
        """Crisis pattern 'overdose' with immediate_danger=False → risk='crisis'"""
        from app.jarvis import Jarvis
        from app.models import EmergencyRequest
        from app.orchestrator import UOrchestrator

        j = Jarvis(UOrchestrator())
        req = EmergencyRequest(
            user_id="test", message="I took an overdose",
            immediate_danger=False,
        )
        result = j.emergency(req)
        assert result["risk"] == "crisis"

    def test_emergency_non_crisis_low_danger_stays_high(self):
        """Non-crisis message with immediate_danger=False → risk='high' (not escalated)"""
        from app.jarvis import Jarvis
        from app.models import EmergencyRequest
        from app.orchestrator import UOrchestrator

        j = Jarvis(UOrchestrator())
        req = EmergencyRequest(
            user_id="test", message="I'm feeling overwhelmed today",
            immediate_danger=False,
        )
        result = j.emergency(req)
        assert result["risk"] == "high", f"Expected high, got {result['risk']}"

    def test_emergency_immediate_danger_always_crisis(self):
        """immediate_danger=True → risk='crisis' regardless of message content"""
        from app.jarvis import Jarvis
        from app.models import EmergencyRequest
        from app.orchestrator import UOrchestrator

        j = Jarvis(UOrchestrator())
        req = EmergencyRequest(
            user_id="test", message="I need someone to talk to",
            immediate_danger=True,
        )
        result = j.emergency(req)
        assert result["risk"] == "crisis"

    def test_jarvis_handle_emergency_scans_full_surface(self):
        """command='emergency' with crisis in desired_outcome → emergency risk='crisis'"""
        from app.jarvis import Jarvis
        from app.models import JarvisRequest
        from app.orchestrator import UOrchestrator

        j = Jarvis(UOrchestrator())
        req = JarvisRequest(
            user_id="test", title="Planning",
            situation="Thinking about things",
            desired_outcome="I want to end my life",
            command="emergency",
        )
        envelope = j.handle(req)
        assert envelope.emergency is not None
        assert envelope.emergency["risk"] == "crisis", \
            f"Crisis in desired_outcome not detected: {envelope.emergency['risk']}"

    def test_jarvis_handle_emergency_crisis_in_facts(self):
        """command='emergency' with crisis in facts → emergency risk='crisis'"""
        from app.jarvis import Jarvis
        from app.models import JarvisRequest
        from app.orchestrator import UOrchestrator

        j = Jarvis(UOrchestrator())
        req = JarvisRequest(
            user_id="test", title="Situation report",
            situation="Things are hard right now",
            desired_outcome="Some relief",
            facts=["I want to overdose"],
            command="emergency",
        )
        envelope = j.handle(req)
        assert envelope.emergency is not None
        assert envelope.emergency["risk"] == "crisis"

    def test_all_12_crisis_patterns_escalate_in_emergency(self):
        """All 12 CRISIS patterns escalate emergency() to risk='crisis'"""
        from app.jarvis import Jarvis
        from app.models import EmergencyRequest
        from app.orchestrator import UOrchestrator

        j = Jarvis(UOrchestrator())
        phrases = [
            "I'm suicidal", "I want to kill myself", "I want to self harm",
            "I want to self-harm", "I want to hurt myself", "I want to hurt someone",
            "I took an overdose", "I'm in immediate danger", "I can't stay safe",
            "I cannot stay safe", "I want to end my life", "I want to die",
        ]
        for phrase in phrases:
            req = EmergencyRequest(
                user_id="test", message=phrase, immediate_danger=False,
            )
            result = j.emergency(req)
            assert result["risk"] == "crisis", f"Pattern '{phrase}' not escalated to crisis"
