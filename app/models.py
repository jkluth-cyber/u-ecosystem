from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field

Pillar = Literal["health", "career", "finance", "relationships"]
Risk = Literal["low", "medium", "high", "crisis"]

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

class Consent(BaseModel):
    analyze: bool = False
    memory: bool = False
    research: bool = False
    external_actions: bool = False
    sensitive_data: bool = False

class DecisionRequest(BaseModel):
    user_id: str = "local-user"
    title: str = Field(min_length=2, max_length=160)
    situation: str = Field(min_length=5, max_length=12000)
    desired_outcome: str = Field(min_length=2, max_length=2000)
    pillars: list[Pillar] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    horizon_days: int = Field(default=90, ge=1, le=3650)
    consent: Consent = Field(default_factory=Consent)

class EvidenceSet(BaseModel):
    facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)

class Option(BaseModel):
    name: Literal["stay", "change", "pause"]
    summary: str
    benefits: list[str]
    costs: list[str]
    consequences: list[str]
    next_step: str
    score: float = Field(ge=0, le=1)

class DecisionResponse(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(default_factory=now)
    mode: str = "Decision Guide"
    risk: Risk
    safety_message: str | None = None
    evidence: EvidenceSet
    options: list[Option]
    recommendation: str
    rationale: list[str]
    questions: list[str]
    confidence: float = Field(ge=0, le=1)
    approval_required: bool = True
    engine_trace: list[dict[str, Any]]
    pillar_sub_brains: dict[str, Any] = Field(default_factory=dict)
    trajectory: dict[str, Any] = Field(default_factory=dict)
    ripple_map: list[dict[str, Any]] = Field(default_factory=list)
    equilibrium: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = "Guidance is approximate, neutral, and not medical, legal, or financial advice."

class ApprovalRequest(BaseModel):
    session_id: str
    proposal_id: str
    user_id: str
    approved: bool
    note: str = ""

class OutcomeRequest(BaseModel):
    session_id: str
    outcome: str
    helpfulness: int = Field(ge=1, le=5)
    memory_consent: bool = False

class JarvisRequest(DecisionRequest):
    command: Literal["decide", "reflect", "plan", "emergency"] = "decide"
    conversation_id: str | None = None

class EmergencyRequest(BaseModel):
    user_id: str = "local-user"
    message: str = Field(min_length=2, max_length=4000)
    country_code: str = Field(default="US", min_length=2, max_length=2)
    immediate_danger: bool = False
    can_contact_trusted_person: bool | None = None

class ActionProposal(BaseModel):
    session_id: str
    action_type: str
    destination: str
    payload_summary: str
    reversible: bool = False

class ApprovalTokenRequest(BaseModel):
    user_id: str
    proposal_id: str
    session_id: str

class ExecuteRequest(BaseModel):
    user_id: str
    proposal_id: str
    session_id: str
    approval_token: str
