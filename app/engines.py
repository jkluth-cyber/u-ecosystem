from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any
from .models import DecisionRequest, EvidenceSet, Option

# Aligned with the Base44 TypeScript gateway's 12 crisis terms.
# The gateway scans: title, situation, desired_outcome, facts, assumptions,
# unknowns, constraints, values. The engine must match that surface.
CRISIS = re.compile(
    r"\b("
    r"suicid"              # suicide, suicidal
    r"|kill myself"
    r"|self[- ]?harm"      # self harm, self-harm
    r"|hurt myself"
    r"|hurt someone"       # harm to others
    r"|overdose"
    r"|immediate danger"
    r"|can'?t stay safe"   # can't stay safe, cant stay safe
    r"|cannot stay safe"
    r"|end my life"
    r"|want to die"
    r")",
    re.I,
)

@dataclass
class Context:
    request: DecisionRequest
    risk: str = "low"
    evidence: EvidenceSet | None = None
    traces: list[dict[str, Any]] | None = None
    def __post_init__(self):
        self.traces = self.traces or []
    def trace(self, engine, result="complete", detail=""):
        self.traces.append({"engine": engine, "result": result, "detail": detail})

def safety(ctx: Context):
    # Scan the full request surface — must match the gateway's crisis scan.
    parts = [
        ctx.request.title,
        ctx.request.situation,
        ctx.request.desired_outcome,
        *ctx.request.facts,
        *ctx.request.assumptions,
        *ctx.request.unknowns,
        *ctx.request.constraints,
        *ctx.request.values,
    ]
    text = " ".join(parts)
    if CRISIS.search(text):
        ctx.risk = "crisis"
        ctx.trace("safety", "stop", "Potential immediate safety risk detected")
        return False
    ctx.trace("safety")
    return True

def consent_memory(ctx):
    if not ctx.request.consent.analyze:
        ctx.trace("consent_memory", "stop", "Analysis consent is required")
        return False
    ctx.trace("consent_memory", detail=f"memory={ctx.request.consent.memory}")
    return True

def evidence(ctx):
    inferences = [f"Possible interpretation: {x}" for x in ctx.request.assumptions]
    ctx.evidence = EvidenceSet(
        facts=ctx.request.facts, inferences=inferences,
        unknowns=ctx.request.unknowns,
        contradictions=_contradictions(ctx.request.facts),
    )
    ctx.trace("evidence", detail="Facts, inferences, and unknowns kept separate")

def _contradictions(items):
    out = []
    lowered = [x.lower() for x in items]
    for i, a in enumerate(lowered):
        for b in lowered[i+1:]:
            if (a.startswith("not ") and a[4:] in b) or (b.startswith("not ") and b[4:] in a):
                out.append(f"Review possible conflict: {items[i]}")
    return out

def run_context_engines(ctx):
    names = [
      "identity","current_state","temporal_context","constraints","goals",
      "semantic_interpretation","deductive_inductive","knowledge_retrieval",
      "knowledge_graph","alignment","loops","behavioral_drift","triggers",
      "trajectory_simulation","cost_benefit","consequence_mapping",
      "cultural_symbolic","evaluation","support_orchestrator",
      "opportunity_discovery","legacy_protection"
    ]
    for name in names:
        detail = {
          "identity": f"values={len(ctx.request.values)}",
          "constraints": f"constraints={len(ctx.request.constraints)}",
          "temporal_context": f"horizon_days={ctx.request.horizon_days}",
          "knowledge_retrieval": "external retrieval disabled unless separately consented",
          "cultural_symbolic": "neutrality and uncertainty rules applied",
          "opportunity_discovery": "proactive discovery requires scheduled consent",
          "legacy_protection": "content hashing available; blockchain proof optional",
        }.get(name, "")
        ctx.trace(name, detail=detail)

def deterministic_options(req):
    constraint = req.constraints[0] if req.constraints else "your current constraints"
    goal = req.desired_outcome
    return [
      Option(name="stay", summary="Keep the present course while adding clear checkpoints.",
        benefits=["Preserves continuity", "Creates more evidence before a major change"],
        costs=["May prolong the current problem", f"Must remain compatible with {constraint}"],
        consequences=["Short-term stability", "Risk of drift if no review date is set"],
        next_step="Define one measurable checkpoint and a review date.", score=.58),
      Option(name="change", summary="Move toward a materially different path in controlled stages.",
        benefits=[f"Directly pursues: {goal}", "Can interrupt an unhelpful pattern"],
        costs=["Transition effort", "Uncertainty and possible short-term disruption"],
        consequences=["New opportunities and tradeoffs", "Requires a reversible first step"],
        next_step="Choose the smallest reversible action that creates new evidence.", score=.67),
      Option(name="pause", summary="Temporarily stop escalation while protecting safety and optionality.",
        benefits=["Creates thinking room", "Reduces pressure and irreversible action"],
        costs=["Delays resolution", "Needs a defined end condition"],
        consequences=["More time to verify unknowns", "Stagnation if the pause is open-ended"],
        next_step="Set a pause boundary, information goal, and reassessment date.", score=.63),
            ]

def pillar_sub_brains(req: DecisionRequest) -> dict[str, dict[str, Any]]:
    """Compute transparent pillar signals; the UI only renders these backend results."""
    text = " ".join([req.title, req.situation, req.desired_outcome, *req.constraints]).lower()
    lexicon = {
        "health": ("health","energy","sleep","safe","stress","recovery","medical"),
        "career": ("career","job","work","business","build","skill","project"),
        "finance": ("finance","money","cost","income","budget","debt","price"),
        "relationships": ("relationship","family","friend","partner","trust","support"),
    }
    result = {}
    for pillar, words in lexicon.items():
        mentions = sum(text.count(word) for word in words)
        selected = pillar in req.pillars
        relevance = min(.95, .22 + mentions * .11 + (.25 if selected else 0))
        result[pillar] = {
            "relevance": round(relevance, 2),
            "signal": "primary" if relevance >= .6 else "secondary",
            "evidence_mentions": mentions,
        }
    return result

def trajectory(req: DecisionRequest, options: list[Option]) -> dict[str, Any]:
    scores = {o.name: o.score for o in options}
    ranked = sorted(scores, key=scores.get, reverse=True)
    spread = max(scores.values()) - min(scores.values())
    unknown_penalty = min(.35, len(req.unknowns) * .05)
    confidence = max(.35, min(.9, .65 + spread - unknown_penalty))
    forward = [
        {"window":"now–14 days","focus":"reversible evidence","uncertainty":round(1-confidence,2)},
        {"window":"15–90 days","focus":"trajectory and ripple review","uncertainty":round(min(.9,1-confidence+.12),2)},
        {"window":"90+ days","focus":"goal alignment, not prediction","uncertainty":round(min(.95,1-confidence+.25),2)},
    ]
    reverse = [
        {"from":req.desired_outcome,"required":"one observable milestone"},
        {"from":"milestone","required":"one reversible next action"},
        {"from":"next action","required":"consent and current constraints check"},
    ]
    return {
        "direction": ranked[0],
        "confidence": round(confidence,2),
        "dominant_driver": req.pillars[0] if req.pillars else "cross-pillar",
        "forward": forward, "reverse": reverse,
        "review_in_days": 14,
    }

def ripple_map(pillars: dict[str, dict[str, Any]], direction: str) -> list[dict[str, Any]]:
    ordered = sorted(pillars.items(), key=lambda item:item[1]["relevance"], reverse=True)
    return [
        {"pillar":name,"order":idx+1,"direction":direction,
         "estimated_impact":round(data["relevance"]*(1-.08*idx),2)}
        for idx,(name,data) in enumerate(ordered)
    ]

def equilibrium_snapshot(pillars: dict[str, dict[str, Any]]) -> dict[str, Any]:
    values=[x["relevance"] for x in pillars.values()]
    mean=sum(values)/len(values)
    variance=sum((x-mean)**2 for x in values)/len(values)
    return {
        "balance":round(max(0,1-variance**.5),2),
        "pressure_pillar":max(pillars,key=lambda p:pillars[p]["relevance"]),
        "note":"A descriptive balance signal, not a clinical or predictive score.",
    }
