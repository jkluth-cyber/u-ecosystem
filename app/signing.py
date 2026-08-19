"""
U — Secure Request Verification (Python side)
app/signing.py

Verifies HMAC-SHA256 signed requests from Base44 backend functions.

Signing payload format:
  timestamp + "." + request_id + "." + exact_request_body

Required headers:
  x-u-request-id
  x-u-user-hash
  x-u-timestamp
  x-u-signature

Required environment variables:
  U_SHARED_SECRET — shared HMAC secret (min 32 chars)
  U_REQUIRE_SIGNED_REQUESTS — "true" to enforce, anything else = dev mode

Rejects:
  - Missing signatures
  - Invalid signatures
  - Expired timestamps (>5 min skew)
  - Modified request bodies
  - Secrets shorter than 32 characters

Accepts timestamps in either format:
  - Unix epoch seconds (e.g. "1722256543") — used by Base44 TypeScript gateway
  - ISO 8601 (e.g. "2026-07-29T10:30:00Z") — used by Python clients
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timezone
from typing import Optional

SECRET_ENV = "U_SHARED_SECRET"
REQUIRE_SIGNED_ENV = "U_REQUIRE_SIGNED_REQUESTS"

HEADER_SIGNATURE = "x-u-signature"
HEADER_TIMESTAMP = "x-u-timestamp"
HEADER_REQUEST_ID = "x-u-request-id"
HEADER_USER_HASH = "x-u-user-hash"

MAX_CLOCK_SKEW_SECONDS = 300  # 5 minutes
MIN_SECRET_LENGTH = 32

# In-memory nonce/request-id cache for replay protection.
# For production with multiple workers, replace with Redis or a database.
_seen_request_ids: dict[str, float] = {}
REQUEST_ID_TTL_SECONDS = 600  # 10 minutes


def _get_secret() -> str:
    """Return the shared secret, raising if missing or too short."""
    secret = os.environ.get(SECRET_ENV, "").strip()
    if not secret:
        raise RuntimeError(f"{SECRET_ENV} not configured")
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"{SECRET_ENV} must be at least {MIN_SECRET_LENGTH} characters "
            f"(got {len(secret)})"
        )
    return secret


def _is_signing_required() -> bool:
    """Return True if signed requests are enforced."""
    return os.environ.get(REQUIRE_SIGNED_ENV, "").strip().lower() == "true"


def _hmac_sha256(key: str, message: str) -> str:
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _signing_payload(timestamp: str, request_id: str, body: str) -> str:
    """Build the exact signing payload: timestamp.request_id.body"""
    return f"{timestamp}.{request_id}.{body}"


def _parse_timestamp(timestamp: str) -> datetime:
    """
    Parse a timestamp string into a timezone-aware datetime.

    Accepts both:
      - Unix epoch seconds as string (e.g. "1722256543")
      - ISO 8601 (e.g. "2026-07-29T10:30:00Z" or "2026-07-29T10:30:00+00:00")

    Returns a timezone-aware UTC datetime.
    Raises ValueError if the format is not recognized.
    """
    # Try Unix epoch first (all digits, possibly with optional sign)
    stripped = timestamp.strip()
    if stripped.lstrip("+-").isdigit():
        epoch = int(stripped)
        return datetime.fromtimestamp(epoch, tz=timezone.utc)

    # Try ISO 8601
    return datetime.fromisoformat(
        stripped.replace("Z", "+00:00")
    )


def _cleanup_seen_ids() -> None:
    """Remove expired request IDs from the cache."""
    now = time.time()
    expired = [
        rid
        for rid, ts in _seen_request_ids.items()
        if now - ts > REQUEST_ID_TTL_SECONDS
    ]
    for rid in expired:
        del _seen_request_ids[rid]


def verify_request(
    method: str,
    path: str,
    body: str,
    headers: dict[str, str],
) -> tuple[bool, Optional[str]]:
    """
    Verify a signed request from Base44.

    Args:
        method: HTTP method (not used in signing, kept for interface)
        path: Request path (not used in signing, kept for interface)
        body: Raw request body as string
        headers: Request headers (case-insensitive keys)

    Returns:
        (is_valid, error_message)
    """
    # Normalize header keys to lowercase
    normalized = {k.lower(): v for k, v in headers.items()}

    signature = normalized.get(HEADER_SIGNATURE, "")
    timestamp = normalized.get(HEADER_TIMESTAMP, "")
    request_id = normalized.get(HEADER_REQUEST_ID, "")

    if not signature or not timestamp or not request_id:
        return False, "Missing required signature headers"

    # ── Timestamp freshness ──────────────────────────────────────────
    try:
        ts = _parse_timestamp(timestamp)
        now = datetime.now(timezone.utc)
        skew = abs((now - ts).total_seconds())

        if skew > MAX_CLOCK_SKEW_SECONDS:
            return False, f"Timestamp expired (skew: {skew:.0f}s, max: {MAX_CLOCK_SKEW_SECONDS}s)"
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"

    # ── Replay protection (request_id check) ─────────────────────────
    _cleanup_seen_ids()

    if request_id in _seen_request_ids:
        return False, "Request ID already used (replay detected)"

    # ── Signature verification (before nonce registration) ───────────
    try:
        secret = _get_secret()
    except RuntimeError as exc:
        return False, str(exc)

    payload = _signing_payload(timestamp, request_id, body)
    expected_signature = _hmac_sha256(secret, payload)

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature, expected_signature):
        return False, "Signature mismatch"

    # Register nonce only AFTER signature verification succeeds
    # (prevents DoS where attacker burns request IDs with invalid signatures)
    _seen_request_ids[request_id] = time.time()

    return True, None


def health_check() -> dict:
    """Return signing layer status for health checks."""
    secret = os.environ.get(SECRET_ENV, "").strip()
    return {
        "signing_key_configured": bool(secret),
        "signing_key_length": len(secret),
        "signing_key_valid": len(secret) >= MIN_SECRET_LENGTH,
        "signing_required": _is_signing_required(),
        "status": "ready" if len(secret) >= MIN_SECRET_LENGTH else "missing_or_short_key",
        "seen_request_ids": len(_seen_request_ids),
    }
