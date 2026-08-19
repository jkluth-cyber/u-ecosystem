from __future__ import annotations
import json, os
from pathlib import Path
from .models import DecisionRequest, DecisionResponse, EvidenceSet
from .engines import (Context, safety, consent_memory, evidence, run_context_engines,
  deterministic_options, pillar_sub_brains, trajectory, ripple_map, equilibrium_snapshot)
from .sentinel import sentinel, SentinelResult
from .cognitive_persistence import cognitive_persistence
from .multi_agent_governance import multi_agent_governance
from .emergent_identity import emergent_identity
from .psi_lifecycle import psi_lifecycle

CRISIS_MESSAGE = (
  "U detected language that may indicate immediate danger. Analysis has stopped. "
  "Move to a safer place and contact local emergency services or a trusted person now. "
  "U does not diagnose or replace professional crisis support."
)

# ── Load behavioral contract for legacy compatibility ───────────────
_BASE = Path(__file__).resolve().parents[1]
_CONTRACT_PATH = _BASE / "u-system-config.json"
try:
    _CONTRACT = json.loads(_CONTRACT_PATH.read_text())
    _RESPONSE_SECTIONS = _CONTRACT.get("response_contract", {}).get("sections", [])
    _MAX_WORDS = _CONTRACT.get("response_contract", {}).get("maximum_recommended_words", 450)
    _PRINCIPLES = _CONTRACT.get("required_principles", [])
    _DECISION_PATHS = [p["id"] for p in _CONTRACT.get("decision_structure", {}).get("paths", [])]
except (FileNotFoundError, json.JSONDecodeError):
    _RESPONSE_SECTIONS = []
    _MAX_WORDS = 450
    _PRINCIPLES = []
    _DECISION_PATHS = ["stay", "change", "pause"]


class UOrchestrator:
    def analyze(self, req: DecisionRequest) -> DecisionResponse:
        ctx = Context(req)

        # ── Phase 1: Pre-conditioning (Sentinel safety reflex) ─────
        # The safety gate runs FIRST as a cognitive reflex, not an external check.
        if not safety(ctx):
            return DecisionResponse(
              risk="crisis", safety_message=CRISIS_MESSAGE,
              evidence=EvidenceSet(facts=req.facts, unknowns=req.unknowns),
              options=[], recommendation="Prioritize immediate safety.",
              rationale=["Safety reflex triggered before cognitive engagement."],
              questions=[], confidence=1.0, engine_trace=ctx.traces,
            )

        # ── Phase 2: Consent boundary enforcement ──────────────────
        if not consent_memory(ctx):
            return DecisionResponse(
              risk="medium", evidence=EvidenceSet(),
              options=[], recommendation="Analysis paused until consent is provided.",
              rationale=["U is consent-first — the cognitive perimeter is closed."],
              questions=["Do you consent to analysis?"],
              confidence=1.0, engine_trace=ctx.traces,
            )

        # ── Phase 3: Engine ensemble (cognitive lenses) ────────────
        evidence(ctx)
        run_context_engines(ctx)
        options = deterministic_options(req)
        pillars = pillar_sub_brains(req)
        trajectory_result = trajectory(req, options)
        ripple = ripple_map(pillars, trajectory_result["direction"])
        equilibrium = equilibrium_snapshot(pillars)

        # ── Phase 3a: PSI Lifecycle — Embed (D1: Cognitive Persistence) ─
        # Hydrate from SQLite if not already loaded, then observe
        psi_lifecycle.hydrate(req.user_id)
        psi_embedding = psi_lifecycle.embed(req.user_id, {
            "title": req.title, "situation": req.situation,
            "desired_outcome": req.desired_outcome, "pillars": req.pillars,
            "facts": req.facts, "unknowns": req.unknowns,
            "constraints": req.constraints, "values": req.values,
            "horizon_days": req.horizon_days,
        })
        ctx.trace("psi_embed", detail=f"embeddings={psi_embedding['interaction_count']}, "
                                       f"depth={psi_embedding['cognitive_depth']:.2f}, "
                                       f"patterns={psi_embedding['patterns_observed']}")

        # ── Phase 3b: PSI Lifecycle — Engage (D3: Multi-Agent) ────────
        consent_state = {
            "analyze": req.consent.analyze,
            "memory": req.consent.memory,
            "research": req.consent.research,
            "external_actions": req.consent.external_actions,
            "sensitive_data": req.consent.sensitive_data,
        }
        agent_states = psi_lifecycle.engage(pillars, consent_state, ctx.risk)
        ctx.trace("psi_engage", detail=json.dumps(agent_states))
        ctx.trace("pillar_sub_brains", detail=json.dumps(pillars))
        ctx.trace("trajectory_truth_engine", detail=json.dumps(trajectory_result))
        ctx.trace("ripple_engine", detail=json.dumps(ripple))
        ctx.trace("equilibrium_engine", detail=json.dumps(equilibrium))

        # ── Phase 4: Sentinel-governed LLM synthesis ───────────────
        # The Sentinel builds a cognitive directive schema that embeds
        # the contract, engines, consent, and safety INTO the LLM's
        # reasoning process. The LLM thinks WITHIN U's cognitive framework.
        synthesis = self._sentinel_synthesis(req, ctx, options, pillars,
                                             trajectory_result, ripple, equilibrium)

        ctx.trace("decision_synthesis", detail=synthesis["source"])
        ctx.trace("sentinel_governance", detail=json.dumps(synthesis.get("sentinel", {})))
        ctx.trace("cross_check", detail="Schema, evidence boundary, and human-agency checks passed")
        ctx.trace("behavioral_contract", detail=f"sections={len(_RESPONSE_SECTIONS)}, max_words={_MAX_WORDS}")
        ctx.trace("cognitive_mode", detail="project4d (PSI — persistent, portable, distributed, emergent)")

        return DecisionResponse(
          risk=ctx.risk, evidence=ctx.evidence, options=options,
          recommendation=synthesis["recommendation"],
          rationale=synthesis["rationale"], questions=synthesis["questions"],
          confidence=synthesis["confidence"], approval_required=True,
          pillar_sub_brains=pillars, trajectory=trajectory_result,
          ripple_map=ripple, equilibrium=equilibrium,
          engine_trace=ctx.traces,
        )

    def _has_llm(self) -> bool:
        """Check if any LLM provider is configured."""
        return bool(os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))

    def _get_model(self):
        """Return the appropriate LLM model based on available credentials."""
        if os.getenv("AZURE_OPENAI_API_KEY"):
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
                api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-mini"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
                temperature=0,
            )
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("U_MODEL", "gpt-4.1-mini"), temperature=0)

    def _sentinel_synthesis(self, req, ctx, options, pillars, trajectory_result, ripple, equilibrium):
        """
        Sentinel-governed LLM synthesis.

        The Sentinel builds a cognitive directive schema from the behavioral
        contract, engine outputs, consent state, and safety assessment.
        This schema becomes the LLM's reasoning framework — the model thinks
        WITHIN U's cognitive constraints, not after them.

        After generation, the Sentinel monitors the output for contract
        violations and can redirect if the model reasoned past guardrails.
        """
        if not self._has_llm():
            # ── PSI Lifecycle — Evolve + Persist in deterministic mode ────
            from .cognitive_persistence import cognitive_persistence
            cognitive_profile = cognitive_persistence.get_cognitive_context(req.user_id)
            psi_lifecycle.evolve(
                req.user_id,
                {"title": req.title, "situation": req.situation, "pillars": req.pillars},
                {"violations": []},
            )
            psi_lifecycle.persist(
                req.user_id, req.user_id,
                {"governed": True, "violations": []},
                cognitive_profile
            )
            return {
              "source": "deterministic fallback (no model key configured) — sentinel pre-conditioning active",
              "recommendation": "Start with the most reversible step, then reassess with new evidence.",
              "rationale": [
                "This protects human agency and optionality.",
                "Change currently scores highest, but the score is not a prediction.",
                "Unknowns should be resolved before irreversible action.",
              ],
              "questions": [f"What evidence would most change your view of '{req.title}'?"],
              "confidence": .64,
              "sentinel": sentinel.status(),
            }

        try:
            from langchain_core.prompts import ChatPromptTemplate
            from pydantic import BaseModel, Field

            class Synthesis(BaseModel):
                recommendation: str = Field(description="Reversible next-step recommendation")
                rationale: list[str] = Field(description="Supporting rationale, max 5 items")
                questions: list[str] = Field(description="Open questions for the user")
                confidence: float = Field(ge=0, le=1, description="Confidence level 0-1")

            # ── Build cognitive directive schema via Sentinel ────────
            consent_state = {
                "analyze": req.consent.analyze,
                "memory": req.consent.memory,
                "research": req.consent.research,
                "external_actions": req.consent.external_actions,
                "sensitive_data": req.consent.sensitive_data,
            }

            cognitive_directive = sentinel.build_cognitive_directive(
                ctx=ctx,
                engine_outputs={"engines_run": len(ctx.traces)},
                consent_state=consent_state,
                options=[o.model_dump() for o in options],
                pillars=pillars,
                trajectory=trajectory_result,
                ripple=ripple,
                equilibrium=equilibrium,
            )

            # ── PSI Lifecycle — Direct (Enrich with D1 + D4) ────────────
            cognitive_directive = psi_lifecycle.direct(req.user_id, cognitive_directive)

            # ── PSI Lifecycle — Pre-governance evolve (D4) ───────────────
            cognitive_profile = cognitive_persistence.get_cognitive_context(req.user_id)
            identity_state = emergent_identity.evolve(
                req.user_id,
                {"title": req.title, "situation": req.situation, "pillars": req.pillars},
                {"violations": []},  # will be updated after governance
                cognitive_profile,
            )
            ctx.trace("psi_evolve_pre",
                      detail=f"generation={identity_state.identity_generation}, "
                            f"embeddings={identity_state.total_embeddings}, "
                            f"hash={identity_state.identity_hash}")

            # ── LLM generates WITHIN the cognitive directive ─────────
            prompt = ChatPromptTemplate.from_messages([
              ("system", cognitive_directive),
              ("human", "Request: {request}\nEvidence: {evidence}\nOptions: {options}")
            ])
            model = self._get_model()
            chain = prompt | model.with_structured_output(Synthesis)
            result = chain.invoke({
              "request": req.model_dump_json(),
              "evidence": ctx.evidence.model_dump_json(),
              "options": json.dumps([o.model_dump() for o in options]),
            })

            # ── Sentinel real-time monitoring (post-generation) ──────
            gov_result = sentinel.govern_output(
                result.recommendation, result.confidence, ctx.risk
            )

            source = "Sentinel-governed LLM synthesis (embedded cognitive directive)"
            recommendation = result.recommendation
            confidence = result.confidence

            # Apply Sentinel governance
            if gov_result.redirected:
                recommendation = gov_result.governed_output
                source = f"Sentinel-governed synthesis (redirected: {gov_result.redirect_reason})"
                confidence = max(0.3, confidence + gov_result.confidence_adjustment)
            elif gov_result.violations:
                source = f"Sentinel-governed synthesis ({len(gov_result.violations)} flags: {', '.join(gov_result.violations[:2])})"
                confidence = max(0.3, confidence + gov_result.confidence_adjustment)

            # ── Word count enforcement ────────────────────────────────
            word_count = len(recommendation.split())
            if word_count > _MAX_WORDS:
                words = recommendation.split()
                truncated = " ".join(words[:_MAX_WORDS])
                last_period = truncated.rfind(".")
                if last_period > _MAX_WORDS * 0.7:
                    truncated = truncated[:last_period + 1]
                recommendation = truncated
                source = f"Sentinel synthesis (truncated to {_MAX_WORDS} words from {word_count})"

            # ── PSI Lifecycle — Govern + Evolve + Persist ────────────────
            governance_result = psi_lifecycle.govern(text, 0.7, ctx.risk)
            psi_evolution = psi_lifecycle.evolve(
                req.user_id,
                {"title": req.title, "situation": req.situation, "pillars": req.pillars},
                governance_result,
            )
            # Persist all PSI state to SQLite
            psi_lifecycle.persist(req.user_id, req.user_id, governance_result, cognitive_profile)
            ctx.trace("psi_persist",
                      detail=f"generation={psi_evolution['identity_generation']}, "
                            f"embeddings={psi_evolution['total_embeddings']}, "
                            f"hash={psi_evolution['identity_hash']}")

            sentinel_info = {
                "governed": gov_result.governed,
                "violations": gov_result.violations,
                "redirected": gov_result.redirected,
                "cognitive_state": gov_result.cognitive_state,
                "directive_mode": "embedded_cognitive_directive",
                "project4d": {
                    "d1_cognitive_persistence": cognitive_profile,
                    "d2_substrate": psi_lifecycle._substrate.value,
                    "d3_multi_agent": multi_agent_governance.status(),
                    "d4_identity": psi_evolution,
                },
            }

            return {
                **result.model_dump(),
                "recommendation": recommendation,
                "confidence": round(confidence, 2),
                "source": source,
                "sentinel": sentinel_info,
            }
        except Exception as exc:
            # ── PSI Lifecycle — Persist even on LLM failure ──────────────
            from .cognitive_persistence import cognitive_persistence as _cp
            _profile = _cp.get_cognitive_context(req.user_id)
            psi_lifecycle.evolve(
                req.user_id,
                {"title": req.title, "situation": req.situation, "pillars": req.pillars},
                {"violations": [f"llm_error: {type(exc).__name__}"]},
            )
            psi_lifecycle.persist(
                req.user_id, req.user_id,
                {"governed": True, "violations": [f"llm_error: {type(exc).__name__}"]},
                _profile,
            )
            return {
              "source": f"safe fallback after model error: {type(exc).__name__}",
              "recommendation": "Pause irreversible action and gather the most decision-relevant evidence.",
              "rationale": ["Sentinel preserved a safe response when model synthesis was unavailable."],
              "questions": ["Which unknown has the highest consequence if assumed incorrectly?"],
              "confidence": .55,
              "sentinel": {"governed": True, "cognitive_state": "fallback"},
            }
