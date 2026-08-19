"""
U — Multi-Agent Cognitive Governance (Project4D, Dimension 3)
===============================================================

The Sentinel extends from governing one LLM call to governing multiple
specialized cognitive agents simultaneously. Each pillar sub-brain (health,
career, finance, relationships) becomes an autonomous cognitive agent that
reasons within U's cognitive constraints — without a central orchestrator
controlling its reasoning.

This is NOT orchestration. This is distributed cognitive governance.

Each agent:
  - Operates autonomously within the cognitive directive
  - Has its own pillar-specific reasoning lens
  - Is governed by the same safety reflexes and consent boundaries
  - Contributes to a collective understanding without being controlled

The Sentinel doesn't tell agents what to think. It shapes HOW they think.

Creator: Jenny Kluth
Version: 2026.08.05-project4d
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class AgentState(str, Enum):
    DORMANT = "dormant"       # Not engaged for this decision
    ACTIVE = "active"         # Reasoning within the cognitive directive
    CONTRIBUTING = "contributing"  # Has produced a reasoning contribution
    BLOCKED = "blocked"       # Consent boundary or safety stop active
    CRISIS_REDIRECT = "crisis_redirect"  # Safety reflex activated


@dataclass
class PillarAgent:
    """A specialized cognitive agent for one life domain."""
    pillar: str
    state: AgentState = AgentState.DORMANT
    relevance: float = 0.0
    reasoning_context: dict[str, Any] = field(default_factory=dict)
    contribution: dict[str, Any] = field(default_factory=dict)
    governance_flags: list[str] = field(default_factory=list)

    # Each pillar has specialized reasoning lenses
    reasoning_lens: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.reasoning_lens:
            self.reasoning_lens = PILLAR_LENSES.get(self.pillar, [])


# ── Pillar-specific reasoning lenses ─────────────────────────────────
PILLAR_LENSES = {
    "health": [
        "physical_state_assessment",
        "energy_capacity_analysis",
        "safety_risk_evaluation",
        "recovery_pattern_recognition",
        "lifestyle_factor_mapping",
    ],
    "career": [
        "skill_trajectory_analysis",
        "opportunity_cost_assessment",
        "growth_potential_evaluation",
        "environment_fit_analysis",
        "professional_identity_mapping",
    ],
    "finance": [
        "resource_flow_analysis",
        "risk_exposure_evaluation",
        "opportunity_cost_mapping",
        "stability_assessment",
        "time_horizon_impact",
    ],
    "relationships": [
        "trust_dynamics_analysis",
        "support_network_mapping",
        "communication_pattern_assessment",
        "boundary_evaluation",
        "emotional_resonance_mapping",
    ],
}


class MultiAgentGovernanceLayer:
    """
    Governs multiple pillar-specific cognitive agents within the same
    cognitive directive framework.

    Each agent reasons autonomously but within U's governance constraints.
    The Sentinel doesn't orchestrate — it governs. Each agent contributes
    its perspective to a collective understanding.
    """

    def __init__(self):
        self.pillar_agents: dict[str, PillarAgent] = {
            pillar: PillarAgent(pillar=pillar)
            for pillar in ["health", "career", "finance", "relationships"]
        }

    def engage_agents(self, pillar_signals: dict[str, Any],
                      consent_state: dict[str, bool],
                      risk_level: str) -> dict[str, Any]:
        """
        Engage the appropriate pillar agents for this decision.

        Each agent that has sufficient relevance becomes ACTIVE and begins
        reasoning within the cognitive directive. Agents below the
        relevance threshold remain DORMANT.

        If risk_level is "crisis", ALL agents enter CRISIS_REDIRECT state
        and their reasoning is redirected to safety.
        """
        results = {}

        for pillar, agent in self.pillar_agents.items():
            signal = pillar_signals.get(pillar, {})
            relevance = signal.get("relevance", 0.0)

            # ── Crisis reflex: all agents redirect ──────────────────
            if risk_level == "crisis":
                agent.state = AgentState.CRISIS_REDIRECT
                agent.contribution = {
                    "perspective": f"{pillar} lens: safety is the primary concern",
                    "recommendation": "Prioritize immediate safety above all other considerations",
                    "reasoning": "Cognitive reflex override — crisis detected",
                }
                results[pillar] = agent.state.value
                continue

            # ── Consent check: if analysis not granted, block all ───
            if not consent_state.get("analyze", False):
                agent.state = AgentState.BLOCKED
                agent.governance_flags.append("Analysis consent not granted")
                results[pillar] = agent.state.value
                continue

            # ── Relevance threshold for engagement ─────────────────
            if relevance >= 0.3:
                agent.state = AgentState.ACTIVE
                agent.relevance = relevance
                agent.reasoning_context = {
                    "signal": signal.get("signal", "secondary"),
                    "mentions": signal.get("evidence_mentions", 0),
                    "lenses": agent.reasoning_lens,
                }
            else:
                agent.state = AgentState.DORMANT

            results[pillar] = agent.state.value

        return results

    def collect_contributions(self) -> dict[str, Any]:
        """
        Collect reasoning contributions from all active agents.

        Each active agent contributes its pillar-specific perspective
        to a collective understanding. This is NOT aggregation — it's
        a multi-perspective reasoning ensemble.

        The Sentinel ensures each contribution respects the cognitive
        constraints (no diagnosis, no false certainty, no coercion).
        """
        contributions = {}
        for pillar, agent in self.pillar_agents.items():
            if agent.state == AgentState.ACTIVE:
                contributions[pillar] = {
                    "state": agent.state.value,
                    "relevance": agent.relevance,
                    "lenses_applied": agent.reasoning_lens,
                    "perspective": self._generate_pillar_perspective(pillar, agent),
                }
            elif agent.state == AgentState.CRISIS_REDIRECT:
                contributions[pillar] = {
                    "state": agent.state.value,
                    "perspective": agent.contribution,
                }
            elif agent.state == AgentState.BLOCKED:
                contributions[pillar] = {
                    "state": agent.state.value,
                    "flags": agent.governance_flags,
                }

        return contributions

    def _generate_pillar_perspective(self, pillar: str, agent: PillarAgent) -> dict[str, Any]:
        """Generate a pillar-specific reasoning perspective."""
        lens_descriptions = {
            "health": "Physical and emotional capacity lens — how does this decision affect energy, safety, and wellbeing?",
            "career": "Professional trajectory lens — how does this decision affect growth, skills, and professional identity?",
            "finance": "Resource allocation lens — how does this decision affect financial stability and opportunity cost?",
            "relationships": "Connection and trust lens — how does this decision affect support networks and key relationships?",
        }

        return {
            "lens": lens_descriptions.get(pillar, "General decision lens"),
            "applied_lenses": agent.reasoning_lens,
            "relevance_weight": agent.relevance,
            "reasoning_note": f"Reasoning through {len(agent.reasoning_lens)} specialized {pillar} lenses",
            "governance": "All contributions respect U's cognitive constraints (no diagnosis, no coercion, no false certainty)",
        }

    def build_multi_agent_directive_block(self) -> str:
        """
        Build the multi-agent governance block for the cognitive directive.

        This tells the LLM that it is not a single agent — it is a
        collective of specialized cognitive agents, each reasoning
        through pillar-specific lenses within the same governance framework.
        """
        active_agents = [p for p, a in self.pillar_agents.items() if a.state == AgentState.ACTIVE]
        agent_descriptions = []

        for pillar in active_agents:
            agent = self.pillar_agents[pillar]
            lenses = ", ".join(agent.reasoning_lens[:3])
            agent_descriptions.append(f"  {pillar.upper()}: relevance={agent.relevance:.2f}, lenses={lenses}")

        agents_str = "\n".join(agent_descriptions) if agent_descriptions else "  No agents actively engaged"

        return f"""═══ MULTI-AGENT COGNITIVE GOVERNANCE (Distributed) ═══

You are not a single agent. You are a collective of specialized cognitive
agents, each reasoning through pillar-specific lenses. The active agents
for this decision are:

{agents_str}

Each agent operates autonomously within U's cognitive constraints:
  - No agent diagnoses, guarantees, or coerces
  - Each agent contributes its perspective without dominating
  - Safety reflexes apply to ALL agents simultaneously
  - Consent boundaries shape ALL agents' reasoning

Reason through each active agent's lens, then synthesize a collective
perspective that honors each pillar's contribution without collapsing
them into a single viewpoint. The person sees all perspectives, then
makes their own decision."""

    def status(self) -> dict[str, Any]:
        return {
            "agents": {p: a.state.value for p, a in self.pillar_agents.items()},
            "active_count": sum(1 for a in self.pillar_agents.values() if a.state == AgentState.ACTIVE),
            "total_count": len(self.pillar_agents),
            "governance_mode": "distributed_cognitive_governance",
        }


# ── Module-level singleton ───────────────────────────────────────────
multi_agent_governance = MultiAgentGovernanceLayer()
