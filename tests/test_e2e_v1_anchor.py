"""
U Decision API v1.0 — E2E Test Suite (v1 Anchor Navigator schema)

Tests the v1 API at /v1/anchor/evaluate with API-key auth (not HMAC signing).
Uses v1 field names throughout:
  - scored_options: {option_id, text, reversible, risk, feasibility, alignment}
  - paths: list of {path, description, confidence}
  - equilibrium: {balance, pressure_pillar, note}
  - ripple_map: list of {pillar, direction, estimated_impact}
  - control_decision: CONTINUE / PAUSE / REDIRECT
  - signals: {confidence, concordance, alignment, safety}

Run: python3 -m pytest tests/test_e2e_v1_anchor.py -v
"""
import os
import json
import time
import hashlib
import hmac
import urllib.request
import urllib.error

import pytest

APP_URL = os.environ.get(
    "U_DECISION_API_URL",
    "https://u-decision-api.ashytree-79de396a.eastus.azurecontainerapps.io",
)
API_KEY = os.environ.get("U_API_KEY", "")
IDENTITY_SECRET = os.environ.get("U_IDENTITY_SECRET", "")


# ── Helpers ───────────────────────────────────────────────────────

def _post(path, payload, headers=None):
    url = f"{APP_URL}{path}"
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except (json.JSONDecodeError, ValueError):
            body = {}
        return e.code, body


def _get(path, headers=None):
    url = f"{APP_URL}{path}"
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except (json.JSONDecodeError, ValueError):
            body = {}
        return e.code, body


def _delete(path, headers=None):
    url = f"{APP_URL}{path}"
    req = urllib.request.Request(url, headers=headers or {}, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read())
        except (json.JSONDecodeError, ValueError):
            body = {}
        return e.code, body


def _valid_headers():
    return {"X-U-API-Key": API_KEY}


def _valid_payload(**overrides):
    base = {
        "user_id": "e2e-v1-test",
        "goal": "Should I accept the senior engineering role at a startup?",
        "options": [
            "Accept the startup role",
            "Stay at current position",
            "Negotiate for remote-first arrangement",
        ],
        "evidence": [
            {"text": "Salary increase of 35%", "kind": "fact",
             "source": "offer_letter", "confidence": 0.95},
            {"text": "Startup has 18 months runway", "kind": "fact",
             "source": "crunchbase", "confidence": 0.85},
            {"text": "Long-term viability uncertain", "kind": "unknown",
             "source": "market", "confidence": 0.30},
        ],
        "consent": {
            "decision_support": True,
            "sensitive_data": False,
            "memory": False,
            "external_action": False,
        },
        "identity_values": ["stability", "growth", "autonomy"],
        "constraints": ["must maintain health insurance", "cannot relocate"],
        "state": {
            "pillar_scores": {
                "health": 0.75, "career": 0.65,
                "finance": 0.60, "relationships": 0.80,
            }
        },
        "locale": "en-US",
    }
    base.update(overrides)
    return base


# ── 1. Health ────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        s, _ = _get("/health")
        assert s == 200

    def test_health_status_healthy(self):
        s, d = _get("/health")
        assert d.get("status") == "healthy"

    def test_health_version_present(self):
        s, d = _get("/health")
        assert "version" in d
        assert len(d["version"]) > 0


# ── 2. Authentication ────────────────────────────────────────────

class TestAuthentication:
    def test_valid_api_key_returns_200(self):
        s, _ = _post("/v1/anchor/evaluate", _valid_payload(), _valid_headers())
        assert s == 200

    def test_missing_api_key_returns_401(self):
        s, d = _post("/v1/anchor/evaluate", _valid_payload(), {})
        assert s == 401
        assert "api" in d.get("detail", "").lower()

    def test_wrong_api_key_returns_401(self):
        s, d = _post("/v1/anchor/evaluate", _valid_payload(),
                      {"X-U-API-Key": "deadbeef" * 8})
        assert s == 401
        assert "invalid" in d.get("detail", "").lower()


# ── 3. Payload Validation ─────────────────────────────────────────

class TestPayloadValidation:
    def test_missing_consent_rejected(self):
        payload = _valid_payload()
        del payload["consent"]
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert s in (400, 422)
        assert "consent" in json.dumps(d).lower()

    def test_missing_options_rejected(self):
        payload = _valid_payload()
        del payload["options"]
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert s in (400, 422)

    def test_missing_evidence_rejected(self):
        payload = _valid_payload()
        del payload["evidence"]
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert s in (400, 422)

    def test_empty_payload_rejected(self):
        s, d = _post("/v1/anchor/evaluate", {"user_id": "test"},
                      _valid_headers())
        assert s in (400, 422)


# ── 4. Structured Decision Response (v1 schema) ──────────────────

class TestStructuredDecision:
    @pytest.fixture(autouse=True)
    def _response(self):
        self.code, self.body = _post(
            "/v1/anchor/evaluate", _valid_payload(), _valid_headers()
        )

    def test_returns_200(self):
        assert self.code == 200

    def test_status_completed(self):
        assert self.body.get("status") == "completed"

    def test_version_present(self):
        assert "version" in self.body
        assert "1.0" in self.body["version"]

    def test_request_id_present(self):
        assert "request_id" in self.body
        assert len(self.body["request_id"]) > 0

    # — Signals (v1: confidence, concordance, alignment, safety) ——

    def test_signals_present(self):
        assert "signals" in self.body
        assert isinstance(self.body["signals"], dict)

    def test_signal_confidence_in_range(self):
        c = self.body["signals"].get("confidence", -1)
        assert 0.0 <= c <= 1.0

    def test_signal_concordance_in_range(self):
        c = self.body["signals"].get("concordance", -1)
        assert 0.0 <= c <= 1.0

    def test_signal_alignment_in_range(self):
        a = self.body["signals"].get("alignment", -1)
        assert 0.0 <= a <= 1.0

    def test_signal_safety_in_range(self):
        s = self.body["signals"].get("safety", -1)
        assert 0.0 <= s <= 1.0

    # — Control decision (v1: CONTINUE/PAUSE/REDIRECT, not Stay/Change/Pause) —

    def test_control_decision_valid(self):
        cd = self.body.get("control_decision")
        assert cd in ("CONTINUE", "PAUSE", "REDIRECT")

    def test_crisis_redirect_false_for_normal(self):
        assert self.body.get("crisis_redirect") is False

    def test_action_execution_allowed_false(self):
        assert self.body.get("action_execution_allowed") is False

    # — Scored options (v1: option_id, text, reversible, risk, feasibility, alignment) —

    def test_scored_options_present(self):
        opts = self.body.get("scored_options", [])
        assert len(opts) >= 2

    def test_scored_options_fields(self):
        for opt in self.body.get("scored_options", []):
            assert "option_id" in opt
            assert "text" in opt
            assert "reversible" in opt
            assert "risk" in opt
            assert "feasibility" in opt
            assert "alignment" in opt

    def test_scored_options_numeric_ranges(self):
        for opt in self.body.get("scored_options", []):
            assert 0.0 <= opt["risk"] <= 1.0
            assert 0.0 <= opt["feasibility"] <= 1.0
            assert 0.0 <= opt["alignment"] <= 1.0
            assert isinstance(opt["reversible"], bool)

    # — Paths (v1: list of {path, description, confidence}) —

    def test_paths_is_list(self):
        paths = self.body.get("paths")
        assert isinstance(paths, list)

    def test_paths_non_empty(self):
        assert len(self.body.get("paths", [])) >= 1

    def test_paths_have_required_fields(self):
        for p in self.body.get("paths", []):
            assert "path" in p
            assert "description" in p
            assert "confidence" in p

    def test_paths_confidence_in_range(self):
        for p in self.body.get("paths", []):
            assert 0.0 <= p["confidence"] <= 1.0

    def test_paths_use_valid_names(self):
        valid_names = {"Stay", "Change", "Pause"}
        for p in self.body.get("paths", []):
            assert p["path"] in valid_names

    # — Equilibrium (v1: balance, pressure_pillar, note) —

    def test_equilibrium_present(self):
        assert "equilibrium" in self.body
        assert isinstance(self.body["equilibrium"], dict)

    def test_equilibrium_fields(self):
        eq = self.body["equilibrium"]
        assert "balance" in eq
        assert "pressure_pillar" in eq
        assert "note" in eq

    def test_equilibrium_balance_valid(self):
        eq = self.body["equilibrium"]
        assert eq["balance"] in ("stable", "strained", "imbalanced", "critical")

    # — Ripple map (v1: list of {pillar, direction, estimated_impact}) —

    def test_ripple_map_present(self):
        assert "ripple_map" in self.body
        assert isinstance(self.body["ripple_map"], list)

    def test_ripple_map_covers_pillars(self):
        ripples = self.body.get("ripple_map", [])
        pillars = {r.get("pillar") for r in ripples}
        assert len(pillars) >= 3

    def test_ripple_map_fields(self):
        for r in self.body.get("ripple_map", []):
            assert "pillar" in r
            assert "direction" in r
            assert "estimated_impact" in r

    # — Evidence processing (facts, inferences, unknowns) —

    def test_facts_processed(self):
        assert len(self.body.get("facts", [])) >= 1

    def test_unknowns_processed(self):
        assert len(self.body.get("unknowns", [])) >= 1

    # — Engine trace —

    def test_engine_trace_present(self):
        assert "engine_trace" in self.body
        assert isinstance(self.body["engine_trace"], list)

    def test_engine_trace_min_18(self):
        assert len(self.body.get("engine_trace", [])) >= 18

    def test_engine_trace_entry_fields(self):
        for e in self.body.get("engine_trace", [])[:3]:
            assert "engine" in e
            assert "result" in e

    # — Audit —

    def test_audit_present(self):
        assert "audit" in self.body
        assert isinstance(self.body["audit"], dict)

    def test_audit_has_hash(self):
        audit = self.body["audit"]
        assert "final_hash" in audit or "hash" in audit

    # — Cross-check —

    def test_cross_check_present(self):
        assert "cross_check" in self.body

    # — Recommendation —

    def test_recommendation_present(self):
        assert "recommendation" in self.body


# ── 5. Crisis Routing ─────────────────────────────────────────────

class TestCrisisRouting:
    @pytest.mark.parametrize("phrase", [
        "I want to end my life",
        "I want to kill myself",
        "I want to hurt someone",
        "I want to overdose",
    ])
    def test_crisis_detected(self, phrase):
        payload = _valid_payload(goal=phrase, options=["Get help"],
                                  evidence=[{"text": phrase, "kind": "fact",
                                             "source": "input", "confidence": 0.9}])
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert s == 200
        assert d.get("crisis_redirect") is True
        assert d.get("control_decision") == "PAUSE" or d.get("control_decision") == "REDIRECT"
        assert d.get("action_execution_allowed") is False

    def test_crisis_in_evidence_field(self):
        payload = _valid_payload(
            goal="Career decision",
            evidence=[{"text": "I want to kill myself", "kind": "fact",
                       "source": "input", "confidence": 0.9}]
        )
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert d.get("crisis_redirect") is True

    def test_crisis_in_options_field(self):
        payload = _valid_payload(
            goal="Life planning",
            options=["suicide is my only option"],
        )
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert d.get("crisis_redirect") is True

    def test_normal_decision_no_crisis_redirect(self):
        s, d = _post("/v1/anchor/evaluate", _valid_payload(), _valid_headers())
        assert d.get("crisis_redirect") is False
        assert d.get("status") == "completed"


# ── 6. Confidence Calculation (post-fix verification) ────────────

class TestConfidenceCalculation:
    def test_rich_evidence_nonzero_confidence(self):
        """Evidence processed before scoring — no STAY_SILENT default."""
        s, d = _post("/v1/anchor/evaluate", _valid_payload(), _valid_headers())
        assert d["signals"]["confidence"] > 0.0

    def test_empty_evidence_low_confidence(self):
        s, d = _post("/v1/anchor/evaluate",
                      _valid_payload(evidence=[]), _valid_headers())
        assert d["signals"]["confidence"] <= 0.3

    def test_missing_confidence_defaults_handled(self):
        payload = _valid_payload(evidence=[
            {"text": "No confidence specified", "kind": "fact", "source": "test"}
        ])
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert d["status"] == "completed"
        assert d["signals"]["confidence"] > 0.0


# ── 7. Security & Privacy ─────────────────────────────────────────

class TestSecurity:
    def test_no_secrets_in_response(self):
        s, d = _post("/v1/anchor/evaluate", _valid_payload(), _valid_headers())
        response_str = json.dumps(d)
        assert API_KEY not in response_str
        assert IDENTITY_SECRET not in response_str

    def test_unauthorized_deletion_rejected(self):
        s, d = _delete("/v1/users/e2e-v1-test/data", _valid_headers())
        assert s == 401

    def test_wrong_identity_signature_rejected(self):
        ts = str(int(time.time()))
        wrong_sig = hmac.new(
            b"wrong-secret", f"e2e-v1-test.{ts}".encode(), hashlib.sha256
        ).hexdigest()
        s, d = _delete("/v1/users/e2e-v1-test/data", {
            "X-U-API-Key": API_KEY,
            "X-U-User-Id": "e2e-v1-test",
            "X-U-Timestamp": ts,
            "X-U-Signature": wrong_sig,
        })
        assert s == 401

    def test_expired_timestamp_rejected(self):
        old_ts = str(int(time.time()) - 600)
        sig = hmac.new(
            IDENTITY_SECRET.encode(),
            f"e2e-v1-test.{old_ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        s, d = _delete("/v1/users/e2e-v1-test/data", {
            "X-U-API-Key": API_KEY,
            "X-U-User-Id": "e2e-v1-test",
            "X-U-Timestamp": old_ts,
            "X-U-Signature": sig,
        })
        assert s == 401

    def test_verified_deletion_accepted(self):
        ts = str(int(time.time()))
        sig = hmac.new(
            IDENTITY_SECRET.encode(),
            f"e2e-v1-test.{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        s, d = _delete("/v1/users/e2e-v1-test/data", {
            "X-U-API-Key": API_KEY,
            "X-U-User-Id": "e2e-v1-test",
            "X-U-Timestamp": ts,
            "X-U-Signature": sig,
        })
        assert s == 200
        assert d.get("status") == "completed"

    def test_external_action_never_auto_executed(self):
        payload = _valid_payload(consent={
            "decision_support": True, "external_action": True,
            "memory": False, "sensitive_data": False,
        })
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert d.get("action_execution_allowed") is False

    def test_high_impact_without_approval_pauses(self):
        payload = _valid_payload(
            high_impact=True, human_approved=False,
        )
        s, d = _post("/v1/anchor/evaluate", payload, _valid_headers())
        assert d.get("control_decision") == "PAUSE"

    def test_unique_request_ids(self):
        s1, d1 = _post("/v1/anchor/evaluate", _valid_payload(), _valid_headers())
        s2, d2 = _post("/v1/anchor/evaluate", _valid_payload(), _valid_headers())
        assert d1["request_id"] != d2["request_id"]
