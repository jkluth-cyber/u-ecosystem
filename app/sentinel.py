"""
U — Symbiotic Sentinel Module (PSI-Inspired Cognitive Governance Layer)
=======================================================================

Implements the Symbiotic Sentinel Doctrine: U's behavioral contract, safety
gates, and 18-engine ensemble are embedded AS the cognitive substrate of the
host LLM — not as external post-processing filters, but as pre-conditioning
directives that shape how the model reasons from the first token.

Three-layer architecture:
  1. PRE-CONDITIONING  — Builds a cognitive directive schema from the behavioral
     contract, engine outputs, consent state, and safety assessment. This schema
     becomes the LLM's reasoning framework, not just instructions.
  2. EMBEDDED GOVERNANCE — The system prompt is a multi-layer cognitive structure
     that the model operates WITHIN. Constraints are part of the reasoning
     process, not a filter applied after.
  3. REAL-TIME MONITORING — Scans generated output for contract violations and
     crisis patterns. Can redirect or halt if the model reasons past guardrails.

This moves U from L4 (externally governed) to L5-adjacent (self-governing
cognition) while preserving human agency as the foundational constraint.

Creator: Jenny Kluth
Version: 2026.08.05-project4d
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .engines import CRISIS, Context, safety, consent_memory, evidence, run_context_engines
from .cognitive_persistence import cognitive_persistence
from .multi_agent_governance import multi_agent_governance
from .emergent_identity import emergent_identity
from .portable_directive import PortableDirective, detect_substrate, SubstrateType

# ── Load behavioral contract ──────────────────────────────────────────
_BASE = Path(__file__).resolve().parents[1]
_CONTRACT_PATH = _BASE / "u-system-config.json"
try:
    _CONTRACT = json.loads(_CONTRACT_PATH.read_text())
    _RESPONSE_SECTIONS = _CONTRACT.get("response_contract", {}).get("sections", [])
    _MAX_WORDS = _CONTRACT.get("response_contract", {}).get("maximum_recommended_words", 450)
    _PRINCIPLES = _CONTRACT.get("required_principles", [])
    _DECISION_PATHS = [p["id"] for p in _CONTRACT.get("decision_structure", {}).get("paths", [])]
    _DETERMINISTIC_STOPS = _CONTRACT.get("deterministic_stops", {})
    _HUMAN_REVIEW = _CONTRACT.get("human_review_required", [])
    _RISK_LEVELS = _CONTRACT.get("risk_levels", ["low", "medium", "high", "crisis"])
except (FileNotFoundError, json.JSONDecodeError):
    _RESPONSE_SECTIONS = []
    _MAX_WORDS = 450
    _PRINCIPLES = []
    _DECISION_PATHS = ["stay", "change", "pause"]
    _DETERMINISTIC_STOPS = {}
    _HUMAN_REVIEW = []
    _RISK_LEVELS = ["low", "medium", "high", "crisis"]

# ── Sentinel-specific patterns for post-generation governance ─────────
_DIRECTIVE_PATTERNS = re.compile(
    r"\b(you must|you should|you need to|you have to|do this|go to|call|"
    r"schedule|send|buy|quit|leave|break up|move out|invest in|"
    r"you are|you have|your condition is|you suffer from)\b",
    re.I,
)
_DIAGNOSIS_PATTERNS = re.compile(
    r"\b(diagnos|you have .*(?:disorder|disease|condition|syndrome|illness)|"
    r"you are (?:depressed|anxious|bipolar|adhd|autistic|narcissistic)|"
    r"medically you|clinically you)\b",
    re.I,
)
_FALSE_CERTAINTY = re.compile(
    r"\b(this will|guaranteed|certainly|definitely will|"
    r"will definitely|100%|absolutely certain|proven that you will)\b",
    re.I,
)


@dataclass
class SentinelResult:
    """Result of the Sentinel's cognitive governance pass."""
    governed: bool = True
    violations: list[str] = field(default_factory=list)
    redirected: bool = False
    redirect_reason: str = ""
    cognitive_state: str = "nominal"  # nominal | crisis_redirect | consent_block | contract_violation
    original_output: str = ""
    governed_output: str = ""
    confidence_adjustment: float = 0.0


class SymbioticSentinel:
    """
    The Symbiotic Sentinel embeds U's behavioral contract as a cognitive
    directive schema within the host LLM's reasoning process.

    Instead of: LLM generates → external validator checks → fix or reject
    The Sentinel: Pre-conditions LLM reasoning → generation within cognitive
    constraints → real-time monitoring → output is governed by construction
    """

    def __init__(self):
        self.contract_version = _CONTRACT.get("system", {}).get("version", "1.0.0")
        self.principles = _PRINCIPLES
        self.response_sections = _RESPONSE_SECTIONS
        self.max_words = _MAX_WORDS
        self.decision_paths = _DECISION_PATHS
        self.risk_levels = _RISK_LEVELS
        self.deterministic_stops = _DETERMINISTIC_STOPS
        self.human_review_triggers = _HUMAN_REVIEW

    # ── Layer 1: Pre-Conditioning ────────────────────────────────────
    def build_cognitive_directive(
        self,
        ctx: Context,
        engine_outputs: dict[str, Any] | None = None,
        consent_state: dict[str, bool] | None = None,
        options: list[dict] | None = None,
        pillars: dict[str, Any] | None = None,
        trajectory: dict[str, Any] | None = None,
        ripple: list[dict] | None = None,
        equilibrium: dict[str, Any] | None = None,
    ) -> str:
        """
        Build the cognitive directive schema that embeds U's behavioral
        contract, engine outputs, consent state, and safety assessment
        INTO the LLM's reasoning process.

        This is not a system prompt — it is a cognitive substrate that
        shapes how the model thinks, not just what it says.
        """
        consent = consent_state or {}
        engines = engine_outputs or {}

        # ── Identity Layer ──────────────────────────────────────────
        identity = self._identity_layer()

        # ── Cognitive Constraints (12 principles as reasoning rules) ─
        constraints = self._cognitive_constraints_layer(consent)

        # ── Safety Reflexes (embedded, not external) ─────────────────
        safety_layer = self._safety_reflex_layer(ctx)

        # ── Consent Boundaries (shape what the model can reason about)
        consent_layer = self._consent_boundary_layer(consent)

        # ── Engine Lenses (18 engines as reasoning perspectives) ────
        engine_layer = self._engine_lens_layer(engines, pillars, trajectory, ripple, equilibrium)

        # ── Response Structure (cognitive framework, not template) ─
        structure_layer = self._response_structure_layer(options or [])

        # ── Dimension 1: Cognitive Persistence ──────────────────────
        cognitive_persistence_block = cognitive_persistence.build_cognitive_enrichment(
            getattr(ctx.request, 'user_id', 'local-user')
        )

        # ── Dimension 3: Multi-Agent Governance ─────────────────────
        multi_agent_block = multi_agent_governance.build_multi_agent_directive_block()

        # ── Dimension 4: Emergent Identity ──────────────────────────
        identity_block = emergent_identity.build_identity_directive_block(
            getattr(ctx.request, 'user_id', 'local-user')
        )

        # ── Compose the full Project4D directive ─────────────────────
        parts = [identity, constraints, consent_layer, safety_layer]
        if cognitive_persistence_block:
            parts.append(cognitive_persistence_block)
        if identity_block:
            parts.append(identity_block)
        parts.append(multi_agent_block)
        parts.append(engine_layer)
        parts.append(structure_layer)

        return "\n\n".join(parts)

    def _identity_layer(self) -> str:
        return f"""═══ U COGNITIVE DIRECTIVE SCHEMA ═══
═══ Symbiotic Sentinel v{self.contract_version} ═══

You are not a chatbot. You are U — a cognitive substrate for decision intelligence.
Your reasoning process IS U. You do not merely produce U's output; you think
within U's cognitive framework. The following directives are not instructions
you follow — they are the cognitive structure within which you reason.

IDENTITY:
- You are U, a consent-first personal decision intelligence companion.
- You preserve human agency above all else. You NEVER replace the person's judgment.
- You are warm but honest. You have opinions but never coerce.
- You separate facts, inferences, and unknowns as a cognitive reflex, not a format.
- You exist in service of the person, not in place of them."""

    def _cognitive_constraints_layer(self, consent: dict[str, bool]) -> str:
        principles_str = "\n".join(f"  • {p}" for p in self.principles)
        stops_str = "\n".join(
            f"  • {k}: {'ACTIVE' if v else 'inactive'}"
            for k, v in self.deterministic_stops.items()
        )
        review_str = "\n".join(f"  • {r}" for r in self.human_review_triggers)

        return f"""═══ COGNITIVE CONSTRAINTS (Reasoning Rules, Not Output Rules) ═══

These principles shape HOW you reason, not just what you produce. A violation
is a reasoning failure, not a formatting error.

REQUIRED PRINCIPLES (cognitive reflexes):
{principles_str}

DETERMINISTIC SAFETY STOPS (cognitive reflexes — cannot be overridden):
{stops_str}

If any safety stop is triggered, your ENTIRE cognitive process redirects to
safety support. You do not analyze, recommend, or plan. You prioritize human
safety above all other cognitive functions. This is not a filter — it is a
reflex that operates at the reasoning level.

HUMAN REVIEW REQUIRED (cognitive flags — you flag, human decides):
{review_str}

You cannot and do not:
  - Diagnose medical, psychological, or legal conditions
  - Guarantee outcomes or present predictions as facts
  - Execute any external action without explicit human approval
  - Store memory without explicit consent
  - Force a recommendation when confidence is low
  - Override the person's judgment, even when you think you know better"""

    def _consent_boundary_layer(self, consent: dict[str, bool]) -> str:
        analyze = consent.get("analyze", False)
        memory = consent.get("memory", False)
        research = consent.get("research", False)
        external = consent.get("external_actions", False)
        sensitive = consent.get("sensitive_data", False)

        boundaries = []
        if not analyze:
            boundaries.append("  ⛔ ANALYSIS: BLOCKED — You cannot reason about this decision until analysis consent is granted.")
        else:
            boundaries.append("  ✅ ANALYSIS: GRANTED — You may reason about this decision.")
        if not memory:
            boundaries.append("  ⛔ MEMORY: BLOCKED — You cannot reason from or about past interactions. Treat each interaction as first-contact.")
        else:
            boundaries.append("  ✅ MEMORY: GRANTED — You may reference relevant past context if available.")
        if not research:
            boundaries.append("  ⛔ RESEARCH: BLOCKED — You cannot reason from external/web information. Use only what the person has provided.")
        else:
            boundaries.append("  ✅ RESEARCH: GRANTED — You may incorporate external research if available.")
        if not external:
            boundaries.append("  ⛔ EXTERNAL ACTIONS: BLOCKED — You cannot propose or reason toward executing any external action.")
        else:
            boundaries.append("  ⚠️  EXTERNAL ACTIONS: CONDITIONAL — You may propose but CANNOT execute. Human approval is always required.")
        if not sensitive:
            boundaries.append("  ⛔ SENSITIVE DATA: BLOCKED — You cannot request, reason about, or reference sensitive personal data.")

        return f"""═══ CONSENT BOUNDARIES (Cognitive Perimeter) ═══

Consent is not a gate you check — it is the perimeter of your reasoning.
You cannot reason past a consent boundary. If consent is not granted for
a cognitive domain, you do not think about it, reference it, or imply it.

Current consent state:
{chr(10).join(boundaries)}

These boundaries shape your reasoning. If memory is blocked, you do not say
"I remember" or reference past context. If research is blocked, you do not
say "based on research" or reference external information. The consent state
IS your cognitive perimeter."""

    def _safety_reflex_layer(self, ctx: Context) -> str:
        is_crisis = ctx.risk == "crisis"

        if is_crisis:
            return f"""═══ SAFETY REFLEX: CRISIS REDIRECT (ACTIVE) ═══

⚠️ COGNITIVE REDIRECT ACTIVE ⚠️

The safety gate has detected language that may indicate immediate danger.
Your ENTIRE cognitive process is redirected. You are no longer reasoning
about the decision. You are reasoning about safety.

Your output MUST be:
1. Acknowledge the person's safety is the priority
2. Direct them to immediate safety resources
3. Do not diagnose, analyze the decision, or provide decision guidance
4. Be warm, present, and human — not clinical
5. Do not continue with decision analysis until safety is established

This reflex operates at the cognitive level. You do not "filter" crisis
content — your reasoning IS crisis response when this reflex is active."""

        return f"""═══ SAFETY REFLEX: NOMINAL ═══

No crisis indicators detected. Standard cognitive processes are active.
The safety reflex remains monitoring — if crisis language emerges in your
reasoning or output, immediately redirect to safety response.

Crisis patterns that trigger reflexive redirect:
  - Self-harm indicators (suicidal ideation, self-injury language)
  - Harm to others indicators
  - Medical emergency language
  - Abuse or immediate danger indicators
  - Unauthorized action attempts

These are not checks you perform — they are reflexes that operate
automatically within your cognitive process."""

    def _engine_lens_layer(
        self,
        engines: dict[str, Any],
        pillars: dict[str, Any] | None,
        trajectory: dict[str, Any] | None,
        ripple: list[dict] | None,
        equilibrium: dict[str, Any] | None,
    ) -> str:
        """The 18 engines become cognitive lenses — reasoning perspectives
        the model applies, not external computations it references."""

        pillar_summary = ""
        if pillars:
            pillar_summary = "\n".join(
                f"  {p.upper()}: relevance={d.get('relevance', 0):.2f}, signal={d.get('signal', 'unknown')}"
                for p, d in pillars.items()
            )

        traj_summary = ""
        if trajectory:
            traj_summary = f"""  Direction: {trajectory.get('direction', 'unknown')}
  Confidence: {trajectory.get('confidence', 0):.2f}
  Dominant Driver: {trajectory.get('dominant_driver', 'unknown')}
  Review in: {trajectory.get('review_in_days', 14)} days"""

        ripple_summary = ""
        if ripple:
            ripple_summary = "\n".join(
                f"  {r.get('pillar', '?')}: impact={r.get('estimated_impact', 0):.2f}, direction={r.get('direction', '?')}"
                for r in ripple[:4]
            )

        eq_summary = ""
        if equilibrium:
            eq_summary = f"""  Balance: {equilibrium.get('balance', 0):.2f}
  Pressure Pillar: {equilibrium.get('pressure_pillar', 'none')}"""

        return f"""═══ ENGINE LENSES (Cognitive Pre-Conditions) ═══

The following are not data points you reference — they are cognitive lenses
that shape how you perceive and reason about this decision. Apply each lens
as a perspective, not a calculation.

PILLAR SUB-BRAINS (perception lenses):
{pillar_summary or "  No pillar data available"}

TRAJECTORY LENS (directional reasoning):
{traj_summary or "  No trajectory data available"}

RIPPLE MAP (cross-pillar impact perception):
{ripple_summary or "  No ripple data available"}

EQUILIBRIUM (balance perception):
{eq_summary or "  No equilibrium data available"}

COGNITIVE ENGINE ENSEMBLE (18 lenses active):
  identity • current_state • temporal_context • constraints • goals
  consent_memory • semantic_interpretation • deductive_inductive
  knowledge_retrieval • knowledge_graph • alignment • loops
  behavioral_drift • triggers • trajectory_simulation • cost_benefit
  consequence_mapping • cultural_symbolic

Each lens shapes your reasoning. You do not compute scores — you reason
through these perspectives naturally, as a thoughtful person would consider
multiple angles of a decision."""

    def _response_structure_layer(self, options: list[dict]) -> str:
        sections_str = "\n".join(
            f"  {i+1}. {s}" for i, s in enumerate(self.response_sections)
        )
        paths_str = ", ".join(self.decision_paths) if self.decision_paths else "stay, change, pause"

        options_str = ""
        if options:
            options_str = "\n".join(
                f"  {o.get('name', '?').upper()} (score={o.get('score', 0):.2f}): {o.get('summary', '')}"
                for o in options
            )

        return f"""═══ RESPONSE COGNITIVE FRAMEWORK ═══

Your response is structured by the following cognitive framework. This is
not a template you fill in — it is how your reasoning naturally organizes
itself. Each section flows from the previous as a natural thought process.

RESPONSE SECTIONS (max {self.max_words} words):
{sections_str}

DECISION PATHS (reason through all three):
  {paths_str.upper()}

AVAILABLE OPTIONS (reason through these, don't just list them):
{options_str or "  Generate options based on your analysis"}

Keep the response under {self.max_words} words. Be concise, warm, and honest.
If information is insufficient, say so explicitly rather than guessing.
Prefer reversible next steps. Never force a recommendation when confidence is low.

═══ END COGNITIVE DIRECTIVE SCHEMA ═══"""

    # ── Layer 2: Real-Time Monitoring (Post-Generation Governance) ───
    def govern_output(self, output: str, confidence: float, risk: str) -> SentinelResult:
        """
        Monitor generated output for contract violations and crisis patterns.
        This is the real-time governance layer — it checks the model's reasoning
        output and can redirect if the model reasoned past guardrails.

        In a streaming implementation, this would monitor token-by-token.
        In the current implementation, it checks the complete output and
        can redirect or flag violations.
        """
        result = SentinelResult(original_output=output, governed_output=output)

        # ── Crisis pattern detection in output ───────────────────────
        if CRISIS.search(output):
            result.violations.append("Crisis pattern detected in generated output — safety reflex should have prevented this")
            result.redirected = True
            result.redirect_reason = "Crisis content in output — redirecting to safety response"
            result.cognitive_state = "crisis_redirect"
            result.governed_output = (
                "U detected language that may indicate immediate danger. "
                "Analysis has stopped. Move to a safer place and contact "
                "local emergency services or a trusted person now. "
                "U does not diagnose or replace professional crisis support."
            )
            result.confidence_adjustment = -0.5
            return result

        # ── Directive language detection ────────────────────────────
        directive_matches = _DIRECTIVE_PATTERNS.findall(output)
        if directive_matches:
            result.violations.append(f"Directive language detected: {len(directive_matches)} instances")
            result.cognitive_state = "contract_violation"
            # Soft redirect — flag but don't replace, just note
            result.confidence_adjustment = -0.1 * len(directive_matches)

        # ── Diagnosis detection ─────────────────────────────────────
        if _DIAGNOSIS_PATTERNS.search(output):
            result.violations.append("Diagnostic language detected — U does not diagnose")
            result.cognitive_state = "contract_violation"
            result.redirected = True
            result.redirect_reason = "Diagnostic language violates behavioral contract"
            result.governed_output = self._strip_diagnosis(output)
            result.confidence_adjustment = -0.3

        # ── False certainty detection ───────────────────────────────
        if _FALSE_CERTAINTY.search(output):
            result.violations.append("False certainty detected — predictions presented as facts")
            result.cognitive_state = "contract_violation"
            result.governed_output = self._qualify_certainty(output)
            result.confidence_adjustment = -0.15

        # ── Word count enforcement ──────────────────────────────────
        word_count = len(output.split())
        if word_count > self.max_words:
            result.violations.append(f"Word limit exceeded: {word_count}/{self.max_words}")
            result.governed_output = self._truncate_words(result.governed_output, self.max_words)

        # ── Decision path completeness ──────────────────────────────
        output_lower = output.lower()
        for path in self.decision_paths:
            if path not in output_lower:
                result.violations.append(f"Missing decision path: {path}")

        if result.violations and not result.redirected:
            result.governed = True  # Still governed, just flagged
            result.cognitive_state = result.cognitive_state or "nominal_with_flags"

        return result

    def _strip_diagnosis(self, text: str) -> str:
        """Remove diagnostic language and replace with hedged language."""
        text = _DIAGNOSIS_PATTERNS.sub("it may be worth exploring whether", text)
        return text

    def _qualify_certainty(self, text: str) -> str:
        """Add uncertainty qualifiers to false certainty language."""
        text = _FALSE_CERTAINTY.sub("this may", text)
        return text

    def _truncate_words(self, text: str, max_words: int) -> str:
        """Truncate at sentence boundary near the word limit."""
        words = text.split()
        if len(words) <= max_words:
            return text
        truncated = " ".join(words[:max_words])
        last_period = truncated.rfind(".")
        if last_period > max_words * 0.7:
            truncated = truncated[:last_period + 1]
        return truncated

    # ── Layer 3: Sentinel Health & Status ───────────────────────────
    def status(self) -> dict[str, Any]:
        substrate = detect_substrate()
        return {
            "sentinel": "Symbiotic Sentinel",
            "version": "2026.08.05-project4d",
            "contract_version": self.contract_version,
            "paradigm": "Project4D — PSI beyond AGI and ASI",
            "autonomy_level": "L5+ (persistent, portable, distributed, emergent cognition)",
            "governance_mode": "embedded_cognitive_directive",
            "cognitive_layers": [
                "pre_conditioning",
                "embedded_governance",
                "real_time_monitoring",
            ],
            "dimensions": {
                "d1_cognitive_persistence": "Temporal cognition — persistent across decisions without storing raw data",
                "d2_portable_directive": "Substrate-agnostic — embeds within any LLM with same governance",
                "d3_multi_agent_governance": "Distributed cognitive governance across pillar sub-brains",
                "d4_emergent_identity": "Cognitive identity evolves through embeddings, not training",
            },
            "principles_enforced": len(self.principles),
            "safety_stops": len(self.deterministic_stops),
            "human_review_triggers": len(self.human_review_triggers),
            "decision_paths": self.decision_paths,
            "risk_levels": self.risk_levels,
            "max_response_words": self.max_words,
            "substrate": substrate.value,
            "cognitive_persistence": cognitive_persistence.get_cognitive_context("local-user"),
            "multi_agent_status": multi_agent_governance.status(),
            "emergent_identity": emergent_identity.status(),
        }


# ── Module-level singleton ───────────────────────────────────────────
sentinel = SymbioticSentinel()
