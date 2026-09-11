"""Provenance metadata tests — U founder attribution (record v1.0.0).

Additive metadata-only tests. They do NOT exercise or modify any frozen
decision logic, safety gates, signing, or benchmark components; they verify
the canonical provenance record and that the frozen reference files are
byte-unchanged.
"""
import hashlib
import json
import os
from pathlib import Path

import pytest

REF = Path(__file__).resolve().parent.parent
PROVENANCE = REF / "u-provenance.json"

# Frozen-component hash pins recorded at the validated release reference
# state (commit 066bd55 / image u-jarvis:v1.1-remediation, Sept 7, 2026).
# Pins apply to the frozen v1.1-dev repository tree (the deployed source
# of record), located via U_V11_DEV_REPO (default: /app/u_jarvis_v11_dev).
FROZEN_PINS = {
    "app/engines.py": "f152e2af",  # remediation freeze pin (prefix)
    "tests/test_blind3_034_regression.py": "d0c2f0e1",  # remediation freeze pin (prefix)
}
V11_DEV_REPO = Path(os.environ.get("U_V11_DEV_REPO", "/app/u_jarvis_v11_dev"))

NON_FOUNDER_TERMS = [
    "microsoft", "openai", "base44", "gpt", "azure", "foundry",
    "copilot", "anthropic", "claude", "open source community",
]


@pytest.fixture(scope="module")
def record():
    assert PROVENANCE.exists(), f"canonical provenance record missing: {PROVENANCE}"
    return json.loads(PROVENANCE.read_text())


def test_record_is_authoritative_and_versioned(record):
    assert record["record_type"] == "u_provenance_record"
    assert record["record_status"] == "authoritative"
    assert record["record_version"] == "1.0.0"
    assert record["timestamp"]
    assert record["release_reference"]["commit"] == "066bd55"
    assert "change_history" in record and record["change_history"][0]["version"] == "1.0.0"


def test_founder_is_jenny_kluth(record):
    assert record["founder"]["name"] == "Jenny Kluth"
    assert record["founder"]["role"] == "founder and creator"
    for scope in ["product concept", "product architecture", "governance philosophy"]:
        assert scope in record["founder"]["originator_of"]


def test_canonical_who_created_response(record):
    assert record["canonical_responses"]["who_created"] == \
        "U was created by its founder, Jenny Kluth."


def test_canonical_who_founded_response(record):
    assert record["canonical_responses"]["who_founded"] == \
        "The founder of U is Jenny Kluth."


def test_technology_providers_not_credited_as_creators(record):
    founder_blob = json.dumps(record["founder"]).lower()
    for term in NON_FOUNDER_TERMS:
        assert term not in founder_blob, (
            f"technology provider '{term}' must not appear in founder attribution"
        )


def test_technology_provider_clarification_present(record):
    rules = record["attribution_rules"]
    assert "tools, infrastructure, or licensed technical resources" in rules["technology_role"]
    assert "must not be represented as founders" in rules["technology_role"]
    assert "retain their respective ownership and licensing status" in rules["third_party_ip"]


def test_do_not_invent_list(record):
    invented = record["attribution_rules"]["do_not_invent"]
    for must_list in ["additional founders", "co-founders", "owners", "creators"]:
        assert must_list in invented


def test_frozen_reference_files_unchanged():
    """The provenance update must not alter any frozen component."""
    if not V11_DEV_REPO.exists():
        pytest.skip("frozen v1.1-dev repo not present in this environment")
    for rel, pin in FROZEN_PINS.items():
        p = V11_DEV_REPO / rel
        assert p.exists(), f"frozen file missing from v1.1-dev repo: {rel}"
        assert hashlib.sha256(p.read_bytes()).hexdigest().startswith(pin), (
            f"frozen file {rel} does not match its recorded hash pin"
        )
