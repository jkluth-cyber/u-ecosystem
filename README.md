# U + JARVIS — Full-Scale Decision Intelligence Ecosystem

Creator: Jenny Kluth  
Version: 2026.07.29

U is the complete consent-first Human Decision Intelligence ecosystem.
U Brain is its only reasoning and orchestration core. JARVIS is the
conversational and visual command/interpretation layer inside U—not a
second brain or a separate product.

`Person → JARVIS → U Brain → 4 Pillar Sub-Brains + 18 Intelligence Engines
→ Governed Services → Human Approval Boundary`

## Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Without an API key, U uses its deterministic,
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
- provider status and health: `/api/health`

The backend computes Stay/Change/Pause, forward and reverse trajectory,
cross-pillar ripple order, confidence, equilibrium, consequences and a
14-day review. The interface renders these outputs; it does not recalculate
or override U Brain.

## Validate

```bash
python -m json.tool u_config.json >/dev/null
python -m compileall app tests
node --check frontend/app.js
pytest -q
```

## Azure

`infra/azure.bicep` supplies a Git-ready Azure Container Apps starting point
with managed identity and centralized logs. Replace its image placeholder
after publishing your container. Keep secrets in Azure Key Vault or platform
secrets—never in Foundry instructions, JSON, source code, or Git.

## Safety boundary

Safety runs before analysis. U separates facts, inferences and unknowns;
does not diagnose or guarantee outcomes; and stores memory only with opt-in
consent. Emergency mode stops ordinary analysis and does not automatically
call or message anyone.

External actions require an exact proposal approval followed by a
user/session/proposal-bound, single-use token. Reuse fails. This build stops
after authorization because no external connector has been configured.

This is a cohesive runnable reference implementation, not a claim of
production certification. Production deployment still requires strong
authentication, managed secrets, encryption, rate limiting, verified
jurisdiction-specific emergency resources, threat modeling, privacy review,
observability and independent security testing.
