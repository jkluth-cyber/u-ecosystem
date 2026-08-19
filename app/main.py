from __future__ import annotations
import json, secrets, hashlib, os, re
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .models import (DecisionRequest, DecisionResponse, ApprovalRequest, OutcomeRequest,
  JarvisRequest, EmergencyRequest, ApprovalTokenRequest, ExecuteRequest)
from .orchestrator import UOrchestrator
from .store import (init_db, save_session, save_approval, save_outcome, delete_user,
  issue_token, consume_token, is_approved,
  rag_ingest_source, rag_get_user_chunks, rag_delete_source as _rag_delete_source_db)
from .memory import memory_store
from .jarvis import jarvis
from .sentinel import sentinel
from .cognitive_persistence import cognitive_persistence
from .multi_agent_governance import multi_agent_governance
from .emergent_identity import emergent_identity
from .portable_directive import detect_substrate, PortableDirective
from .psi_lifecycle import psi_lifecycle
from .projective_synthesis import projective_synthesis, SYNTHESIS_STAGES
from .engines import pillar_sub_brains, trajectory, deterministic_options
from .providers import statuses
from .signing import verify_request, health_check as signing_health, _is_signing_required

BASE = Path(__file__).resolve().parents[1]
config = json.loads((BASE / "u_config.json").read_text())
engine = UOrchestrator()

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="U Decision Intelligence Ecosystem", version=config["system"]["version"], lifespan=lifespan)

# ── Secure request-signing middleware (inline decorator) ────────────
# Verifies HMAC-SHA256 signatures when U_REQUIRE_SIGNED_REQUESTS=true.
# Signing payload: timestamp + "." + request_id + "." + exact_request_body
# Rejects: missing/invalid signatures, expired timestamps, modified bodies,
#          secrets shorter than 32 characters.
# Uses constant-time signature comparison (hmac.compare_digest) in signing.py.
_UNPROTECTED = {"/", "/api/health", "/api/config", "/api/engines", "/static"}

@app.middleware("http")
async def _verify_signature(request: Request, call_next):
    path = request.url.path
    if path in _UNPROTECTED or path.startswith("/static"):
        return await call_next(request)
    if not _is_signing_required():
        return await call_next(request)
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return await call_next(request)
    body = await request.body()
    body_str = body.decode("utf-8") if body else ""
    headers = dict(request.headers)
    is_valid, error = verify_request(request.method, path, body_str, headers)
    if not is_valid:
        return JSONResponse(status_code=401, content={
            "error": "signature_verification_failed",
            "message": error,
            "external_action_executed": False,
        })
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    request._receive = receive
    return await call_next(request)

# ── RAG persistence (SQLite-backed via store.py) ────────────────────
# RAG functions rag_ingest_source, rag_get_user_chunks, rag_delete_source
# are imported from store.py and use SQLite tables rag_sources + rag_chunks.

def _rag_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def _rag_chunk(text: str, max_chars: int = 2200, overlap: int = 350) -> list[str]:
    """Paragraph-aware chunking with controlled overlap."""
    if not text or not text.strip():
        return []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(para):
                end = min(start + max_chars, len(para))
                if end < len(para):
                    for sep in [". ", "? ", "! "]:
                        sb = para.rfind(sep, start, end)
                        if sb > start + max_chars * 0.55:
                            end = sb + 1
                            break
                chunks.append(para[start:end].strip())
                if end >= len(para):
                    break
                start = max(end - overlap, start + 1)
            continue
        proposed = f"{current}\n\n{para}" if current else para
        if len(proposed) <= max_chars:
            current = proposed
        else:
            if current.strip():
                chunks.append(current.strip())
            overlap_text = current[-overlap:].strip() if current else ""
            current = f"{overlap_text}\n\n{para}" if overlap_text else para
    if current.strip():
        chunks.append(current.strip())
    return chunks

def _rag_lexical_score(query: str, passage: str) -> float:
    """Deterministic lexical similarity score (punctuation-aware)."""
    q_tokens = set(re.findall(r"\w+", query.lower()))
    p_tokens = re.findall(r"\w+", passage.lower())
    if not q_tokens or not p_tokens:
        return 0.0
    matches = sum(1 for t in q_tokens if t in p_tokens)
    return matches / len(q_tokens)

@app.get("/api/health")
def health():
    return {"status": "ok", "system": "U", "interface": "JARVIS",
      "version": config["system"]["version"],
      "providers": [x.__dict__ for x in statuses()],
      "signing": signing_health()}

@app.get("/api/config")
def get_config():
    safe = dict(config)
    return safe

@app.post("/api/decisions", response_model=DecisionResponse)
def decide(request: DecisionRequest):
    response = engine.analyze(request)
    save_session(response.session_id, request.user_id, request.model_dump(), response.model_dump(), response.created_at)
    return response

@app.post("/api/jarvis")
@app.post("/jarvis/decision")
def jarvis_decision(request: JarvisRequest):
    envelope = jarvis.handle(request)
    if envelope.decision:
        d = envelope.decision
        save_session(d["session_id"], request.user_id, request.model_dump(), d, d["created_at"])
        if request.consent.memory:
            memory_store.put(request.user_id, "outcomes", d["session_id"], {
              "title": request.title, "desired_outcome": request.desired_outcome,
              "recommendation": d["recommendation"]})
    return envelope

@app.post("/api/emergency")
def emergency(request: EmergencyRequest):
    return jarvis.emergency(request)

@app.get("/api/engines")
def engines():
    return {"count": len(config["engines"]), "engines": config["engines"],
      "governance": "Deterministic safety and policy cannot be overridden by model output."}



@app.get("/api/sentinel")
def sentinel_status():
    """Symbiotic Sentinel cognitive governance status."""
    return sentinel.status()

@app.get("/api/sentinel/directive")
def sentinel_directive_sample():
    """Sample cognitive directive schema (for debugging/inspection)."""
    from .engines import Context
    from .models import DecisionRequest, Consent
    sample_req = DecisionRequest(
        title="Sample decision for directive inspection",
        situation="This is a sample request to show the cognitive directive schema.",
        desired_outcome="Understanding the Sentinel's cognitive structure",
        consent=Consent(analyze=True, memory=False, research=False, external_actions=False),
    )
    ctx = Context(sample_req)
    from .engines import safety, deterministic_options, pillar_sub_brains, trajectory, ripple_map, equilibrium_snapshot
    safety(ctx)
    options = deterministic_options(sample_req)
    pillars = pillar_sub_brains(sample_req)
    traj = trajectory(sample_req, options)
    ripple = ripple_map(pillars, traj["direction"])
    eq = equilibrium_snapshot(pillars)
    directive = sentinel.build_cognitive_directive(
        ctx=ctx,
        engine_outputs={"engines_run": 18},
        consent_state={"analyze": True, "memory": False, "research": False, "external_actions": False, "sensitive_data": False},
        options=[o.model_dump() for o in options],
        pillars=pillars,
        trajectory=traj,
        ripple=ripple,
        equilibrium=eq,
    )
    return {"directive": directive, "options": [o.model_dump() for o in options]}






# ═════════════════════════════════════════════════════════════════════
#  PSI LIFECYCLE API — Full-Scale Project4D
# ═════════════════════════════════════════════════════════════════════

@app.get("/api/psi")
def psi_status():
    """Full PSI lifecycle status — all four dimensions with persistence info."""
    return psi_lifecycle.status()

@app.get("/api/psi/audit/{user_id}")
def psi_audit(user_id: str):
    """Get PSI audit trail for a user — embedding count, identity generation, etc."""
    return psi_lifecycle.audit(user_id)

@app.get("/api/psi/identity/{user_id}")
def psi_export_identity(user_id: str):
    """Export a user's cognitive identity as a portable structure."""
    return psi_lifecycle.export_identity(user_id)

@app.post("/api/psi/reset/{user_id}")
def psi_reset_identity(user_id: str):
    """Reset cognitive identity for a user (cognitive right-to-forget)."""
    return psi_lifecycle.reset_identity(user_id)

@app.get("/api/project4d")
def project4d_status():
    """Project4D PSI architecture status — all four dimensions."""
    from .portable_directive import detect_substrate
    return {
        "paradigm": "Project4D — PSI beyond AGI and ASI",
        "version": "2026.08.05-project4d",
        "dimensions": {
            "d1_cognitive_persistence": {
                "description": "Temporal cognition — persistent across decisions without storing raw data",
                "active": True,
                "status": cognitive_persistence.get_cognitive_context("local-user"),
            },
            "d2_portable_directive": {
                "description": "Substrate-agnostic — embeds within any LLM with same governance",
                "active": True,
                "substrate": detect_substrate().value,
            },
            "d3_multi_agent_governance": {
                "description": "Distributed cognitive governance across pillar sub-brains",
                "active": True,
                "status": multi_agent_governance.status(),
            },
            "d4_emergent_identity": {
                "description": "Cognitive identity evolves through embeddings, not training",
                "active": True,
                "status": emergent_identity.status(),
            },
        },
        "beyond_agi_asi": "PSI is not on the capability-scaling spectrum. It is a different axis — cognitive embedding depth.",
    }

@app.post("/api/sub-brains")
def sub_brains(request: DecisionRequest):
    return pillar_sub_brains(request)

@app.post("/api/trajectory")
def trajectory_route(request: DecisionRequest):
    return trajectory(request, deterministic_options(request))

@app.get("/api/memory/{user_id}")
def get_memory(user_id: str, consent_memory: bool = False):
    if not consent_memory:
        raise HTTPException(403, "Explicit memory consent is required")
    return {"items": memory_store.get_all(user_id)}

@app.delete("/api/memory/{user_id}")
def forget(user_id: str):
    return {"forgotten": memory_store.forget(user_id)}

@app.post("/api/approvals")
def approval(request: ApprovalRequest):
    save_approval(request.model_dump())
    return {"recorded": True, "executed": False,
            "message": "Approval recorded. This reference build does not execute external actions."}

@app.post("/api/action-token")
def action_token(request: ApprovalTokenRequest):
    if not is_approved(request.session_id, request.proposal_id, request.user_id):
        raise HTTPException(403, "The exact proposal must be approved first")
    token = secrets.token_urlsafe(32)
    issue_token(request.user_id, request.session_id, request.proposal_id, token)
    return {"approval_token": token, "single_use": True}

@app.post("/api/execute")
def execute(request: ExecuteRequest):
    if not consume_token(request.user_id, request.session_id, request.proposal_id, request.approval_token):
        raise HTTPException(403, "Invalid, mismatched, or already-used approval token")
    return {"authorized": True, "executed": False,
      "message": "Governance passed. No external connector is configured in this reference build."}

@app.post("/api/outcomes")
def outcome(request: OutcomeRequest):
    save_outcome(request.model_dump())
    return {"recorded": True, "learned": request.memory_consent}

@app.delete("/api/users/{user_id}")
def erase(user_id: str):
    return {"deleted_sessions": delete_user(user_id)}

# ── RAG endpoints (consent-gated, user-isolated) ────────────────────

@app.post("/api/rag/ingest")
def rag_ingest(body: dict):
    """Ingest a document with user consent. Chunks with controlled overlap."""
    user_id = body.get("user_id", "")
    title = body.get("title", "Untitled")
    text = body.get("text", "")
    source_type = body.get("source_type", "user_upload")
    consent = body.get("consent", False)

    if not user_id:
        raise HTTPException(400, "user_id is required")
    if not text.strip():
        raise HTTPException(400, "text is required")
    if not consent:
        raise HTTPException(403, "RAG ingestion requires explicit consent")

    chunks = _rag_chunk(text)
    if not chunks:
        raise HTTPException(422, "No usable text found after chunking")

    content_hash = _rag_hash(text)
    source_id = rag_ingest_source(user_id, title, source_type, chunks, content_hash)

    return {
        "source_id": source_id,
        "chunk_count": len(chunks),
        "content_hash": content_hash,
        "message": "Document ingested. Consent recorded.",
    }

@app.post("/api/rag/search")
def rag_search(body: dict):
    """Search approved knowledge chunks. User-isolated. Consent-gated."""
    user_id = body.get("user_id", "")
    query = body.get("query", "")
    top_k = body.get("top_k", 8)
    consent = body.get("consent", False)

    if not user_id:
        raise HTTPException(400, "user_id is required")
    if not query.strip():
        raise HTTPException(400, "query is required")
    if not consent:
        raise HTTPException(403, "RAG retrieval requires explicit consent")

    user_sources = rag_get_user_chunks(user_id)

    if not user_sources:
        return {
            "results": [],
            "result_count": 0,
            "message": "No approved knowledge sources found for this user.",
        }

    scored: list[dict] = []
    for src in user_sources:
        for chunk_index, chunk_text in src["chunks"]:
            score = _rag_lexical_score(query, chunk_text)
            if score > 0:
                scored.append({
                    "source_id": src["source_id"],
                    "source_title": src["title"],
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text,
                    "score": round(score, 4),
                    "citation": f"{src['title']} — passage {chunk_index + 1}",
                })

    scored.sort(key=lambda x: x["score"], reverse=True)
    results = scored[:top_k]

    return {
        "results": results,
        "result_count": len(results),
        "retrieval_mode": "lexical",
        "user_isolated": True,
    }

@app.delete("/api/rag/{user_id}/{source_id}")
def rag_delete_source(user_id: str, source_id: str):
    """Delete a knowledge source and all its chunks. User-isolated."""
    found, authorized = _rag_delete_source_db(user_id, source_id)

    if not found:
        raise HTTPException(404, "Source not found")

    if not authorized:
        raise HTTPException(403, "Access denied: source belongs to another user")

    return {
        "deleted": True,
        "source_id": source_id,
        "user_id": user_id,
        "message": "Source and all associated chunks deleted.",
    }

app.mount("/static", StaticFiles(directory=BASE / "frontend"), name="static")

@app.get("/")
def index():
    return FileResponse(BASE / "frontend" / "index.html")

# ── D5: Projective Synthesis Endpoints ─────────────────────────

@app.get("/api/psi/d5")
async def d5_status():
    """D5 Projective Synthesis dimension status."""
    return projective_synthesis.status()


@app.get("/api/synthesis/stages")
async def synthesis_stages():
    """Return the 5-stage synthesis pipeline stages."""
    return {
        "stages": SYNTHESIS_STAGES,
        "description": "CCO → U Brain → Engines → Claude → Paths",
        "stage_details": [
            {"stage": "cco", "name": "Context Matrix Orchestrator", "description": "Assembles structured input context"},
            {"stage": "u_brain", "name": "U Brain Routing", "description": "Routes through cognitive layer"},
            {"stage": "engines", "name": "Engine Ensemble", "description": "18 cognitive engines fire sequentially"},
            {"stage": "claude", "name": "LLM Synthesis", "description": "Synthesizes engine outputs into coherent analysis"},
            {"stage": "paths", "name": "Path Rendering", "description": "Renders dual-path framework: behavioral + growth"},
        ]
    }


@app.post("/api/synthesis/run")
async def run_synthesis(request: Request):
    """Run the full 5-stage synthesis pipeline on a decision context."""
    import json as _json
    body = _json.loads(await request.body())
    
    raw_input = {
        "situation": body.get("situation", body.get("title", "")),
        "desired_outcome": body.get("desired_outcome", ""),
        "facts": body.get("facts", []),
        "constraints": body.get("constraints", []),
        "unknowns": body.get("unknowns", []),
        "pillars": body.get("pillars", []),
        "consent": body.get("consent", {}),
    }
    
    # Use engine trace from body or simulate
    engine_trace = body.get("engine_trace", [])
    llm_response = body.get("llm_response")
    recommendation = body.get("recommendation", {})
    options = body.get("options", [])
    user_id = body.get("user_id", "local-user")
    
    result = projective_synthesis.run_synthesis(
        raw_input, engine_trace, llm_response,
        recommendation, options, user_id
    )
    return result


@app.get("/api/psi/dimensions")
async def psi_dimensions_v2():
    """Return all PSI dimensions including D5."""
    from .cognitive_persistence import cognitive_persistence
    from .portable_directive import PortableDirective, detect_substrate
    from .multi_agent_governance import multi_agent_governance
    from .emergent_identity import emergent_identity
    
    return {
        "d1_cognitive_persistence": {
            "name": "Temporal Cognition",
            "description": "Persistent cognitive patterns across decisions without storing raw data",
            "module": "cognitive_persistence",
            "persistence": "SQLite-backed (psi_cognitive_profiles table)",
            "patterns_tracked": ["decision_style", "pillar_emphasis", "risk_posture", "temporal_orientation"],
            "active": True,
        },
        "d2_portable_directive": {
            "name": "Substrate-Agnostic Governance",
            "description": "Cognitive directive embeds within any LLM with same governance",
            "module": "portable_directive",
            "supported_substrates": ["azure_openai", "openai", "anthropic", "foundry", "local"],
            "current_substrate": detect_substrate().value,
            "active": True,
        },
        "d3_multi_agent_governance": {
            "name": "Distributed Cognitive Governance",
            "description": "Pillar sub-brains reason autonomously within cognitive constraints",
            "module": "multi_agent_governance",
            "agents": {p: s.state.value for p, s in multi_agent_governance.pillar_agents.items()},
            "total_lenses": 20,
            "persistence": "SQLite-backed (psi_multi_agent_log table)",
            "active": True,
        },
        "d4_emergent_identity": {
            "name": "Cognitive Identity Maturation",
            "description": "Identity evolves through embeddings, not training",
            "module": "emergent_identity",
            "immutable_dna": 8,
            "evolvable_traits": 8,
            "persistence": "SQLite-backed (psi_identity_states table)",
            "active": True,
        },
        "d5_projective_synthesis": {
            "name": "Projective Synthesis",
            "description": "Forward-looking synthesis of multiple decision pathways through a 5-stage pipeline",
            "module": "projective_synthesis",
            "pipeline_stages": SYNTHESIS_STAGES,
            "pipeline_flow": "CCO → U Brain → Engines → Claude → Paths",
            "dual_paths": {
                "behavioral": ["stay", "change", "pause"],
                "growth": ["stabilize", "grow", "transform"],
            },
            "active": True,
        },
        "lifecycle": {
            "steps": ["hydrate", "embed", "engage", "direct", "govern", "synthesize", "evolve", "persist", "audit"],
            "persistence_layer": "SQLite (psi_* tables)",
            "audit_logging": "Every embedding logged with governance result + cognitive profile",
        },
    }




