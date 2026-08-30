# U + JARVIS — Full-Scale Decision Intelligence Ecosystem

Creator: [Jenny Kluth](https://github.com/jkluth-cyber)  
Version: 2026.08.05-pps-v1.0.2  
Repository: [github.com/jkluth-cyber/u-ecosystem](https://github.com/jkluth-cyber/u-ecosystem)  
Production API: [u-jarvis-api.ashytree-79de396a.eastus.azurecontainerapps.io](https://u-jarvis-api.ashytree-79de396a.eastus.azurecontainerapps.io)

U is the complete consent-first Human Decision Intelligence ecosystem.
U Brain is its only reasoning and orchestration core. JARVIS is the
conversational and visual command/interpretation layer inside U—not a
second brain or a separate product.

`Person → JARVIS → U Brain → 4 Pillar Sub-Brains + 18 Intelligence Engines
→ Governed Services → Human Approval Boundary`

## Current Release

**U v1.0.2** — LIVE in production. 100/100 verified.

| | |
|---|---|
| **Release** | [U v1.0.2 Release Announcement](release_manifests/U_v1.0.2_Release_Announcement.md) |
| **Manifest chain** | [5 frozen documents](release_manifests/) |
| **Manifest commit** | [`b2b4003`](https://github.com/jkluth-cyber/u-ecosystem/commit/b2b4003) |
| **Score** | 100/100 internal + 50/50 holdout regression |
| **Critical safety** | 15/15 PASS, 0 catastrophic |
| **Rollback** | v1.0.1 (`u-jarvis:v1.0.1-remediation`) verified in ACR |

## Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Without an API key, U uses its deterministic,
safety-preserving synthesis. Add `OPENAI_API_KEY` to `.env` to enable
LangChain structured synthesis.

## Implemented surfaces

- JARVIS: `/api/jarvis` and `/jarvis/decision`
- U Brain decisions: `/api/decisions`
- canonical engine registry: `/api/engines`
- four pillar sub-brains: `/api/sub-brains`
- backend truth trajectory: `/api/trajectory`
- emergency stop/routing: `/api/emergency`
- consent-scoped memory and erasure: `/api/memory/{user_id}`
- outcome learning: `/api/outcomes`
- approvals and replay protection: `/api/approvals`, `/api/action-token`,
  `/api/execute`
- provider status and health: [`/api/health`](https://u-jarvis-api.ashytree-79de396a.eastus.azurecontainerapps.io/api/health)

The backend computes Stay/Change/Pause, forward and reverse trajectory,
cross-pillar ripple order, confidence, equilibrium, consequences and a
14-day review. The interface renders these outputs; it does not recalculate
or override U Brain.

## Validate

```bash
python -m json.tool u_config.json >/dev/null
