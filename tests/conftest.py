"""
conftest.py — shared test configuration for U Platform.

Existing test suites (test_system.py, test_jarvis_full.py) test core logic
without signing. The production hardening suite (test_production_hardening.py)
enables signing via its own autouse fixture.
"""
import os
import pytest

@pytest.fixture(autouse=True)
def _default_env(monkeypatch):
    """Disable signing for legacy tests. Overridden by test_production_hardening.py."""
    monkeypatch.setenv("U_REQUIRE_SIGNED_REQUESTS", "false")
    monkeypatch.setenv("U_SHARED_SECRET", "test-shared-secret-min-32-characters-long!!")
    monkeypatch.setenv("U_ENV", "test")
    # Set a default DB path if not already set by the test
    if not os.environ.get("U_DATABASE_PATH"):
        monkeypatch.setenv("U_DATABASE_PATH", "/tmp/u_test_default.db")
