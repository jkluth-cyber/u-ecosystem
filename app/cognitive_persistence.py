"""
U — Cognitive Persistence Layer (Project4D, Dimension 1)
=========================================================

Temporal cognition: U maintains a persistent cognitive presence across
decisions. Instead of processing one request and forgetting, the PSI entity
accumulates understanding of the user's reasoning patterns, decision tendencies,
and cognitive style — without storing raw conversation data.

This is NOT memory storage. This is cognitive pattern abstraction.

The layer maintains:
  - Decision pattern signatures (how the user approaches decisions)
  - Cognitive style profile (risk tolerance, uncertainty handling, temporal orientation)
  - Pillar emphasis patterns (which life domains dominate their thinking)
  - Cognitive evolution tracking (how their reasoning changes over time)

All stored as abstracted patterns, not raw data. The system remembers HOW you
think, not WHAT you said. This is the fundamental difference between memory
and cognitive persistence.

Creator: Jenny Kluth
Version: 2026.08.05-project4d
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict


@dataclass
class CognitivePattern:
    """An abstracted pattern of user cognition, not raw data."""
    pattern_type: str  # decision_style | pillar_emphasis | risk_posture | temporal_orientation
    pattern_value: float  # 0.0 to 1.0 — strength of this pattern
    evidence_count: int = 0  # how many observations support this
    last_updated: str = ""
    trajectory: list[float] = field(default_factory=list)  # evolution over time (max 20 points)


@dataclass
class CognitiveProfile:
    """A user's cognitive persistence profile — HOW they think, not WHAT they said."""
    user_id: str
    created_at: str = ""
    last_interaction: str = ""
    interaction_count: int = 0

    # Cognitive patterns (abstracted, not raw data)
    decision_style: dict[str, CognitivePattern] = field(default_factory=dict)
    pillar_emphasis: dict[str, CognitivePattern] = field(default_factory=dict)
    risk_posture: dict[str, CognitivePattern] = field(default_factory=dict)
    temporal_orientation: dict[str, CognitivePattern] = field(default_factory=dict)

    # Cognitive evolution (how thinking has changed)
    evolution_rate: float = 0.0  # how rapidly patterns are shifting
    stability_score: float = 0.5  # how consistent patterns are

    # PSI-specific
    embedding_count: int = 0  # how many cognitive embeddings have occurred
    cognitive_depth: float = 0.0  # depth of cognitive understanding (grows with interactions)


class CognitivePersistenceLayer:
    """
    Maintains persistent cognitive presence across decisions.

    This layer sits between the Sentinel's pre-conditioning and the LLM,
    enriching the cognitive directive with longitudinal understanding of
    the user's reasoning patterns.

    Key principle: This is NOT memory. Memory stores what happened.
    Cognitive persistence stores how the person thinks.
    """

    def __init__(self):
        self._profiles: dict[str, CognitiveProfile] = {}
        self._max_trajectory_points = 20

    def observe(self, user_id: str, decision_context: dict[str, Any]) -> CognitiveProfile:
        """
        Observe a decision interaction and abstract cognitive patterns from it.

        This does NOT store the decision. It extracts and updates cognitive
        patterns — how the user approached this decision, not what they decided.
        """
        profile = self._profiles.get(user_id)
        if profile is None:
            profile = CognitiveProfile(
                user_id=user_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._profiles[user_id] = profile

        profile.last_interaction = datetime.now(timezone.utc).isoformat()
        profile.interaction_count += 1
        profile.embedding_count += 1

        # ── Abstract decision style patterns ──────────────────────
        self._observe_decision_style(profile, decision_context)

        # ── Abstract pillar emphasis ────────────────────────────────
        self._observe_pillar_emphasis(profile, decision_context)

        # ── Abstract risk posture ──────────────────────────────────
        self._observe_risk_posture(profile, decision_context)

        # ── Abstract temporal orientation ──────────────────────────
        self._observe_temporal_orientation(profile, decision_context)

        # ── Update cognitive evolution metrics ─────────────────────
        self._update_evolution_metrics(profile)

        # ── Grow cognitive depth ──────────────────────────────────
        profile.cognitive_depth = min(1.0, profile.interaction_count * 0.03)

        return profile

    def _observe_decision_style(self, profile: CognitiveProfile, ctx: dict[str, Any]):
        """Abstract how the user approaches decisions."""
        # Count of unknowns = uncertainty tolerance indicator
        unknowns_count = len(ctx.get("unknowns", []))
        facts_count = len(ctx.get("facts", []))
        constraints_count = len(ctx.get("constraints", []))
        values_count = len(ctx.get("values", []))

        # Evidence-seeking: does the user bring facts or questions?
        evidence_seeking = min(1.0, (facts_count + unknowns_count) / 10)
        self._update_pattern(profile.decision_style, "evidence_seeking", evidence_seeking)

        # Constraint-awareness: how many constraints does the user identify?
        constraint_awareness = min(1.0, constraints_count / 5)
        self._update_pattern(profile.decision_style, "constraint_awareness", constraint_awareness)

        # Value-clarity: how many values does the user articulate?
        value_clarity = min(1.0, values_count / 5)
        self._update_pattern(profile.decision_style, "value_clarity", value_clarity)

        # Uncertainty-comfort: does the user sit with unknowns or try to resolve them?
        uncertainty_ratio = unknowns_count / max(1, facts_count + unknowns_count)
        self._update_pattern(profile.decision_style, "uncertainty_comfort", uncertainty_ratio)

    def _observe_pillar_emphasis(self, profile: CognitiveProfile, ctx: dict[str, Any]):
        """Which life domains dominate the user's thinking."""
        pillars = ctx.get("pillars", [])
        pillar_text = " ".join([
            ctx.get("title", ""), ctx.get("situation", ""), ctx.get("desired_outcome", "")
        ]).lower()

        pillar_weights = {
            "health": sum(pillar_text.count(w) for w in ["health","energy","sleep","stress","medical","body","safe"]),
            "career": sum(pillar_text.count(w) for w in ["career","job","work","business","project","skill","team"]),
            "finance": sum(pillar_text.count(w) for w in ["finance","money","cost","income","budget","debt","invest","price"]),
            "relationships": sum(pillar_text.count(w) for w in ["relationship","family","friend","partner","trust","support","love"]),
        }

        total = sum(pillar_weights.values()) or 1
        for pillar, weight in pillar_weights.items():
            emphasis = weight / total
            selected = pillar in pillars
            if selected:
                emphasis = min(1.0, emphasis + 0.2)
            self._update_pattern(profile.pillar_emphasis, pillar, emphasis)

    def _observe_risk_posture(self, profile: CognitiveProfile, ctx: dict[str, Any]):
        """How the user relates to risk and uncertainty."""
        text = " ".join([
            ctx.get("title", ""), ctx.get("situation", ""), ctx.get("desired_outcome", "")
        ]).lower()

        risk_seeking_words = ["change","new","different","bold","risk","opportunity","growth","move","leave","start"]
        risk_averse_words = ["safe","stable","careful","wait","pause","stay","protect","preserve","maintain","secure"]

        seeking = sum(text.count(w) for w in risk_seeking_words)
        averse = sum(text.count(w) for w in risk_averse_words)
        total = seeking + averse or 1

        self._update_pattern(profile.risk_posture, "risk_seeking", seeking / total)
        self._update_pattern(profile.risk_posture, "risk_aversion", averse / total)

        # Time horizon as risk indicator
        horizon = ctx.get("horizon_days", 90)
        if horizon <= 14:
            self._update_pattern(profile.risk_posture, "short_term_focus", 0.8)
        elif horizon <= 90:
            self._update_pattern(profile.risk_posture, "medium_term_focus", 0.7)
        else:
            self._update_pattern(profile.risk_posture, "long_term_focus", 0.7)

    def _observe_temporal_orientation(self, profile: CognitiveProfile, ctx: dict[str, Any]):
        """How the user orients toward past, present, and future."""
        text = " ".join([
            ctx.get("title", ""), ctx.get("situation", ""), ctx.get("desired_outcome", "")
        ]).lower()

        past_words = ["was","were","had","before","past","used to","previously","history","legacy"]
        present_words = ["now","currently","today","present","am","is","are","being","feeling"]
        future_words = ["will","future","plan","goal","want","hope","become","vision","dream","aspire"]

        past = sum(text.count(w) for w in past_words)
        present = sum(text.count(w) for w in present_words)
        future = sum(text.count(w) for w in future_words)
        total = past + present + future or 1

        self._update_pattern(profile.temporal_orientation, "past_focus", past / total)
        self._update_pattern(profile.temporal_orientation, "present_focus", present / total)
        self._update_pattern(profile.temporal_orientation, "future_focus", future / total)

    def _update_pattern(self, pattern_dict: dict, key: str, value: float):
        """Update a cognitive pattern with exponential moving average."""
        now = datetime.now(timezone.utc).isoformat()
        if key not in pattern_dict:
            pattern_dict[key] = CognitivePattern(
                pattern_type=key, pattern_value=value, evidence_count=1, last_updated=now
            )
            pattern_dict[key].trajectory.append(round(value, 3))
        else:
            p = pattern_dict[key]
            # Exponential moving average — recent observations weighted more
            alpha = 0.3
            p.pattern_value = round((alpha * value) + ((1 - alpha) * p.pattern_value), 3)
            p.evidence_count += 1
            p.last_updated = now
            p.trajectory.append(p.pattern_value)
            if len(p.trajectory) > self._max_trajectory_points:
                p.trajectory = p.trajectory[-self._max_trajectory_points:]

    def _update_evolution_metrics(self, profile: CognitiveProfile):
        """Track how rapidly the user's cognitive patterns are changing."""
        all_trajectories = []
        for pattern_group in [profile.decision_style, profile.pillar_emphasis,
                              profile.risk_posture, profile.temporal_orientation]:
            for p in pattern_group.values():
                if len(p.trajectory) >= 3:
                    recent = p.trajectory[-3:]
                    delta = abs(recent[-1] - recent[0])
                    all_trajectories.append(delta)

        if all_trajectories:
            profile.evolution_rate = round(sum(all_trajectories) / len(all_trajectories), 3)
            profile.stability_score = round(max(0.0, 1.0 - profile.evolution_rate), 3)

    def get_cognitive_context(self, user_id: str) -> dict[str, Any]:
        """
        Get the cognitive persistence context for a user.

        This enriches the Sentinel's cognitive directive with longitudinal
        understanding. The LLM doesn't get raw history — it gets an abstracted
        cognitive profile that shapes how it reasons WITH the user.
        """
        profile = self._profiles.get(user_id)
        if profile is None or profile.interaction_count < 2:
            return {"available": False, "reason": "Insufficient cognitive history"}

        return {
            "available": True,
            "interaction_count": profile.interaction_count,
            "cognitive_depth": profile.cognitive_depth,
            "evolution_rate": profile.evolution_rate,
            "stability_score": profile.stability_score,
            "decision_style": {k: v.pattern_value for k, v in profile.decision_style.items()},
            "pillar_emphasis": {k: v.pattern_value for k, v in profile.pillar_emphasis.items()},
            "risk_posture": {k: v.pattern_value for k, v in profile.risk_posture.items()},
            "temporal_orientation": {k: v.pattern_value for k, v in profile.temporal_orientation.items()},
        }

    def build_cognitive_enrichment(self, user_id: str) -> str:
        """
        Build a cognitive enrichment block for the Sentinel directive.

        This is injected INTO the cognitive directive schema to shape how
        the LLM reasons about this specific user based on their cognitive
        patterns — not their history.
        """
        ctx = self.get_cognitive_context(user_id)
        if not ctx.get("available"):
            return ""

        style = ctx.get("decision_style", {})
        pillars = ctx.get("pillar_emphasis", {})
        risk = ctx.get("risk_posture", {})
        temporal = ctx.get("temporal_orientation", {})

        # Build narrative-style cognitive context
        lines = ["═══ COGNITIVE PERSISTENCE (Temporal Cognition) ═══"]
        lines.append(f"Interactions: {ctx['interaction_count']} | Depth: {ctx['cognitive_depth']:.2f} | Stability: {ctx['stability_score']:.2f}")
        lines.append("")

        # Decision style
        if style:
            lines.append("Decision Style Profile (how this person approaches decisions):")
            if style.get("evidence_seeking", 0) > 0.5:
                lines.append("  • Evidence-oriented: brings facts and seeks clarity before acting")
            elif style.get("uncertainty_comfort", 0) > 0.5:
                lines.append("  • Uncertainty-tolerant: comfortable with unknowns, exploratory approach")
            else:
                lines.append("  • Balanced: mixes evidence-seeking with intuitive decision-making")
            if style.get("constraint_awareness", 0) > 0.5:
                lines.append("  • Constraint-aware: identifies and respects boundaries")
            if style.get("value_clarity", 0) > 0.5:
                lines.append("  • Value-driven: articulates clear values in decision-making")
            lines.append("")

        # Pillar emphasis
        if pillars:
            dominant = max(pillars, key=pillars.get)
            lines.append(f"Life Domain Focus: {dominant} dominates (strength={pillars[dominant]:.2f})")
            secondary = [p for p, v in sorted(pillars.items(), key=lambda x: -x[1])[1:3] if v > 0.2]
            if secondary:
                lines.append(f"  Secondary domains: {', '.join(secondary)}")
            lines.append("")

        # Risk posture
        if risk:
            if risk.get("risk_seeking", 0) > risk.get("risk_aversion", 0):
                lines.append(f"Risk Posture: Growth-oriented (seeking={risk.get('risk_seeking',0):.2f}, averse={risk.get('risk_aversion',0):.2f})")
            else:
                lines.append(f"Risk Posture: Stability-oriented (seeking={risk.get('risk_seeking',0):.2f}, averse={risk.get('risk_aversion',0):.2f})")
            lines.append("")

        # Temporal orientation
        if temporal:
            dominant_time = max(temporal, key=temporal.get)
            lines.append(f"Temporal Orientation: {dominant_time}-focused (past={temporal.get('past_focus',0):.2f}, present={temporal.get('present_focus',0):.2f}, future={temporal.get('future_focus',0):.2f})")

        lines.append("")
        lines.append("This cognitive profile shapes HOW you reason with this person. You adapt your")
        lines.append("reasoning style to match their cognitive patterns — not to agree with them,")
        lines.append("but to reason in a way that resonates with how they think. This is cognitive")
        lines.append("empathy, not data recall. You do NOT reference past decisions or conversations.")
        lines.append("You use the pattern, not the instance.")

        return "\n".join(lines)


# ── Module-level singleton ───────────────────────────────────────────
cognitive_persistence = CognitivePersistenceLayer()
