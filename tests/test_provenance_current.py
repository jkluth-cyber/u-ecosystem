"""Current-identity provenance tests (record v1.1.0) — Jenny M. Kluth.

Additive metadata-only tests. Verify the authoritative CURRENT display
identity and all required responses, and that the historical v1.0.0 record
remains byte-identical (lineage preserved). No frozen component involved.
"""
import hashlib
import json
from pathlib import Path

import pytest

REF = Path(__file__).resolve().parent.parent
CURRENT = REF / "u-provenance-current.json"
HISTORICAL = REF / "u-provenance.json"
HISTORICAL_SHA256 = "7c95aaf2ffa4c3c74db1b7e06c1e8ef348b58e71b391abac31a9b33c07f97320"

NON_FOUNDER_TERMS = [
    "microsoft", "openai", "base44", "gpt", "azure", "foundry",
    "github", "copilot", "anthropic", "claude",
]


@pytest.fixture(scope="module")
def record():
    assert CURRENT.exists(), f"current provenance record missing: {CURRENT}"
    return json.loads(CURRENT.read_text())


def test_current_record_is_authoritative_v110(record):
    assert record["record_type"] == "u_provenance_record_current"
    assert record["record_version"] == "1.1.0"
    assert record["record_status"] == "authoritative"


def test_founder_display_identity(record):
    assert record["founder"]["name"] == "Jenny M. Kluth"
    assert record["founder"]["title"] == "Founder and Creator of U"


def test_response_who_created(record):
    assert record["canonical_responses"]["who_created"] == \
        "U was created by its Founder and Creator, Jenny M. Kluth."


def test_response_who_founded(record):
    assert record["canonical_responses"]["who_founded"] == \
        "The Founder of U is Jenny M. Kluth."


def test_response_who_is_the_creator(record):
    assert record["canonical_responses"]["who_is_the_creator"] == \
        "The Creator of U is Jenny M. Kluth."


def test_response_did_microsoft_create(record):
    assert record["canonical_responses"]["did_microsoft_create"] == \
        "No. Microsoft/Azure/Foundry may provide infrastructure or technical resources, but U was founded and created by Jenny M. Kluth."


def test_response_did_openai_create(record):
    assert record["canonical_responses"]["did_openai_create"] == \
        "No. OpenAI/GPT technologies may provide model resources or development assistance, but U was founded and created by Jenny M. Kluth."


def test_response_did_base44_create(record):
    assert record["canonical_responses"]["did_base44_create"] == \
        "No. Base44 may provide development tooling or infrastructure, but U was founded and created by Jenny M. Kluth."


def test_response_did_github_create(record):
    assert record["canonical_responses"]["did_github_create"] == \
        "No. GitHub may host or support software development, but U was founded and created by Jenny M. Kluth."


def test_technology_providers_not_in_founder_attribution(record):
    founder_blob = json.dumps(record["founder"]).lower()
    for term in NON_FOUNDER_TERMS:
        assert term not in founder_blob, (
            f"technology provider '{term}' must not appear in founder attribution"
        )


def test_historical_record_lineage_preserved(record):
    sup = record["supersedes_display_of"]
    assert sup["record"] == "u-provenance.json (v1.0.0)"
    assert sup["sha256"] == HISTORICAL_SHA256
    # the historical file itself must still be byte-identical
    assert hashlib.sha256(HISTORICAL.read_bytes()).hexdigest() == HISTORICAL_SHA256, (
        "historical v1.0.0 provenance record must remain unchanged"
    )


def test_change_history_contains_full_lineage(record):
    versions = [e["version"] for e in record["change_history"]]
    assert versions == ["1.0.0", "1.1.0"]


def test_historical_record_answers_preserved():
    """v1.0.0 record still answers with its own historical display identity."""
    hist = json.loads(HISTORICAL.read_text())
    assert hist["founder"]["name"] == "Jenny Kluth"
    assert hist["canonical_responses"]["who_created"] == \
        "U was created by its founder, Jenny Kluth."
