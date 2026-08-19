from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .models import JarvisRequest, DecisionResponse, EmergencyRequest
from .orchestrator import UOrchestrator
from .engines import CRISIS
from .sentinel import sentinel

@dataclass(frozen=True)
class JarvisEnvelope:
    """JARVIS interprets and presents; U Brain + Sentinel remain the source of truth."""
    interface: str
    command: str
    message: str
    decision: dict[str, Any] | None
    emergency: dict[str, Any] | None
    sentinel: dict[str, Any] | None = None

class Jarvis:
    def __init__(self, brain: UOrchestrator):
        self.brain = brain

    def handle(self, request: JarvisRequest) -> JarvisEnvelope:
        if request.command == "emergency":
            full_surface = " ".join([
                request.title, request.situation, request.desired_outcome,
                *request.facts, *request.assumptions, *request.unknowns,
                *request.constraints, *request.values,
            ])[:4000]
            emergency = self.emergency(EmergencyRequest(
                user_id=request.user_id, message=full_surface,
                immediate_danger=True,
            ))
            return JarvisEnvelope("JARVIS", "emergency",
                "Emergency mode is active. Sentinel cognitive redirect engaged.",
                None, emergency, sentinel.status())

        decision: DecisionResponse = self.brain.analyze(request)
        message = (
            "I mapped Stay, Change, and Pause through the Sentinel-governed cognitive layer."
            if decision.options else
            "I paused the cognitive flow because a governing boundary was reached."
        )
        return JarvisEnvelope("JARVIS", request.command, message,
            decision.model_dump(), None, sentinel.status())

    def emergency(self, request: EmergencyRequest) -> dict[str, Any]:
        # Defense-in-depth: scan message content for crisis patterns
        crisis_in_message = bool(CRISIS.search(request.message))
        escalate = request.immediate_danger or crisis_in_message

        # Sentinel cognitive redirect — the emergency response is shaped
        # by the Sentinel's safety reflex layer, not just a static message.
        return {
            "mode": "emergency",
            "risk": "crisis" if escalate else "high",
            "analysis_stopped": True,
            "sentinel_state": "crisis_redirect" if escalate else "monitoring",
            "steps": [
                "Move away from immediate danger if you can do so safely.",
                "Contact local emergency services now if danger is immediate.",
                "Contact a trusted person and ask them to stay with you or remain on the phone.",
                "Use a verified local crisis resource appropriate to your country.",
            ],
            "external_action_executed": False,
            "human_choice_required": True,
            "message": "U can organize the next safe steps, but it cannot contact anyone without your explicit approval.",
        }

jarvis = Jarvis(UOrchestrator())
