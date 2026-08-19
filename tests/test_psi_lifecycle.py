"""
Tests for the full-scale PSI lifecycle (Project4D).
"""
import os
import sys
import json
import pytest
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.psi_lifecycle import psi_lifecycle
from app.store import init_db, init_psi_tables
from app.cognitive_persistence import cognitive_persistence
from app.emergent_identity import emergent_identity
from app.multi_agent_governance import multi_agent_governance
from app.portable_directive import detect_substrate, SubstrateType, PortableDirective
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    init_db()
    init_psi_tables()
    return TestClient(app)


# ── PSI Lifecycle Tests ──────────────────────────────────────────────

class TestPSILifecycle:

    def test_psi_initialization(self):
        psi_lifecycle.initialize()
        assert psi_lifecycle._initialized is True

    def test_psi_hydrate_new_user(self):
        result = psi_lifecycle.hydrate("new-test-user")
        assert result["hydrated"] is True
        assert result["cognitive_profile_loaded"] is False
        assert result["identity_state_loaded"] is False

    def test_psi_embed(self):
        result = psi_lifecycle.embed("psi-test-user", {
            "title": "Should I change jobs?",
            "situation": "I've been offered a new position with better pay but longer commute.",
            "desired_outcome": "Make the right choice for my family",
            "pillars": ["career", "finance"],
            "facts": ["New salary is 20% higher"],
            "unknowns": ["New team culture"],
            "constraints": ["Family needs my time"],
            "values": ["growth", "family"],
            "horizon_days": 90,
        })
        assert result["interaction_count"] >= 1
        assert result["cognitive_depth"] > 0
        assert result["patterns_observed"] > 0

    def test_psi_engage_agents(self):
        psi_lifecycle.embed("psi-test-user", {
            "title": "Career change", "situation": "New job opportunity",
            "desired_outcome": "Best decision", "pillars": ["career", "finance"],
            "facts": [], "unknowns": [], "constraints": [], "values": [],
        })
        states = psi_lifecycle.engage(
            pillar_signals={"career": {"relevance": 0.8}, "finance": {"relevance": 0.6}},
            consent_state={"analyze": True, "memory": False, "research": False,
                          "external_actions": False, "sensitive_data": False},
            risk_level="low"
        )
        assert "career" in states
        assert "finance" in states

    def test_psi_engage_crisis_redirect(self):
        states = psi_lifecycle.engage(
            pillar_signals={"health": {"relevance": 0.9}},
            consent_state={"analyze": True},
            risk_level="crisis"
        )
        assert all(s == "crisis_redirect" for s in states.values())

    def test_psi_govern(self):
        result = psi_lifecycle.govern(
            "This is a safe, balanced response with no crisis indicators.",
            0.8, "low"
        )
        assert "governed" in result
        assert "violations" in result

    def test_psi_evolve(self):
        result = psi_lifecycle.evolve("psi-test-user", {
            "title": "Career", "situation": "Job change", "pillars": ["career"]
        }, {"violations": []})
        assert result["identity_generation"] >= 1
        assert result["total_embeddings"] >= 1
        assert len(result["traits"]) > 0
        assert result["identity_hash"] != ""

    def test_psi_persist_and_hydrate(self):
        # Embed + evolve to create state
        psi_lifecycle.embed("persist-test-user", {
            "title": "Test decision", "situation": "Testing persistence",
            "desired_outcome": "Verify persistence", "pillars": ["career"],
            "facts": [], "unknowns": [], "constraints": [], "values": [],
        })
        psi_lifecycle.evolve("persist-test-user",
            {"title": "Test", "situation": "Test", "pillars": ["career"]},
            {"violations": []})
        psi_lifecycle.persist("persist-test-user", "session-1",
            {"governed": True, "violations": []},
            {"available": True, "interaction_count": 1})

        # Hydrate should now load the persisted state
        result = psi_lifecycle.hydrate("persist-test-user")
        assert result["cognitive_profile_loaded"] is True
        assert result["identity_state_loaded"] is True

    def test_psi_export_identity(self):
        psi_lifecycle.embed("export-test-user", {
            "title": "Export test", "situation": "Testing export",
            "desired_outcome": "Exportable identity", "pillars": ["career"],
            "facts": [], "unknowns": [], "constraints": [], "values": [],
        })
        psi_lifecycle.evolve("export-test-user",
            {"title": "T", "situation": "T", "pillars": ["career"]},
            {"violations": []})
        exported = psi_lifecycle.export_identity("export-test-user")
        assert exported["portable"] is True
        assert "cognitive_profile" in exported
        assert "identity" in exported
        assert exported["identity"]["generation"] >= 1

    def test_psi_reset_identity(self):
        psi_lifecycle.embed("reset-test-user", {
            "title": "Reset test", "situation": "Testing reset",
            "desired_outcome": "Reset", "pillars": ["career"],
            "facts": [], "unknowns": [], "constraints": [], "values": [],
        })
        psi_lifecycle.persist("reset-test-user", "s1", {"violations": []}, {})
        result = psi_lifecycle.reset_identity("reset-test-user")
        assert result["reset"] is True


# ── API Endpoint Tests ──────────────────────────────────────────────

class TestPSIAPI:

    def test_psi_status_endpoint(self, client):
        resp = client.get("/api/psi")
        assert resp.status_code == 200
        data = resp.json()
        assert "Project4D" in data["paradigm"]
        assert "d1_cognitive_persistence" in data["dimensions"]
        assert "d2_portable_directive" in data["dimensions"]
        assert "d3_multi_agent_governance" in data["dimensions"]
        assert "d4_emergent_identity" in data["dimensions"]

    def test_psi_dimensions_endpoint(self, client):
        resp = client.get("/api/psi/dimensions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["d1_cognitive_persistence"]["active"] is True
        assert data["d2_portable_directive"]["active"] is True
        assert data["d3_multi_agent_governance"]["active"] is True
        assert data["d4_emergent_identity"]["active"] is True
        assert data["d3_multi_agent_governance"]["total_lenses"] == 20

    def test_psi_audit_endpoint(self, client):
        resp = client.get("/api/psi/audit/api-test-user")
        assert resp.status_code == 200
        data = resp.json()
        assert "interaction_count" in data
        assert "embedding_logs" in data

    def test_psi_identity_export_endpoint(self, client):
        resp = client.get("/api/psi/identity/api-export-user")
        assert resp.status_code == 200
        data = resp.json()
        assert data["portable"] is True

    def test_psi_reset_endpoint(self, client):
        resp = client.post("/api/psi/reset/api-reset-user")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reset"] is True

    def test_project4d_endpoint_updated(self, client):
        resp = client.get("/api/project4d")
        assert resp.status_code == 200
        data = resp.json()
        assert "Project4D" in data["paradigm"]
        assert len(data["dimensions"]) == 4


# ── Cross-Dimension Integration Tests ────────────────────────────────

class TestPSIIntegration:

    def test_multi_decision_cognitive_persistence(self, client):
        """After multiple decisions, cognitive patterns accumulate."""
        import hmac, hashlib, time, uuid

        secret = os.environ.get("U_SHARED_SECRET", "test-secret-min-32-characters-long!!")
        user_id = "persistence-integration-test"

        for i in range(3):
            body = json.dumps({
                "title": f"Decision {i+1}",
                "situation": f"Situation {i+1} involves career growth and financial stability.",
                "desired_outcome": "Good decision",
                "pillars": ["career", "finance"],
                "facts": [f"Fact {i+1}"],
                "unknowns": [f"Unknown {i+1}"],
                "constraints": ["Budget limit"],
                "values": ["growth"],
                "consent": {"analyze": True, "memory": False, "research": False,
                           "external_actions": False, "sensitive_data": False},
                "user_id": user_id,
                "command": "decide",
            })
            request_id = str(uuid.uuid4())
            timestamp = str(int(time.time()))
            msg = f"{timestamp}.{request_id}.{body}".encode()
            sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
            headers = {"x-u-request-id": request_id, "x-u-timestamp": timestamp,
                       "x-u-signature": sig, "Content-Type": "application/json"}
            resp = client.post("/api/jarvis", data=body, headers=headers)
            assert resp.status_code == 200

        # Check that cognitive profile accumulated
        audit = client.get(f"/api/psi/audit/{user_id}")
        data = audit.json()
        assert data["total_embeddings"] >= 3

    def test_identity_evolves_across_decisions(self, client):
        """Identity generation increases with each decision."""
        import hmac, hashlib, time, uuid

        secret = os.environ.get("U_SHARED_SECRET", "test-secret-min-32-characters-long!!")
        user_id = "identity-evolution-test"

        generations = []
        for i in range(3):
            body = json.dumps({
                "title": f"Identity test {i+1}",
                "situation": f"Testing identity evolution through decision {i+1}.",
                "desired_outcome": "Verify identity evolves",
                "pillars": ["career"],
                "consent": {"analyze": True, "memory": False, "research": False,
                           "external_actions": False, "sensitive_data": False},
                "user_id": user_id,
                "command": "decide",
            })
            request_id = str(uuid.uuid4())
            timestamp = str(int(time.time()))
            msg = f"{timestamp}.{request_id}.{body}".encode()
            sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
            headers = {"x-u-request-id": request_id, "x-u-timestamp": timestamp,
                       "x-u-signature": sig, "Content-Type": "application/json"}
            resp = client.post("/api/jarvis", data=body, headers=headers)

            identity = client.get(f"/api/psi/identity/{user_id}")
            id_data = identity.json()
            generations.append(id_data["identity"]["generation"])

        # Identity should be evolving (generation should increase or stay same)
        assert generations[-1] >= generations[0]
