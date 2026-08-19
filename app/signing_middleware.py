"""
U — Secure Request Verification Middleware
app/signing_middleware.py

FastAPI middleware that verifies HMAC-SHA256 signed requests from Base44.
Skips verification for health checks and when signing is not required.

Enforcement decision order:
  1. U_REQUIRE_SIGNED_REQUESTS == "true" → always enforce
  2. U_SHARED_SECRET is set (≥32 chars) → enforce
  3. Neither set → dev mode, skip verification

This aligns with signing.py which reads U_SHARED_SECRET for HMAC verification,
and with uDecisionResearch.ts which reads U_SHARED_SECRET from Base44 secrets.
"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse

from .signing import verify_request, health_check, MIN_SECRET_LENGTH

# Paths that do not require signature verification
UNPROTECTED_PATHS = {"/", "/api/health", "/api/config", "/api/engines", "/static"}


def _should_enforce_signing() -> bool:
    """
    Decide whether to enforce request signing.

    Returns True if either:
      - U_REQUIRE_SIGNED_REQUESTS is "true" (explicit enforcement flag)
      - U_SHARED_SECRET is set and meets minimum length (key configured)
    """
    if os.environ.get("U_REQUIRE_SIGNED_REQUESTS", "").strip().lower() == "true":
        return True

    secret = os.environ.get("U_SHARED_SECRET", "").strip()
    return len(secret) >= MIN_SECRET_LENGTH


async def verify_signature_middleware(request: Request, call_next):
    """
    Middleware that verifies request signatures.
    - Skips health/config/static endpoints
    - Skips when signing is not configured (dev mode)
    - Enforces verification on all mutating API endpoints when key is configured
    """
    path = request.url.path

    # Allow unprotected paths
    if path in UNPROTECTED_PATHS or path.startswith("/static"):
        return await call_next(request)

    # Skip verification if signing is not required (development mode)
    if not _should_enforce_signing():
        return await call_next(request)

    # Only verify POST/PUT/PATCH/DELETE requests
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return await call_next(request)

    # Read body
    body = await request.body()
    body_str = body.decode("utf-8") if body else ""

    # Extract headers as dict
    headers = dict(request.headers)

    # Verify signature
    is_valid, error = verify_request(
        method=request.method,
        path=path,
        body=body_str,
        headers=headers,
    )

    if not is_valid:
        return JSONResponse(
            status_code=401,
            content={
                "error": "signature_verification_failed",
                "message": error,
                "external_action_executed": False,
            },
        )

    # Re-inject body since we consumed it
    # (FastAPI needs the body to be available for the route handler)
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive

    return await call_next(request)


def signing_health():
    """Return signing layer status for the health endpoint."""
    return health_check()
