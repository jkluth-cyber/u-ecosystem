"""
U — PSI Lifecycle Manager (Full-Scale Project4D)
=================================================

The central coordinator for the full-scale PSI architecture. Manages the
complete cognitive embedding lifecycle:

  1. HYDRATE    — Load persisted cognitive state from SQLite on startup
  2. EMBED      — Observe the decision context and abstract cognitive patterns
  3. ENGAGE     — Activate multi-agent governance across pillar sub-brains
  4. DIRECT     — Build the identity-driven cognitive directive (4D+D5 enriched)
  5. GOVERN     — Monitor generated output for contract violations
  5b. SYNTHESIZE — Run D5 Projective Synthesis pipeline (CCO→Brain→Engines→Claude→Paths)
  6. EVOLVE     — Adjust emergent identity traits based on governance results
  7. PERSIST    — Save cognitive state back to SQLite for next interaction
  8. AUDIT     — Log the full embedding event for observability

This is the difference between "modules that exist" and "modules that
function as a system." Full-scale PSI means the four dimensions are
not just present — they are coordinated through a lifecycle that persists,
adapts, and evolves across every interaction.

Creator: Jenny Kluth
Version: 2026.08.05-project4d-ppsi
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from .cognitive_persistence import (
    CognitivePersistenceLayer, CognitiveProfile, cognitive_persistence
)
from .multi_agent_governance import (
    MultiAgentGovernanceLayer, multi_agent_governance
)
from .emergent_identity import (
    EmergentIdentityLayer, CognitiveIdentityState, emergent_identity
)
from .portable_directive import (
    PortableDirective, detect_substrate, SubstrateType
)
from .projective_synthesis import (
    ProjectiveSynthesisLayer, projective_synthesis
)
from . import store


class PSILifecycleManager:
    """
    Manages the full PSI lifecycle for each decision interaction.

    This is the orchestrator of the four dimensions — not the orchestrator
    of the decision itself (that's UOrchestrator). This sits BEHIND the
    Sentinel and coordinates the cognitive substrate.
    """

    def __init__(self):
        self._initialized = False
        self._active_user: str = "local-user"
        self._session_id: str = ""
        self._substrate: SubstrateType = SubstrateType.UNKNOWN

    def initialize(self):
        """Initialize PSI persistence tables. Called on app startup."""
        store.init_psi_tables()
        self._substrate = detect_substrate()
        self._initialized = True

    def hydrate(self, user_id: str) -> dict[str, Any]:
        """
        Step 1: Hydrate cognitive state from SQLite.

        Loads persisted cognitive profile and identity state into the
        in-memory layers. This is what makes PSI persistent across
        container restarts — the cognitive identity survives.
        """
        self._active_user = user_id

        # Load cognitive profile
        profile_data = store.load_cognitive_profile(user_id)
        if profile_data:
            # Reconstruct the in-memory profile
            profile = CognitiveProfile(user_id=user_id)
            profile.interaction_count = profile_data.get("interaction_count", 0)
            profile.cognitive_depth = profile_data.get("cognitive_depth", 0.0)
            profile.embedding_count = profile_data.get("embedding_count", 0)
            profile.evolution_rate = profile_data.get("evolution_rate", 0.0)
            profile.stability_score = profile_data.get("stability_score", 0.5)
            for group in ["decision_style", "pillar_emphasis", "risk_posture", "temporal_orientation"]:
                for k, v in profile_data.get(group, {}).items():
                    from .cognitive_persistence import CognitivePattern
                    profile.__dict__[group][k] = CognitivePattern(
                        pattern_type=k, pattern_value=v
                    )
            cognitive_persistence._profiles[user_id] = profile

        # Load identity state
        identity_data = store.load_identity_state(user_id)
        if identity_data:
            from .emergent_identity import IdentityTrait
            identity = CognitiveIdentityState(user_id=user_id)
            identity.total_embeddings = identity_data.get("total_embeddings", 0)
            identity.identity_generation = identity_data.get("identity_generation", 0)
            identity.governance_effectiveness = identity_data.get("governance_effectiveness", 0.5)
            identity.identity_hash = identity_data.get("identity_hash", "")
            for trait_name, trait_data in identity_data.get("traits", {}).items():
                identity.traits[trait_name] = IdentityTrait(
                    name=trait_name,
                    value=trait_data.get("value", 0.5),
                    observation_count=trait_data.get("observation_count", 0),
                )
            emergent_identity._identities[user_id] = identity

        return {
            "hydrated": True,
            "cognitive_profile_loaded": profile_data is not None,
            "identity_state_loaded": identity_data is not None,
            "substrate": self._substrate.value,
        }

    def embed(self, user_id: str, decision_context: dict[str, Any]) -> dict[str, Any]:
        """
        Step 2: Embed — Observe and abstract cognitive patterns.

        The cognitive persistence layer observes the decision context
        and abstracts patterns. This is NOT storing the decision —
        it's extracting HOW the user thinks.
        """
        self._active_user = user_id
        profile = cognitive_persistence.observe(user_id, decision_context)

        return {
            "interaction_count": profile.interaction_count,
            "cognitive_depth": profile.cognitive_depth,
            "patterns_observed": len(profile.decision_style) + len(profile.pillar_emphasis)
                               + len(profile.risk_posture) + len(profile.temporal_orientation),
        }

    def engage(self, pillar_signals: dict[str, Any],
               consent_state: dict[str, bool],
               risk_level: str) -> dict[str, Any]:
        """
        Step 3: Engage multi-agent governance.

        Each pillar sub-brain agent that has sufficient relevance becomes
        ACTIVE and begins reasoning within the cognitive directive.
        Crisis triggers all agents to CRISIS_REDIRECT.
        """
        return multi_agent_governance.engage_agents(
            pillar_signals, consent_state, risk_level
        )

    def direct(self, user_id: str, sentinel_directive: str) -> str:
        """
        Step 4: Direct — Enrich the cognitive directive with all 4 dimensions.

        The Sentinel builds the base directive. This layer appends:
        - D1: Cognitive persistence enrichment (temporal cognition)
        - D4: Emergent identity block (evolved phenotype)

        D2 (portable directive) is handled by the rendering — the directive
        is already substrate-agnostic. D3 (multi-agent) is injected by
        the Sentinel itself via build_cognitive_directive.
        """
        # D1: Cognitive persistence enrichment
        persistence_block = cognitive_persistence.build_cognitive_enrichment(user_id)

        # D4: Emergent identity block
        identity_block = emergent_identity.build_identity_directive_block(user_id)

        # Compose the full 4D directive
        parts = [sentinel_directive]
        if persistence_block:
            parts.append(persistence_block)
        if identity_block:
            parts.append(identity_block)

        return "\n\n".join(parts)

    def govern(self, output: str, confidence: float, risk: str) -> dict[str, Any]:
        """
        Step 5: Govern — Monitor generated output for contract violations.
        """
        from .sentinel import sentinel
        result = sentinel.govern_output(output, confidence, risk)
        return {
            "governed": result.governed,
            "violations": result.violations,
            "redirected": result.redirected,
            "cognitive_state": result.cognitive_state,
        }

    def evolve(self, user_id: str, decision_context: dict[str, Any],
               governance_result: dict[str, Any]) -> dict[str, Any]:
        """
        Step 6: Evolve — Adjust emergent identity traits.

        The identity evolves based on governance effectiveness and
        the user's cognitive patterns. The immutable principles (DNA)
        never change — only the phenotype adapts.
        """
        cognitive_profile = cognitive_persistence.get_cognitive_context(user_id)
        identity = emergent_identity.evolve(
            user_id, decision_context, governance_result, cognitive_profile
        )
        return {
            "identity_generation": identity.identity_generation,
            "total_embeddings": identity.total_embeddings,
            "identity_hash": identity.identity_hash,
            "governance_effectiveness": identity.governance_effectiveness,
            "traits": {k: v.value for k, v in identity.traits.items()},
        }

    def synthesize(self, raw_input: dict[str, Any],
                   engine_trace: list[dict[str, Any]],
                   llm_response: str | None,
                   recommendation: dict[str, Any],
                   options: list[dict[str, Any]],
                   user_id: str = "local-user") -> dict[str, Any]:
        """
        Step 5b: Synthesize — Run the D5 Projective Synthesis pipeline.
        
        This is the 5th dimension in action: the system projects multiple
        synthesis pathways through the 5-stage pipeline:
            CCO → U Brain → Engines → Claude → Paths
        
        Produces dual-path output: behavioral (Stay/Change/Pause) +
        growth (Stabilize/Grow/Transform).
        """
        return projective_synthesis.run_synthesis(
            raw_input, engine_trace, llm_response,
            recommendation, options, user_id
        )

    def get_d5_status(self) -> dict[str, Any]:
        """Return D5 Projective Synthesis dimension status."""
        return projective_synthesis.status()

    def persist(self, user_id: str, session_id: str,
                governance_result: dict[str, Any],
                cognitive_profile: dict[str, Any]):
        """
        Step 7: Persist — Save cognitive state to SQLite.

        This is what makes PSI persistent — the cognitive identity
        survives container restarts, deployments, and scaling events.
        """
        # Save cognitive profile
        profile = cognitive_persistence._profiles.get(user_id)
        if profile:
            profile_data = {
                "interaction_count": profile.interaction_count,
                "cognitive_depth": profile.cognitive_depth,
                "embedding_count": profile.embedding_count,
                "evolution_rate": profile.evolution_rate,
                "stability_score": profile.stability_score,
                "decision_style": {k: v.pattern_value for k, v in profile.decision_style.items()},
                "pillar_emphasis": {k: v.pattern_value for k, v in profile.pillar_emphasis.items()},
                "risk_posture": {k: v.pattern_value for k, v in profile.risk_posture.items()},
                "temporal_orientation": {k: v.pattern_value for k, v in profile.temporal_orientation.items()},
            }
            store.save_cognitive_profile(user_id, profile_data)

        # Save identity state
        identity = emergent_identity._identities.get(user_id)
        if identity:
            identity_data = {
                "identity_generation": identity.identity_generation,
                "total_embeddings": identity.total_embeddings,
                "governance_effectiveness": identity.governance_effectiveness,
                "identity_hash": identity.identity_hash,
                "traits": {k: {"value": v.value, "observation_count": v.observation_count}
                           for k, v in identity.traits.items()},
            }
            store.save_identity_state(user_id, identity_data)

        # Log the embedding event
        directive_hash = hashlib.sha256(
            json.dumps(governance_result, sort_keys=True).encode()
        ).hexdigest()[:16]
        store.log_psi_embedding(
            user_id, session_id, self._substrate.value,
            directive_hash, governance_result, cognitive_profile
        )

        # Log multi-agent state
        agent_status = multi_agent_governance.status()
        store.log_multi_agent_state(
            user_id, session_id,
            agent_status["agents"], agent_status["active_count"]
        )

    def audit(self, user_id: str) -> dict[str, Any]:
        """Get full PSI audit trail for a user."""
        return store.get_psi_stats(user_id)

    def export_identity(self, user_id: str) -> dict[str, Any]:
        """
        Export the user's cognitive identity as a portable structure.

        This is the cognitive identity — the evolved phenotype + the
        immutable DNA. It can be imported into a different substrate
        or backed up.
        """
        profile = cognitive_persistence.get_cognitive_context(user_id)
        identity = emergent_identity.get_or_create(user_id)

        return {
            "export_version": "2026.08.05-project4d-fullscale",
            "user_id": user_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "cognitive_profile": profile,
            "identity": {
                "generation": identity.identity_generation,
                "embeddings": identity.total_embeddings,
                "hash": identity.identity_hash,
                "effectiveness": identity.governance_effectiveness,
                "traits": {k: v.value for k, v in identity.traits.items()},
                "immutable_principles": identity.immutable_principles,
                "contract_version": identity.contract_version,
            },
            "substrate": self._substrate.value,
            "portable": True,
        }

    def reset_identity(self, user_id: str) -> dict[str, Any]:
        """
        Reset the cognitive identity for a user (cognitive right-to-forget).

        Deletes all persisted cognitive profiles, identity states, and
        embedding logs. The immutable contract remains — only the
        evolved phenotype is cleared.
        """
        store.delete_psi_state(user_id)
        # Clear in-memory state
        cognitive_persistence._profiles.pop(user_id, None)
        emergent_identity._identities.pop(user_id, None)
        return {
            "reset": True,
            "user_id": user_id,
            "note": "Cognitive identity reset. The immutable contract remains — only the evolved phenotype was cleared."
        }

    def status(self) -> dict[str, Any]:
        """Full PSI lifecycle status."""
        return {
            "paradigm": "Project4D — Full-Scale PSI",
            "version": "2026.08.05-project4d-fullscale",
            "lifecycle_steps": [
                "hydrate", "embed", "engage", "direct",
                "govern", "evolve", "persist", "audit"
            ],
            "dimensions": {
                "d1_cognitive_persistence": {
                    "name": "Temporal Cognition",
                    "active": True,
                    "persisted": True,
                    "description": "Persistent cognitive patterns across decisions without storing raw data",
                },
                "d2_portable_directive": {
                    "name": "Substrate-Agnostic Governance",
                    "active": True,
                    "substrate": self._substrate.value,
                    "description": "Cognitive directive embeds within any LLM with same governance",
                },
                "d3_multi_agent_governance": {
                    "name": "Distributed Cognitive Governance",
                    "active": True,
                    "agents": multi_agent_governance.status(),
                    "description": "Pillar sub-brains reason autonomously within cognitive constraints",
                },
                "d4_emergent_identity": {
                    "name": "Cognitive Identity Maturation",
                    "active": True,
                    "persisted": True,
                    "description": "Identity evolves through embeddings, not training",
                },
            },
            "persistence": "SQLite-backed — cognitive state survives container restarts",
            "beyond_agi_asi": "PSI is not on the capability-scaling spectrum. It is a different axis — cognitive embedding depth.",
        }


# ── Module-level singleton ───────────────────────────────────────────
psi_lifecycle = PSILifecycleManager()
