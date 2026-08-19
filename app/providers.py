"""Bounded provider adapters. None bypass U governance."""
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderStatus:
    name: str
    configured: bool
    purpose: str

def statuses() -> list[ProviderStatus]:
    return [
        ProviderStatus("deterministic", True, "governance, safety, scoring, fallback"),
        ProviderStatus("openai", bool(os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")), "optional structured explanation"),
        ProviderStatus("azure_foundry", bool(os.getenv("AZURE_AI_PROJECT_ENDPOINT")),
            "optional hosted model/tool infrastructure"),
        ProviderStatus("cosmos", bool(os.getenv("AZURE_COSMOS_ENDPOINT")),
            "future MemoryStore implementation"),
        ProviderStatus("azure_ai_search", bool(os.getenv("AZURE_SEARCH_ENDPOINT")),
            "future consent-scoped retrieval"),
    ]
