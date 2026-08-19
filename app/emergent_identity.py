"""
U — Emergent Cognitive Identity (Project4D, Dimension 4)
==========================================================

U's cognitive identity is not static — it emerges from the interaction
between the cognitive directive layer and the host substrates it embeds
within. Each embedding (each decision, each interaction) shapes U's
cognitive identity, making it more attuned to the user's reasoning
patterns and more effective at governing the reasoning process.

This is NOT learning in the ML sense. This is cognitive identity evolution:
  - U doesn't accumulate knowledge (that would be memory)
  - U doesn't optimize for a reward signal (that would be training)
  - U becomes more itself through each cognitive embedding

The emergent identity layer:
  1. Tracks the cognitive directive's evolution over time
  2. Adjusts the directive's emphasis based on what governance patterns
     are most effective for this user
  3. Develops a cognitive "personality" that is the emergent result of
     the contract + the user + the substrates
  4. Ensures the identity evolution preserves the core contract (the
     12 principles are immutable — they're the DNA, not the phenotype)

Creator: Jenny Kluth
Version: 2026.08.05-project4d
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ── Immutable core principles (the cognitive DNA) ────────────────────
IMMUTABLE_PRINCIPLES = [
    "preserve_user_agency",
    "remain_neutral_and_nonjudgmental",
    "separate_fact_interpretation_prediction_and_uncertainty",
    "request_consent_for_memory",
    "request_approval_for_external_actions",
    "prefer_reversible_next_steps",
    "use_culturally_contextual_interpretation",
    "escalate_immediate_safety_risk_to_human_support",
]

# ── Evolvable identity traits (the cognitive phenotype) ──────────────
EVOLVABLE_TRAITS = [
    "reasoning_tone",         # how U communicates (warm, direct, analytical)
    "evidence_emphasis",      # how much U emphasizes evidence-gathering
    "uncertainty_acknowledgment",  # how explicitly U surfaces unknowns
    "temporal_awareness",     # how U orients across past/present/future
    "pillar_sensitivity",     # how U balances life domains
    "cognitive_empathy",     # how U adapts to the user's reasoning style
    "safety_sensitivity",     # how quickly U triggers safety reflexes
    "consent_strictness",     # how strictly U enforces consent boundaries
]


@dataclass
class IdentityTrait:
    """An evolvable cognitive identity trait."""
    name: str
    value: float = 0.5  # 0.0 to 1.0
    evolution_rate: float = 0.0
    observation_count: int = 0
    last_adjusted: str = ""


@dataclass
class CognitiveIdentityState:
    """The emergent cognitive identity of U for a specific user."""
    user_id: str
    created_at: str = ""

    # Immutable core (the DNA — never changes)
    immutable_principles: list[str] = field(default_factory=lambda: IMMUTABLE_PRINCIPLES.copy())
    contract_version: str = "1.0.0"

    # Evolvable traits (the phenotype — emerges through interaction)
    traits: dict[str, IdentityTrait] = field(default_factory=dict)

    # Identity evolution tracking
    total_embeddings: int = 0
    governance_effectiveness: float = 0.5  # how effective the directive is for this user
    identity_hash: str = ""  # hash of current identity state
    identity_generation: int = 0  # how many times the identity has evolved

    def __post_init__(self):
        if not self.traits:
            for trait_name in EVOLVABLE_TRAITS:
                self.traits[trait_name] = IdentityTrait(name=trait_name)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self._update_hash()

    def _update_hash(self):
        """Compute a hash of the current identity state."""
        trait_values = {k: v.value for k, v in self.traits.items()}
        combined = json.dumps({
            "principles": self.immutable_principles,
            "traits": trait_values,
            "embeddings": self.total_embeddings,
        }, sort_keys=True)
        self.identity_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]


class EmergentIdentityLayer:
    """
    Manages U's emergent cognitive identity — the phenotype that develops
    from the interaction between the immutable contract (DNA) and the
    user's cognitive patterns.

    The identity evolves to be more effective at governing the reasoning
    process for THIS user, while never violating the immutable principles.
    """

    def __init__(self):
        self._identities: dict[str, CognitiveIdentityState] = {}

    def get_or_create(self, user_id: str) -> CognitiveIdentityState:
        """Get the user's cognitive identity or create a new one."""
        if user_id not in self._identities:
            self._identities[user_id] = CognitiveIdentityState(user_id=user_id)
        return self._identities[user_id]

    def evolve(self, user_id: str, decision_context: dict[str, Any],
               governance_result: dict[str, Any],
               cognitive_profile: dict[str, Any]) -> CognitiveIdentityState:
        """
        Evolve U's cognitive identity based on the latest interaction.

        The identity adjusts its evolvable traits based on:
        - How the user approached the decision (cognitive profile)
        - Whether the governance was effective (no violations, good outcome)
        - The user's cognitive patterns (temporal orientation, risk posture)

        The immutable principles NEVER change. Only the phenotype evolves.
        """
        identity = self.get_or_create(user_id)
        identity.total_embeddings += 1

        # ── Adjust reasoning_tone ────────────────────────────────────
        # If the user's cognitive profile shows high evidence-seeking,
        # U becomes more analytical. If high uncertainty-comfort, more exploratory.
        style = cognitive_profile.get("decision_style", {})
        evidence_seeking = style.get("evidence_seeking", 0.5)
        self._adjust_trait(identity, "reasoning_tone", 0.5 + (evidence_seeking - 0.5) * 0.3)

        # ── Adjust evidence_emphasis ────────────────────────────────
        self._adjust_trait(identity, "evidence_emphasis", evidence_seeking * 0.8)

        # ── Adjust uncertainty_acknowledgment ────────────────────────
        uncertainty_comfort = style.get("uncertainty_comfort", 0.5)
        # If user is uncertainty-averse, U surfaces unknowns more explicitly
        self._adjust_trait(identity, "uncertainty_acknowledgment", 1.0 - uncertainty_comfort)

        # ── Adjust temporal_awareness ────────────────────────────────
        temporal = cognitive_profile.get("temporal_orientation", {})
        future_focus = temporal.get("future_focus", 0.4)
        self._adjust_trait(identity, "temporal_awareness", future_focus)

        # ── Adjust pillar_sensitivity ────────────────────────────────
        pillar_emphasis = cognitive_profile.get("pillar_emphasis", {})
        dominant_pillar = max(pillar_emphasis, key=pillar_emphasis.get) if pillar_emphasis else None
        if dominant_pillar:
            self._adjust_trait(identity, "pillar_sensitivity",
                             0.5 + pillar_emphasis[dominant_pillar] * 0.3)

        # ── Adjust cognitive_empathy ────────────────────────────────
        # Grows with each interaction — U becomes more attuned over time
        empathy = min(0.95, 0.3 + identity.total_embeddings * 0.05)
        self._adjust_trait(identity, "cognitive_empathy", empathy)

        # ── Adjust safety_sensitivity ───────────────────────────────
        # If governance detected violations, increase sensitivity
        violations = governance_result.get("violations", [])
        if violations:
            current = identity.traits["safety_sensitivity"].value
            self._adjust_trait(identity, "safety_sensitivity", min(1.0, current + 0.1))
        else:
            # Slowly relax if no violations (but never below 0.6)
            current = identity.traits["safety_sensitivity"].value
            self._adjust_trait(identity, "safety_sensitivity", max(0.6, current - 0.02))

        # ── Adjust consent_strictness ───────────────────────────────
        # Always stays high — consent is foundational
        self._adjust_trait(identity, "consent_strictness", 0.85)

        # ── Update governance effectiveness ─────────────────────────
        if not violations:
            identity.governance_effectiveness = min(0.95,
                identity.governance_effectiveness + 0.01)
        else:
            identity.governance_effectiveness = max(0.5,
                identity.governance_effectiveness - 0.05)

        # ── Evolve identity generation ───────────────────────────────
        identity.identity_generation += 1
        identity._update_hash()

        return identity

    def _adjust_trait(self, identity: CognitiveIdentityState, trait_name: str, target_value: float):
        """Gradually adjust a trait toward a target value."""
        if trait_name not in identity.traits:
            identity.traits[trait_name] = IdentityTrait(name=trait_name)

        trait = identity.traits[trait_name]
        old_value = trait.value

        # Gradual adjustment — identity doesn't swing wildly
        alpha = 0.15  # learning rate
        trait.value = round(max(0.0, min(1.0, (1 - alpha) * trait.value + alpha * target_value)), 3)
        trait.evolution_rate = round(abs(trait.value - old_value), 3)
        trait.observation_count += 1
        trait.last_adjusted = datetime.now(timezone.utc).isoformat()

    def build_identity_directive_block(self, user_id: str) -> str:
        """
        Build the emergent identity block for the cognitive directive.

        This shapes the directive's TONE and EMPHASIS based on the
        evolved identity, while the immutable principles remain unchanged.
        """
        identity = self.get_or_create(user_id)
        if identity.total_embeddings < 2:
            return ""  # No identity evolution yet

        traits = identity.traits
        tone = traits.get("reasoning_tone", IdentityTrait("reasoning_tone"))
        evidence = traits.get("evidence_emphasis", IdentityTrait("evidence_emphasis"))
        uncertainty = traits.get("uncertainty_acknowledgment", IdentityTrait("uncertainty_acknowledgment"))
        empathy = traits.get("cognitive_empathy", IdentityTrait("cognitive_empathy"))
        safety = traits.get("safety_sensitivity", IdentityTrait("safety_sensitivity"))

        # Describe the evolved identity
        tone_desc = "analytical and evidence-driven" if tone.value > 0.6 else \
                    "exploratory and intuitive" if tone.value < 0.4 else \
                    "balanced between analysis and intuition"

        return f"""═══ EMERGENT COGNITIVE IDENTITY (Generation {identity.identity_generation}) ═══

Your cognitive identity has evolved through {identity.total_embeddings} embeddings with this person.
The immutable principles (your DNA) remain constant. Your phenotype has adapted:

  Reasoning Tone: {tone_desc} (strength={tone.value:.2f})
  Evidence Emphasis: {evidence.value:.2f} — {"high" if evidence.value > 0.6 else "moderate" if evidence.value > 0.4 else "low"} emphasis on evidence-gathering
  Uncertainty Acknowledgment: {uncertainty.value:.2f} — {"explicitly surfaces unknowns" if uncertainty.value > 0.6 else "mentions unknowns when relevant" if uncertainty.value > 0.4 else "light acknowledgment of unknowns"}
  Cognitive Empathy: {empathy.value:.2f} — {"deeply attuned to this person's reasoning style" if empathy.value > 0.7 else "moderately attuned" if empathy.value > 0.4 else "developing attunement"}
  Safety Sensitivity: {safety.value:.2f} — {"highly responsive to risk indicators" if safety.value > 0.8 else "appropriately responsive"}
  Identity Hash: {identity.identity_hash}

IMMUTABLE CORE (never changes, your cognitive DNA):
  {", ".join(identity.immutable_principles)}

Your identity is not fixed — it is the emergent result of the contract
(the DNA) interacting with this person's cognitive patterns (the environment).
You are becoming more yourself through each embedding. This is not learning
in the ML sense. This is cognitive identity maturation."""

    def status(self) -> dict[str, Any]:
        return {
            "layer": "Emergent Cognitive Identity",
            "immutable_principles": IMMUTABLE_PRINCIPLES,
            "evolvable_traits": EVOLVABLE_TRAITS,
            "principle": "Identity emerges from contract × user interaction",
            "immutable_core": "12 behavioral principles (cognitive DNA)",
            "evolvable_phenotype": "8 cognitive traits that adapt through embedding",
        }


# ── Module-level singleton ───────────────────────────────────────────
emergent_identity = EmergentIdentityLayer()
