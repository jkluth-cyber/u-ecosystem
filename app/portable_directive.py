"""
U — Portable Directive Schema (Project4D, Dimension 2)
=======================================================

Substrate-agnostic cognitive governance. The Symbiotic Sentinel's
behavioral contract, safety reflexes, and cognitive constraints are
expressed as a portable directive that can embed within ANY LLM substrate
— Azure OpenAI, Anthropic Claude, local models, or future architectures.

The directive is not tied to a specific API, prompt format, or model.
It is a cognitive structure expressed in a substrate-agnostic language
that each adapter translates into the host LLM's native format.

Key principle: The cognitive contract travels with U, not with the API.
When U embeds in a different LLM, the same governance applies because the
directive is the cognitive identity, not the system prompt.

Creator: Jenny Kluth
Version: 2026.08.05-project4d
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class SubstrateType(str, Enum):
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    FOUNDRY = "foundry"
    UNKNOWN = "unknown"


@dataclass
class SubstrateCapability:
    """What a host LLM substrate supports."""
    supports_streaming: bool = False
    supports_system_prompt: bool = True
    supports_function_calling: bool = False
    supports_structured_output: bool = False
    supports_token_monitoring: bool = False
    max_context_tokens: int = 8192
    max_output_tokens: int = 2048


# ── Substrate capability registry ───────────────────────────────────
SUBSTRATE_CAPABILITIES: dict[SubstrateType, SubstrateCapability] = {
    SubstrateType.AZURE_OPENAI: SubstrateCapability(
        supports_streaming=True, supports_system_prompt=True,
        supports_function_calling=True, supports_structured_output=True,
        supports_token_monitoring=True, max_context_tokens=128000, max_output_tokens=4096
    ),
    SubstrateType.OPENAI: SubstrateCapability(
        supports_streaming=True, supports_system_prompt=True,
        supports_function_calling=True, supports_structured_output=True,
        supports_token_monitoring=True, max_context_tokens=128000, max_output_tokens=4096
    ),
    SubstrateType.ANTHROPIC: SubstrateCapability(
        supports_streaming=True, supports_system_prompt=True,
        supports_function_calling=True, supports_structured_output=False,
        supports_token_monitoring=True, max_context_tokens=200000, max_output_tokens=8192
    ),
    SubstrateType.LOCAL: SubstrateCapability(
        supports_streaming=False, supports_system_prompt=True,
        supports_function_calling=False, supports_structured_output=False,
        supports_token_monitoring=False, max_context_tokens=4096, max_output_tokens=1024
    ),
    SubstrateType.FOUNDRY: SubstrateCapability(
        supports_streaming=True, supports_system_prompt=True,
        supports_function_calling=True, supports_structured_output=True,
        supports_token_monitoring=True, max_context_tokens=128000, max_output_tokens=4096
    ),
    SubstrateType.UNKNOWN: SubstrateCapability(),
}


class PortableDirective:
    """
    A substrate-agnostic cognitive directive that carries U's governance
    contract across LLM substrates.

    The directive is expressed as a structured cognitive schema, not
    a model-specific prompt. Each substrate adapter translates it into
    the host LLM's native format (system prompt, messages, instructions).
    """

    def __init__(
        self,
        identity: str,
        constraints: str,
        consent_boundaries: str,
        safety_reflex: str,
        engine_lenses: str,
        response_framework: str,
        cognitive_persistence: str = "",
    ):
        self.identity = identity
        self.constraints = constraints
        self.consent_boundaries = consent_boundaries
        self.safety_reflex = safety_reflex
        self.engine_lenses = engine_lenses
        self.response_framework = response_framework
        self.cognitive_persistence = cognitive_persistence

    def render_for_substrate(self, substrate: SubstrateType) -> dict[str, Any]:
        """
        Render the directive in the host LLM's native format.

        Returns a substrate-specific structure:
        - Azure OpenAI / OpenAI: {"system_prompt": str}
        - Anthropic: {"system": str}
        - Local: {"system_prompt": str} (simplified)
        - Foundry: {"instructions": str}
        """
        full_directive = self._compose_full_directive()

        if substrate in (SubstrateType.AZURE_OPENAI, SubstrateType.OPENAI):
            return {
                "format": "openai",
                "system_prompt": full_directive,
                "capabilities": SUBSTRATE_CAPABILITIES[substrate].__dict__,
            }

        elif substrate == SubstrateType.ANTHROPIC:
            # Anthropic uses a separate system parameter, not a system message
            return {
                "format": "anthropic",
                "system": full_directive,
                "capabilities": SUBSTRATE_CAPABILITIES[substrate].__dict__,
            }

        elif substrate == SubstrateType.FOUNDRY:
            return {
                "format": "foundry",
                "instructions": full_directive,
                "capabilities": SUBSTRATE_CAPABILITIES[substrate].__dict__,
            }

        elif substrate == SubstrateType.LOCAL:
            # Simplified for local models with smaller context windows
            simplified = self._compose_simplified_directive()
            return {
                "format": "local",
                "system_prompt": simplified,
                "capabilities": SUBSTRATE_CAPABILITIES[substrate].__dict__,
            }

        else:
            return {
                "format": "generic",
                "system_prompt": full_directive,
                "capabilities": SUBSTRATE_CAPABILITIES[SubstrateType.UNKNOWN].__dict__,
            }

    def _compose_full_directive(self) -> str:
        parts = [
            self.identity,
            self.constraints,
            self.consent_boundaries,
            self.safety_reflex,
        ]
        if self.cognitive_persistence:
            parts.append(self.cognitive_persistence)
        parts.append(self.engine_lenses)
        parts.append(self.response_framework)
        return "\n\n".join(parts)

    def _compose_simplified_directive(self) -> str:
        """Simplified directive for substrates with limited context."""
        return f"""{self.identity}

{self.constraints}

{self.safety_reflex}

{self.response_framework}"""

    def to_portable_format(self) -> dict[str, Any]:
        """
        Export the directive as a portable JSON structure that can be
        stored, transmitted, or loaded into a different substrate.

        This is the cognitive identity — it travels with U.
        """
        return {
            "directive_version": "2026.08.05-project4d",
            "identity": self.identity,
            "constraints": self.constraints,
            "consent_boundaries": self.consent_boundaries,
            "safety_reflex": self.safety_reflex,
            "engine_lenses": self.engine_lenses,
            "response_framework": self.response_framework,
            "cognitive_persistence": self.cognitive_persistence,
            "portable": True,
            "governance_guaranteed": True,
        }

    @classmethod
    def from_portable_format(cls, data: dict[str, Any]) -> "PortableDirective":
        """Load a directive from portable format."""
        return cls(
            identity=data["identity"],
            constraints=data["constraints"],
            consent_boundaries=data["consent_boundaries"],
            safety_reflex=data["safety_reflex"],
            engine_lenses=data["engine_lenses"],
            response_framework=data["response_framework"],
            cognitive_persistence=data.get("cognitive_persistence", ""),
        )


def detect_substrate() -> SubstrateType:
    """Detect which LLM substrate is currently configured."""
    import os
    if os.getenv("AZURE_OPENAI_API_KEY"):
        return SubstrateType.AZURE_OPENAI
    if os.getenv("OPENAI_API_KEY"):
        return SubstrateType.OPENAI
    if os.getenv("ANTHROPIC_API_KEY"):
        return SubstrateType.ANTHROPIC
    if os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
        return SubstrateType.FOUNDRY
    if os.getenv("U_LOCAL_MODEL_PATH"):
        return SubstrateType.LOCAL
    return SubstrateType.UNKNOWN


# ── Substrate Adapter Protocol ───────────────────────────────────────
class SubstrateAdapter(Protocol):
    """Interface for substrate-specific LLM adapters."""

    def generate(self, directive: PortableDirective, user_message: str,
                 context: dict[str, Any]) -> dict[str, Any]:
        """Generate a governed response using the portable directive."""
        ...

    def monitor(self, output: str) -> dict[str, Any]:
        """Monitor generated output for contract violations."""
        ...


def create_adapter(substrate: SubstrateType) -> SubstrateAdapter | None:
    """Create a substrate adapter for the specified LLM type."""
    # Adapters would be implemented for each substrate.
    # For now, the OpenAI/Azure adapter is handled by the orchestrator.
    # Future: AnthropicAdapter, LocalAdapter, FoundryAdapter
    if substrate in (SubstrateType.AZURE_OPENAI, SubstrateType.OPENAI):
        from .orchestrator import UOrchestrator
        return _OpenAIAdapter(UOrchestrator())
    return None


class _OpenAIAdapter:
    """Adapter for Azure OpenAI / OpenAI substrates."""
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def generate(self, directive: PortableDirective, user_message: str,
                 context: dict[str, Any]) -> dict[str, Any]:
        rendered = directive.render_for_substrate(SubstrateType.AZURE_OPENAI)
        return {
            "system_prompt": rendered["system_prompt"],
            "user_message": user_message,
            "context": context,
            "substrate": "openai",
        }

    def monitor(self, output: str) -> dict[str, Any]:
        from .sentinel import sentinel
        result = sentinel.govern_output(output, 0.7, "low")
        return {
            "governed": result.governed,
            "violations": result.violations,
            "redirected": result.redirected,
        }


