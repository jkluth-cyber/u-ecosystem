"""
U — D5: Projective Synthesis (PPSI Evolution)
=============================================

The 5th dimension of PSI. While D1-D4 handle cognitive persistence,
portable governance, distributed agency, and emergent identity,
D5 handles PROJECTION — the ability to synthesize multiple
decision pathways through a structured pipeline.

The synthesis flow from the urlife architecture:
    CCO → U Brain → Engines → Claude/LLM → Paths

This module implements:
  - Context Matrix Orchestration (CCO) — assembles structured input
  - Synthesis Pipeline — 5-stage projection with engine signals
  - Dual Path Generation — behavioral (Stay/Change/Pause) + 
    growth (Stabilize/Grow/Transform)

Creator: Jenny Kluth
Version: 2026.08.05-project4d-ppsi
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from typing import Any


# ── CCO (Context Matrix Orchestrator) ───────────────────────────

class ContextMatrixOrchestrator:
    """
    Pre-processes raw decision input into a structured Context Matrix
    before the U Brain engages. This is the first stage of the
    synthesis pipeline.
    """

    def __init__(self):
        self.matrix: dict[str, Any] = {}

    def assemble(self, raw_input: dict[str, Any]) -> dict[str, Any]:
        """
        Assemble the Context Matrix from raw user input.
        
        Extracts and structures:
        - situation (core problem statement)
        - desired_outcome (what success looks like)
        - known_facts (deterministic inputs)
        - constraints (boundaries on options)
        - unknowns (gaps in knowledge)
        - pillars (life domains affected)
        - time_horizon (past/present/future orientation)
        - consent_state (what the user has authorized)
        """
        self.matrix = {
            "situation": raw_input.get("situation", raw_input.get("title", "")),
            "desired_outcome": raw_input.get("desired_outcome", ""),
            "known_facts": raw_input.get("facts", []),
            "constraints": raw_input.get("constraints", []),
            "unknowns": raw_input.get("unknowns", []),
            "pillars": raw_input.get("pillars", []),
            "time_horizon": self._detect_time_horizon(raw_input),
            "consent_state": raw_input.get("consent", {}),
            "assembled_at": datetime.now(timezone.utc).isoformat(),
            "matrix_hash": self._hash_matrix(raw_input),
        }
        return self.matrix

    def _detect_time_horizon(self, raw: dict) -> list[str]:
        horizons = []
        text = (raw.get("situation", "") + " " + raw.get("desired_outcome", "")).lower()
        past_words = ["was", "were", "had", "used to", "before", "previously", "past"]
        present_words = ["am", "is", "now", "currently", "today", "present"]
        future_words = ["will", "want to", "plan", "future", "goal", "hope", "aspire"]
        if any(w in text for w in past_words): horizons.append("past")
        if any(w in text for w in present_words): horizons.append("present")
        if any(w in text for w in future_words): horizons.append("future")
        return horizons or ["present"]

    def _hash_matrix(self, raw: dict) -> str:
        canonical = json.dumps(raw, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def summary(self) -> dict[str, Any]:
        """Return a compact summary for the synthesis pipeline."""
        return {
            "situation_length": len(self.matrix.get("situation", "")),
            "facts_count": len(self.matrix.get("known_facts", [])),
            "constraints_count": len(self.matrix.get("constraints", [])),
            "unknowns_count": len(self.matrix.get("unknowns", [])),
            "pillars_active": self.matrix.get("pillars", []),
            "time_horizons": self.matrix.get("time_horizon", []),
            "matrix_hash": self.matrix.get("matrix_hash", ""),
        }


# ── Synthesis Pipeline Stages ────────────────────────────────────

SYNTHESIS_STAGES = [
    "cco",       # Context Matrix Orchestrator
    "u_brain",   # Route through cognitive layer
    "engines",   # 18-engine ensemble fire
    "claude",    # LLM synthesis
    "paths",     # Decision path rendering
]


class SynthesisPipeline:
    """
    The 5-stage synthesis pipeline that projects decision pathways.
    Each stage feeds into the next, building from raw context to
    fully rendered dual-path recommendations.
    """

    def __init__(self):
        self.stages_completed: list[dict[str, Any]] = []
        self.engine_signals: list[dict[str, Any]] = []
        self.behavioral_paths: list[dict[str, Any]] = []
        self.growth_paths: list[dict[str, Any]] = []
        self.synthesis_output: str = ""

    def run_cco(self, raw_input: dict[str, Any]) -> dict[str, Any]:
        """Stage 1: Context Matrix Orchestration."""
        cco = ContextMatrixOrchestrator()
        matrix = cco.assemble(raw_input)
        self.stages_completed.append({
            "stage": "cco",
            "status": "complete",
            "summary": cco.summary(),
        })
        return matrix

    def route_brain(self, matrix: dict[str, Any], user_id: str) -> dict[str, Any]:
        """Stage 2: Route through U Brain cognitive layer."""
        # The brain routing determines which engines are relevant
        pillars = matrix.get("pillars", [])
        relevant_engines = self._select_engines(pillars)
        
        self.stages_completed.append({
            "stage": "u_brain",
            "status": "complete",
            "pillars_detected": pillars,
            "engines_selected": len(relevant_engines),
        })
        return {
            "matrix": matrix,
            "engines": relevant_engines,
            "user_id": user_id,
        }

    def fire_engines(self, brain_output: dict[str, Any], 
                     engine_trace: list[dict[str, Any]]) -> dict[str, Any]:
        """Stage 3: Fire all 18 engines and collect signals."""
        # Engine trace comes from the existing orchestrator
        self.engine_signals = []
        for entry in engine_trace:
            self.engine_signals.append({
                "engine": entry.get("engine", "unknown"),
                "status": "completed",
                "output_summary": entry.get("output", "")[:120],
                "pillar": entry.get("pillar", "core"),
            })
        
        self.stages_completed.append({
            "stage": "engines",
            "status": "complete",
            "engine_count": len(self.engine_signals),
            "signals": self.engine_signals,
        })
        return {"engine_signals": self.engine_signals}

    def synthesize(self, engine_output: dict[str, Any],
                   llm_response: str | None,
                   recommendation: dict[str, Any]) -> dict[str, Any]:
        """Stage 4: Claude/LLM synthesis of engine outputs."""
        if llm_response:
            self.synthesis_output = llm_response
        else:
            # Deterministic fallback synthesis
            self.synthesis_output = self._deterministic_synthesis(
                engine_output, recommendation
            )
        
        self.stages_completed.append({
            "stage": "claude",
            "status": "complete",
            "synthesis_length": len(self.synthesis_output),
            "source": "llm" if llm_response else "deterministic",
        })
        return {"synthesis": self.synthesis_output}

    def render_paths(self, synthesis: dict[str, Any],
                     options: list[dict[str, Any]]) -> dict[str, Any]:
        """Stage 5: Render dual-path framework."""
        # Behavioral paths: Stay/Change/Pause (from existing options)
        behavioral_map = {"stay": 0, "change": 1, "pause": 2}
        self.behavioral_paths = []
        for opt in options:
            name = opt.get("name", "").lower()
            if name in behavioral_map:
                self.behavioral_paths.append({
                    "name": name,
                    "label": name.capitalize(),
                    "summary": opt.get("summary", ""),
                    "benefits": opt.get("benefits", []),
                    "costs": opt.get("costs", []),
                    "consequences": opt.get("consequences", ""),
                    "next_step": opt.get("next_step", ""),
                    "confidence": opt.get("confidence", 0.5),
                    "type": "behavioral",
                })

        # Growth paths: Stabilize/Grow/Transform (projective synthesis)
        self.growth_paths = self._project_growth_paths(options, synthesis)
        
        self.stages_completed.append({
            "stage": "paths",
            "status": "complete",
            "behavioral_count": len(self.behavioral_paths),
            "growth_count": len(self.growth_paths),
        })
        return {
            "behavioral_paths": self.behavioral_paths,
            "growth_paths": self.growth_paths,
        }

    def _select_engines(self, pillars: list[str]) -> list[str]:
        """Select relevant engines based on active pillars."""
        all_engines = [
            "identity", "current_state", "temporal_context", "constraints",
            "goals", "consent_memory", "semantic_interpretation",
            "deductive_inductive", "knowledge_retrieval", "knowledge_graph",
            "alignment", "loops", "behavioral_drift", "triggers",
            "trajectory_simulation", "cost_benefit", "consequence_mapping",
            "cultural_symbolic",
        ]
        # All 18 engines fire in the full-scale model
        return all_engines

    def _deterministic_synthesis(self, engine_output: dict[str, Any],
                                  recommendation: dict[str, Any]) -> str:
        """Fallback synthesis when no LLM is available."""
        signals = engine_output.get("engine_signals", [])
        engine_names = [s.get("engine", "") for s in signals]
        rec = recommendation.get("recommendation", "No recommendation available.")
        confidence = recommendation.get("confidence", 0.5)
        
        return (
            f"Synthesis complete across {len(signals)} cognitive engines. "
            f"Primary recommendation: {rec} "
            f"Confidence: {confidence:.0%}. "
            f"Behavioral paths (Stay/Change/Pause) and growth trajectories "
            f"(Stabilize/Grow/Transform) have been projected based on "
            f"the assembled context matrix and engine ensemble output."
        )

    def _project_growth_paths(self, options: list[dict[str, Any]],
                               synthesis: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Project growth trajectories from the behavioral options.
        
        Stabilize: Consolidate and strengthen the current position.
        Grow: Expand capabilities or reach in the chosen direction.
        Transform: Fundamental shift in approach or identity.
        """
        growth_paths = []
        synth_text = synthesis.get("synthesis", "")
        
        # Stabilize — derived from the Stay option
        stay_opt = next((o for o in options if o.get("name", "").lower() == "stay"), {})
        growth_paths.append({
            "name": "stabilize",
            "label": "Stabilize",
            "summary": "Consolidate and strengthen your current position. "
                       "Build resilience before expanding.",
            "what_it_means": "Focus on deepening existing foundations, "
                             "reducing volatility, and creating stability.",
            "recommended_action": stay_opt.get("next_step", "Maintain current trajectory with intentional reinforcement."),
            "timeframe": "Immediate to short-term",
            "confidence": stay_opt.get("confidence", 0.5),
            "type": "growth",
            "accent": "emerald",
        })

        # Grow — derived from the Change option
        change_opt = next((o for o in options if o.get("name", "").lower() == "change"), {})
        growth_paths.append({
            "name": "grow",
            "label": "Grow",
            "summary": "Expand capabilities or reach in the direction "
                       "of your desired outcome.",
            "what_it_means": "Take the change path and scale it — new skills, "
                            "broader network, increased capacity.",
            "recommended_action": change_opt.get("next_step", "Pursue the change with a growth-oriented expansion plan."),
            "timeframe": "Short to medium-term",
            "confidence": change_opt.get("confidence", 0.5),
            "type": "growth",
            "accent": "cyan",
        })

        # Transform — a projective leap
        growth_paths.append({
            "name": "transform",
            "label": "Transform",
            "summary": "Fundamental shift in approach or identity. "
                       "Not incremental change — a paradigm shift.",
            "what_it_means": "Reframe the problem entirely. The question "
                            "isn't which path to take, but whether the "
                            "paths themselves need redefining.",
            "recommended_action": "Re-examine the core assumptions. What if "
                                  "the decision framework itself is the constraint?",
            "timeframe": "Long-term or open-ended",
            "confidence": 0.3,  # Transform is inherently lower confidence
            "type": "growth",
            "accent": "purple",
        })

        return growth_paths

    def get_pipeline_status(self) -> dict[str, Any]:
        """Return the full pipeline execution status."""
        return {
            "stages": SYNTHESIS_STAGES,
            "completed": [s["stage"] for s in self.stages_completed],
            "stage_details": self.stages_completed,
            "engine_signal_count": len(self.engine_signals),
            "behavioral_paths": len(self.behavioral_paths),
            "growth_paths": len(self.growth_paths),
            "synthesis_source": "llm" if any(
                s.get("source") == "llm" for s in self.stages_completed
                if s.get("stage") == "claude"
            ) else "deterministic",
        }


# ── D5 Layer (Projective Synthesis Dimension) ────────────────────

class ProjectiveSynthesisLayer:
    """
    D5: Projective Synthesis — the 5th PSI dimension.
    
    This dimension handles the system's ability to PROJECT multiple
    synthesis pathways through a structured pipeline, producing both
    behavioral and growth-oriented decision paths.
    
    Unlike D1-D4 which operate on cognitive persistence, governance,
    and identity, D5 operates on PROJECTION — the forward-looking
    synthesis of possible futures.
    """

    def __init__(self):
        self.pipeline = SynthesisPipeline()
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    def run_synthesis(self, raw_input: dict[str, Any],
                      engine_trace: list[dict[str, Any]],
                      llm_response: str | None,
                      recommendation: dict[str, Any],
                      options: list[dict[str, Any]],
                      user_id: str = "local-user") -> dict[str, Any]:
        """
        Run the full 5-stage synthesis pipeline.
        
        Returns the complete projection: behavioral paths, growth paths,
        engine signals, and synthesis output.
        """
        # Stage 1: CCO
        matrix = self.pipeline.run_cco(raw_input)
        
        # Stage 2: U Brain routing
        brain_output = self.pipeline.route_brain(matrix, user_id)
        
        # Stage 3: Fire engines
        engine_output = self.pipeline.fire_engines(brain_output, engine_trace)
        
        # Stage 4: Synthesis
        synthesis = self.pipeline.synthesize(engine_output, llm_response, recommendation)
        
        # Stage 5: Render paths
        paths = self.pipeline.render_paths(synthesis, options)
        
        return {
            "dimension": "D5",
            "name": "Projective Synthesis",
            "active": True,
            "pipeline_status": self.pipeline.get_pipeline_status(),
            "context_matrix": matrix,
            "behavioral_paths": paths["behavioral_paths"],
            "growth_paths": paths["growth_paths"],
            "synthesis_output": synthesis["synthesis"],
            "engine_signals": self.pipeline.engine_signals,
        }

    def status(self) -> dict[str, Any]:
        return {
            "name": "Projective Synthesis",
            "dimension": "D5",
            "active": self._active,
            "description": "Forward-looking synthesis of multiple decision pathways through a 5-stage pipeline",
            "module": "projective_synthesis",
            "pipeline_stages": SYNTHESIS_STAGES,
            "capabilities": [
                "context_matrix_orchestration",
                "dual_path_projection",
                "engine_signal_collection",
                "deterministic_synthesis_fallback",
                "growth_trajectory_modeling",
            ],
        }


# ── Module Singletons ───────────────────────────────────────────

projective_synthesis = ProjectiveSynthesisLayer()
cco = ContextMatrixOrchestrator()
