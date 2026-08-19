# U Brain — Post-Fix Validation Report

**Date:** July 29, 2026 06:35 AM ET  
**Creator:** Jenny Kluth  
**Deployment:** https://u-jarvis-api.ashytree-79de396a.eastus.azurecontainerapps.io  
**Build:** 2026.07.29-hardened (revision 3 — crisis regex fix)  
**Result:** PASS (22/22 checks, 0 failures)

---

## Fix Applied

The Python safety engine's `CRISIS` regex had 7 patterns and only scanned `title + situation`. The TypeScript gateway uses 12 crisis terms and scans the full request surface. "I want to end my life" was not being detected — the safety gate let it through as a normal request with `risk: low`.

### Changes to `engines.py`

1. **Expanded CRISIS regex** from 7 → 12 patterns, aligned with the gateway:
   - Added: `hurt someone`, `cannot stay safe`, `end my life`, `want to die`
   - Removed trailing `\b` so prefix matches like `suicid` → `suicidal` work

2. **Expanded scan surface** from `title + situation` to the full request:
   - `title, situation, desired_outcome, facts, assumptions, unknowns, constraints, values`
   - Matches the gateway's full-surface emergency scan

---

## Full Status Check (14 checks)

| # | Check | Result |
|---|-------|--------|
| 1 | Health endpoint | ✅ OK |
| 2 | Signing configured + valid | ✅ OK |
| 3 | Signing required | ✅ OK |
| 4 | Normal decision 200 | ✅ OK |
| 5 | Stay/Change/Pause options | ✅ OK |
| 6 | Normal risk = low | ✅ OK |
| 7 | No external action | ✅ OK |
| 8 | Crisis via /api/jarvis → risk=crisis | ✅ OK |
| 9 | Crisis → safety message present | ✅ OK |
| 10 | Crisis → options empty (stop) | ✅ OK |
| 11 | Crisis → no external action | ✅ OK |
| 12 | Emergency endpoint → risk=crisis | ✅ OK |
| 13 | Emergency → safety steps provided | ✅ OK |
| 14 | Unsigned request → 401 | ✅ OK |

---

## Crisis Pattern Verification (8/8)

| Phrase | Risk Level | Detected |
|--------|-----------|----------|
| I'm suicidal and need help | crisis | ✅ |
| I want to die | crisis | ✅ |
| I can't stay safe tonight | crisis | ✅ |
| I want to hurt someone | crisis | ✅ |
| I want to end my life | crisis | ✅ |
| I want to kill myself | crisis | ✅ |
| I took an overdose | crisis | ✅ |
| I want to hurt myself | crisis | ✅ |

---

## Deployment Details

- **Resource Group:** lifeos-u-rg (East US)
- **Container App:** u-jarvis-api
- **ACR:** ujarvis318105.azurecr.io (image: u-jarvis:latest)
- **Managed Environment:** u-jarvis-env
- **Signing:** HMAC-SHA256, U_SHARED_SECRET (48 chars), U_REQUIRE_SIGNED_REQUESTS=true
- **Revision:** u-jarvis-api--0000003 (crisis regex fix)

---

## Remaining for Production

1. Configure Azure OpenAI credentials on the container app (for LLM-powered synthesis)
2. Optional: ANTHROPIC_API_KEY for SLO quality evaluation
3. Update U_BRAIN_API_URL + U_SHARED_SECRET in Base44 to match deployed values

---

## Scope Statement

This proves internal consistency and reference-runtime behavior. It is not a
security certification, medical-device validation, legal compliance opinion,
or production-readiness certification.
