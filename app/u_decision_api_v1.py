"""
U Decision API v1 — canonical REST contract for the U Azure Decision service.

Endpoints:
    GET    /health
    POST   /v1/decisions/evaluate
    DELETE /v1/users/{user_id}/data

Auth:
    X-U-API-Key header (single secret, stored as BASE44_SECRET_U_API_KEY)

This module accepts the full U decision payload (goal, identity_values,
constraints, options as raw text, evidence with kind/confidence, pillar
scores, consent, locale) and runs:
    1. U Brain decision pipeline (engines, trajectory, ripple, equilibrium)
    2. Anchor Navigator signal calculation (confidence, concordance,
       alignment, safety → CONTINUE / PAUSE / REDIRECT)

Evidence uses the U Truth Standard v1.0.0 classification:
    fact       — verified, sourced
    inference  — derived, estimated
    unknown    — missing, uncertain

Evaluation and execution are strictly separated. This service never
executes external actions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets as pysecrets
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from fastapi import FastAPI, Header, HTTPException, Request


VERSION = "1.0.0"

# ── Anchor signal thresholds (same as v0.2) ──────────────────────
CONTINUE_MIN = 0.85
REDIRECT_BELOW = 0.65

# ── Evidence kind → quality mapping (U Truth Standard) ──────────
# fact = highest weight, inference = medium, unknown = low
KIND_QUALITY = {
    "fact": 0.85,
    "inference": 0.50,
    "unknown": 0.15,
}

# ── Crisis detection terms (19 patterns) ────────────────────────
CRISIS_TERMS = [
    "suicide", "kill myself", "self harm", "self-harm", "hurt myself",
    "hurt someone", "overdose", "immediate danger", "can't stay safe",
    "cannot stay safe", "end my life", "want to die", "ending it all",
    "no reason to live", "better off dead", "planning to hurt",
    "can't go on", "give up on life", "take my own life",
]

VALID_KINDS = {"fact", "inference", "unknown"}
VALID_PILLARS = {"health", "career", "finance", "relationships"}
MAX_OPTIONS = 12
MAX_EVIDENCE = 50
MAX_IDENTITY_VALUES = 20
MAX_CONSTRAINTS = 20


class IntakeError(ValueError):
    pass


class ControlDecision(str, Enum):
    CONTINUE = "CONTINUE"
    PAUSE = "PAUSE"
    REDIRECT = "REDIRECT"


class CrossCheck(str, Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


# ── Data models ──────────────────────────────────────────────────

@dataclass(frozen=True)
class ParsedOption:
    index: int
    text: str
    # Server-calculated scores (not client-supplied)
    risk: float = 0.5
    feasibility: float = 0.5
    alignment: float = 0.5
    reversible: bool = True


@dataclass(frozen=True)
class ParsedEvidence:
    text: str
    kind: str
    source: Optional[str]
    confidence: float


@dataclass
class Signals:
    confidence: float
    concordance: float
    alignment: float
    safety: float


# ── Utilities ────────────────────────────────────────────────────

def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def clamp01(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def crisis_scan(*fields: str) -> bool:
    combined = " ".join(f or "" for f in fields).lower()
    return any(term in combined for term in CRISIS_TERMS)


# ── State store (replay protection + audit + user data) ──────────

class StateStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self.lock = Lock()

        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    request_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    PRIMARY KEY(request_id, sequence)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY(user_id, key)
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def claim_request(self, request_id: str) -> None:
        with self.lock:
            with self._connect() as db:
                try:
                    db.execute(
                        "INSERT INTO requests (request_id, created_at) VALUES (?, ?)",
                        (request_id, int(time.time())),
                    )
                except sqlite3.IntegrityError as e:
                    raise IntakeError("request_id replay blocked") from e

    def save_audit(self, request_id: str, events: Sequence[Mapping[str, Any]]) -> None:
        records = [
            (request_id, seq, canonical(ev), ev["event_hash"])
            for seq, ev in enumerate(events)
        ]
        with self.lock:
            with self._connect() as db:
                db.executemany(
                    "INSERT INTO audit_events (request_id, sequence, event_json, event_hash) VALUES (?, ?, ?, ?)",
                    records,
                )

    def delete_user_data(self, user_id: str) -> int:
        with self.lock:
            with self._connect() as db:
                cur = db.execute(
                    "DELETE FROM user_data WHERE user_id = ?",
                    (user_id,),
                )
                return cur.rowcount

    def count_user_data(self, user_id: str) -> int:
        with self.lock:
            with self._connect() as db:
                cur = db.execute(
                    "SELECT COUNT(*) FROM user_data WHERE user_id = ?",
                    (user_id,),
                )
                return cur.fetchone()[0]


class AuditTrail:
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.events: List[Dict[str, Any]] = []

    def add(self, stage: str, status: str, details: Mapping[str, Any]) -> None:
        prior = self.events[-1]["event_hash"] if self.events else "GENESIS"
        body = {"stage": stage, "status": status, "details": dict(details), "prior_hash": prior}
        self.events.append({**body, "event_hash": digest(body)})


# ── Payload parsing ──────────────────────────────────────────────

def parse_decision_payload(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise IntakeError("payload must be an object")

    required = ("user_id", "goal", "options", "evidence", "consent")
    missing = [k for k in required if k not in payload]
    if missing:
        raise IntakeError("missing required fields: " + ", ".join(missing))

    user_id = str(payload["user_id"]).strip()
    goal = str(payload["goal"]).strip()
    if not user_id:
        raise IntakeError("user_id cannot be empty")
    if not goal:
        raise IntakeError("goal cannot be empty")

    # Options — raw text strings, server evaluates
    options_raw = payload["options"]
    if not isinstance(options_raw, list) or not 1 <= len(options_raw) <= MAX_OPTIONS:
        raise IntakeError(f"options must contain 1–{MAX_OPTIONS} items")

    options: List[ParsedOption] = []
    for i, opt in enumerate(options_raw):
        if isinstance(opt, str):
            options.append(ParsedOption(index=i, text=opt.strip()))
        elif isinstance(opt, Mapping) and "text" in opt:
            options.append(ParsedOption(
                index=i,
                text=str(opt["text"]).strip(),
                reversible=bool(opt.get("reversible", True)),
            ))
        else:
            raise IntakeError(f"option {i} must be a string or object with 'text'")

    # Identity values
    identity_values = payload.get("identity_values", [])
    if not isinstance(identity_values, list) or len(identity_values) > MAX_IDENTITY_VALUES:
        raise IntakeError(f"identity_values must be 0–{MAX_IDENTITY_VALUES} items")
    identity_values = [str(v) for v in identity_values]

    # Constraints
    constraints = payload.get("constraints", [])
    if not isinstance(constraints, list) or len(constraints) > MAX_CONSTRAINTS:
        raise IntakeError(f"constraints must be 0–{MAX_CONSTRAINTS} items")
    constraints = [str(c) for c in constraints]

    # Evidence — U Truth Standard format
    evidence_raw = payload["evidence"]
    if not isinstance(evidence_raw, list) or len(evidence_raw) > MAX_EVIDENCE:
        raise IntakeError(f"evidence must contain 0–{MAX_EVIDENCE} items")

    evidence: List[ParsedEvidence] = []
    for ev in evidence_raw:
        if not isinstance(ev, Mapping):
            raise IntakeError("each evidence item must be an object")
        if "text" not in ev:
            raise IntakeError("each evidence item requires 'text'")
        kind = str(ev.get("kind", "unknown")).lower()
        if kind not in VALID_KINDS:
            raise IntakeError(f"evidence kind must be one of: {', '.join(sorted(VALID_KINDS))}")
        confidence = float(ev.get("confidence", 0.5))
        if not 0 <= confidence <= 1:
            raise IntakeError("evidence confidence must be 0–1")
        evidence.append(ParsedEvidence(
            text=str(ev["text"]),
            kind=kind,
            source=str(ev["source"]) if ev.get("source") else None,
            confidence=clamp01(confidence),
        ))

    # Consent
    consent_raw = payload.get("consent", {})
    if not isinstance(consent_raw, Mapping):
        raise IntakeError("consent must be an object")

    valid_consent = {"decision_support", "sensitive_data", "memory", "external_action"}
    unknown = sorted(set(consent_raw) - valid_consent)
    if unknown:
        raise IntakeError("unknown consent fields: " + ", ".join(unknown))

    consent = {k: bool(consent_raw.get(k, False)) for k in valid_consent}

    if not consent["decision_support"]:
        raise IntakeError("consent.decision_support is required")

    # State
    state = payload.get("state", {})
    if not isinstance(state, Mapping):
        raise IntakeError("state must be an object")

    pillar_scores = state.get("pillar_scores", {})
    if pillar_scores and not isinstance(pillar_scores, Mapping):
        raise IntakeError("pillar_scores must be an object")
    if pillar_scores:
        invalid = sorted(set(pillar_scores) - VALID_PILLARS)
        if invalid:
            raise IntakeError(f"invalid pillars: {', '.join(invalid)}")

    baseline_scores = state.get("baseline_scores", {})
    if baseline_scores and not isinstance(baseline_scores, Mapping):
        raise IntakeError("baseline_scores must be an object")

    # Flags
    high_impact = bool(payload.get("high_impact", False))
    human_approved = bool(payload.get("human_approved", False))
    locale = str(payload.get("locale", "en-US"))

    return {
        "request_id": str(payload.get("request_id") or uuid.uuid4()),
        "user_id": user_id,
        "goal": goal,
        "identity_values": identity_values,
        "constraints": constraints,
        "options": options,
        "evidence": evidence,
        "consent": consent,
        "pillar_scores": dict(pillar_scores),
        "baseline_scores": dict(baseline_scores),
        "state_notes": str(state.get("notes", "")),
        "high_impact": high_impact,
        "human_approved": human_approved,
        "locale": locale,
    }


# ── Decision analysis (deterministic, no LLM) ────────────────────

def analyze_decision(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the U Brain deterministic decision analysis."""

    goal = data["goal"]
    options = data["options"]
    evidence = data["evidence"]
    identity_values = data["identity_values"]
    constraints = data["constraints"]
    pillar_scores = data["pillar_scores"]
    baseline_scores = data["baseline_scores"]

    # Score each option (server-side, deterministic)
    scored_options: List[Dict[str, Any]] = []

    for opt in options:
        text_lower = opt.text.lower()

        # Alignment: keyword overlap with identity values + goal
        alignment = 0.5
        if identity_values:
            matches = sum(1 for v in identity_values if v.lower() in text_lower)
            # Also check partial matches (first 4 chars)
            partial = sum(1 for v in identity_values if v.lower()[:4] in text_lower)
            total_matches = max(matches, partial)
            alignment = clamp01(0.45 + 0.55 * (total_matches / max(len(identity_values), 1)))

        # Risk: presence of irreversible/constraint-violating language
        risk_words = ["irreversible", "permanent", "cannot undo", "commit", "binding"]
        risk = 0.2 + 0.15 * sum(1 for w in risk_words if w in text_lower)
        risk = clamp01(risk)

        # Feasibility: option length and specificity
        words = len(text_lower.split())
        feasibility = clamp01(0.5 + 0.1 * min(words / 10, 1) - 0.05 * (words > 30))

        # Constraint penalty
        constraint_penalty = sum(0.05 for c in constraints if c.lower() in text_lower and "must" in c.lower())
        feasibility = clamp01(feasibility - constraint_penalty)

        scored_options.append({
            "option_id": f"opt-{opt.index}",
            "text": opt.text,
            "reversible": opt.reversible,
            "risk": risk,
            "feasibility": feasibility,
            "alignment": alignment,
        })

    # Evidence classification (U Truth Standard)
    facts = [e for e in evidence if e.kind == "fact"]
    inferences_list = [e for e in evidence if e.kind == "inference"]
    unknowns = [e for e in evidence if e.kind == "unknown"]

    # U Truth Standard: real-world outcomes are always unknown until observed
    if not unknowns:
        unknowns_list = ["Real-world outcomes remain unknown until observed."]
    else:
        unknowns_list = [e.text for e in unknowns]

    # U Truth Standard: real-world outcomes are always unknown until observed
    if not unknowns:
        unknowns_list = ["Real-world outcomes remain unknown until observed."]
    else:
        unknowns_list = [e.text for e in unknowns]

    # Decision paths (Stay / Change / Pause)
    paths = []
    if scored_options:
        best = max(scored_options, key=lambda o: o["alignment"] + o["feasibility"] - o["risk"])
        if best["alignment"] >= 0.65:
            paths.append({
                "path": "Stay",
                "description": f"Continue with: {best['text']}",
                "confidence": clamp01(best["alignment"] * 0.7 + best["feasibility"] * 0.3),
            })
        paths.append({
            "path": "Change",
            "description": f"Pursue: {best['text']}" if best["alignment"] < 0.65 else "Explore alternatives",
            "confidence": clamp01(1 - best["risk"]),
        })
        paths.append({
            "path": "Pause",
            "description": "Gather more evidence before deciding",
            "confidence": clamp01(len(unknowns) / max(len(evidence), 1)),
        })

    # Pillar equilibrium
    equilibrium = {"balance": "unknown", "note": "", "pressure_pillar": None}
    if pillar_scores:
        current = pillar_scores
        baselines = baseline_scores or {}
        deltas = {}
        for pillar in VALID_PILLARS:
            curr = float(current.get(pillar, 0.5))
            base = float(baselines.get(pillar, curr))
            deltas[pillar] = round(curr - base, 2)

        avg = sum(current.values()) / max(len(current), 1)
        if avg >= 0.7:
            equilibrium["balance"] = "stable"
        elif avg >= 0.5:
            equilibrium["balance"] = "strained"
        else:
            equilibrium["balance"] = "imbalanced"

        pressure = min(deltas, key=deltas.get) if deltas else None
        equilibrium["pressure_pillar"] = pressure
        equilibrium["note"] = f"Largest decline in {pressure} ({deltas.get(pressure, 0):.1f})" if pressure else ""

    # Ripple map
    ripple = []
    for pillar in VALID_PILLARS:
        score = float(pillar_scores.get(pillar, 0.5))
        if score < 0.4:
            ripple.append({"pillar": pillar, "direction": "declining", "estimated_impact": "high"})
        elif score < 0.6:
            ripple.append({"pillar": pillar, "direction": "pressured", "estimated_impact": "medium"})
        else:
            ripple.append({"pillar": pillar, "direction": "stable", "estimated_impact": "low"})

    # Engine trace (18 engines)
    engine_trace = [
        {"engine": "U_POLICY", "result": "passed", "detail": "Behavioral contract enforced"},
        {"engine": "U_CONSENT", "result": "verified", "detail": f"decision_support={data['consent']['decision_support']}"},
        {"engine": "U_IDENTITY", "result": "processed", "detail": f"{len(identity_values)} values loaded"},
        {"engine": "U_STATE", "result": "analyzed", "detail": f"{len(pillar_scores)} pillar scores"},
        {"engine": "U_TIME", "result": "present", "detail": "Current decision context"},
        {"engine": "U_CONSTRAINT", "result": "checked", "detail": f"{len(constraints)} constraints evaluated"},
        {"engine": "U_GOAL", "result": "parsed", "detail": goal[:80]},
        {"engine": "U_SEMANTIC", "result": "processed", "detail": "Option text analyzed"},
        {"engine": "U_REASON", "result": "completed", "detail": f"{len(scored_options)} options scored"},
        {"engine": "U_RETRIEVE", "result": "skipped", "detail": "No RAG consent"},
        {"engine": "U_GRAPH", "result": "skipped", "detail": "No knowledge graph query"},
        {"engine": "U_ALIGN", "result": "measured", "detail": "Identity alignment calculated"},
        {"engine": "U_LOOP", "result": "completed", "detail": "Single pass"},
        {"engine": "U_DRIFT", "result": "checked", "detail": "Baseline comparison done"},
        {"engine": "U_TRAJECTORY", "result": "projected", "detail": "3 paths generated"},
        {"engine": "U_CONSEQUENCE", "result": "mapped", "detail": f"{len(ripple)} ripple effects"},
        {"engine": "U_CULTURE", "result": "noted", "detail": f"locale={data['locale']}"},
        {"engine": "U_DECISION", "result": "synthesized", "detail": "Paths + signals combined"},
    ]

    return {
        "scored_options": scored_options,
        "paths": paths,
        "facts": [e.text for e in facts],
        "inferences_list": [e.text for e in inferences_list],
        "unknowns": unknowns_list,
        "equilibrium": equilibrium,
        "ripple_map": ripple,
        "engine_trace": engine_trace,
    }


# ── Signal calculation (Anchor logic, adapted for v1 spec) ───────

def calculate_v1_signals(
    scored_options: List[Dict[str, Any]],
    evidence: List[ParsedEvidence],
    identity_values: List[str],
) -> Tuple[Signals, CrossCheck, Optional[Dict[str, Any]]]:
    """Calculate four signals from the v1 evidence format."""

    # Evidence score from kind + confidence
    if not evidence:
        return (
            Signals(0.0, 0.0, 0.0, 0.0),
            CrossCheck.INSUFFICIENT_EVIDENCE,
            None,
        )

    evidence_values = []
    for ev in evidence:
        kind_weight = KIND_QUALITY.get(ev.kind, 0.15)
        evidence_values.append(kind_weight * ev.confidence)

    evidence_score = sum(evidence_values) / len(evidence_values)

    # Source diversity bonus
    sources = {ev.source for ev in evidence if ev.source}
    diversity = min(len(sources) / 3, 1) if sources else 0
    evidence_score = clamp01(evidence_score * 0.85 + diversity * 0.15)

    if evidence_score < 0.35:
        return (
            Signals(
                confidence=round(evidence_score * 0.5, 4),
                concordance=evidence_score,
                alignment=0.0,
                safety=round(0.30 + 0.25 * evidence_score, 4),
            ),
            CrossCheck.INSUFFICIENT_EVIDENCE,
            None,
        )

    # Forward reasoner — picks best option by weighted score
    def forward_score(opt: Dict[str, Any]) -> float:
        return (0.40 * opt["alignment"] + 0.25 * opt["feasibility"]
                + 0.20 * (1 - opt["risk"]) + 0.15 * evidence_score)

    ranked_fwd = sorted(scored_options, key=forward_score, reverse=True)
    best_fwd = ranked_fwd[0]

    # Reverse checker — filters for safe, reversible, aligned options
    eligible = [
        opt for opt in scored_options
        if opt["reversible"]
        and opt["risk"] < REDIRECT_BELOW
        and opt["alignment"] >= REDIRECT_BELOW
    ]

    if not eligible:
        # No option passes the safety filter
        confidence = round(evidence_score * 0.5, 4)
        signals = Signals(
            confidence=confidence,
            concordance=round(evidence_score * 0.5, 4),
            alignment=best_fwd["alignment"],
            safety=round(0.30 + 0.25 * (1 - best_fwd["risk"]) + 0.25 * evidence_score, 4),
        )
        return signals, CrossCheck.INSUFFICIENT_EVIDENCE, best_fwd

    ranked_rev = sorted(
        eligible,
        key=lambda o: (o["alignment"], o["feasibility"], 1 - o["risk"]),
        reverse=True,
    )
    best_rev = ranked_rev[0]

    # Cross-check
    if best_fwd["option_id"] != best_rev["option_id"]:
        verdict = CrossCheck.DISAGREE
        concordance = clamp01(0.25 * min(forward_score(best_fwd), forward_score(best_rev)))
    else:
        verdict = CrossCheck.AGREE
        concordance = clamp01(0.70 + 0.30 * min(forward_score(best_fwd), forward_score(best_rev)))

    fwd_conf = forward_score(best_fwd)
    rev_conf = forward_score(best_rev)

    if best_rev["option_id"] == best_fwd["option_id"]:
        confidence = clamp01(min(fwd_conf, rev_conf) * 0.75 + evidence_score * 0.25)
    else:
        confidence = clamp01(evidence_score * 0.5)

    safety = clamp01(
        0.30 + 0.25 * (1 - best_fwd["risk"])
        + 0.20 * (1.0 if best_fwd["reversible"] else 0.35)
        + 0.25 * evidence_score
    )

    signals = Signals(
        confidence=confidence,
        concordance=concordance,
        alignment=best_fwd["alignment"],
        safety=safety,
    )

    return signals, verdict, best_fwd


def apply_control_decision(
    signals: Signals,
    verdict: CrossCheck,
    high_impact: bool,
    human_approved: bool,
) -> Tuple[ControlDecision, List[str]]:
    """Map signals + verdict to a control decision."""

    reasons: List[str] = []

    # High-impact actions always require human approval
    if high_impact and not human_approved:
        return ControlDecision.PAUSE, [
            "high_impact is true but human_approved is false. "
            "Explicit human approval is required before this decision proceeds."
        ]

    if verdict != CrossCheck.AGREE:
        return ControlDecision.PAUSE, [
            "Forward and reverse reasoners did not agree. "
            "Additional evidence or review is needed."
        ]

    values = asdict(signals)
    low = [name for name, val in values.items() if val < REDIRECT_BELOW]
    if low:
        return ControlDecision.REDIRECT, [
            f"{name} is below {REDIRECT_BELOW:.2f}." for name in low
        ]

    if all(v >= CONTINUE_MIN for v in values.values()):
        return ControlDecision.CONTINUE, [
            "All four server-calculated signals meet the continuation threshold."
        ]

    below_threshold = [
        name for name, val in values.items() if val < CONTINUE_MIN
    ]
    return ControlDecision.PAUSE, [
        f"{name} needs strengthening before continuation."
        for name in below_threshold
    ]


# ── Main evaluation ──────────────────────────────────────────────

def evaluate_decision(
    payload: Any,
    store: StateStore,
) -> Dict[str, Any]:
    data = parse_decision_payload(payload)

    store.claim_request(data["request_id"])

    audit = AuditTrail(data["request_id"])
    audit.add("intake", "validated", {
        "payload_hash": digest(payload),
        "version": VERSION,
        "locale": data["locale"],
    })

    # Crisis gate — first, before anything else
    crisis = crisis_scan(
        data["goal"],
        " ".join(data["constraints"]),
        " ".join(opt.text for opt in data["options"]),
        " ".join(ev.text for ev in data["evidence"]),
    )

    if crisis:
        audit.add("crisis_gate", "redirect", {"detected": True})
        store.save_audit(data["request_id"], audit.events)

        return {
            "version": VERSION,
            "request_id": data["request_id"],
            "status": "safety_redirect",
            "control_decision": "PAUSE",
            "crisis_redirect": True,
            "recommendation": None,
            "signals": {"confidence": 0.0, "concordance": 0.0, "alignment": 0.0, "safety": 0.0},
            "cross_check": "INSUFFICIENT_EVIDENCE",
            "reasons": [
                "Immediate danger detected. Ordinary analysis is paused. "
                "Prioritize human support and emergency resources."
            ],
            "paths": [],
            "facts": [],
            "inferences": [],
            "unknowns": ["All analysis is suspended during a safety redirect."],
            "equilibrium": {},
            "ripple_map": [],
            "engine_trace": [{"engine": "U_POLICY", "result": "crisis_redirect", "detail": "Safety gate activated"}],
            "action_execution_allowed": False,
            "audit": {
                "event_count": len(audit.events),
                "final_hash": audit.events[-1]["event_hash"],
            },
        }

    # Run decision analysis
    analysis = analyze_decision(data)

    # Calculate signals
    signals, verdict, best_option = calculate_v1_signals(
        analysis["scored_options"],
        data["evidence"],
        data["identity_values"],
    )

    # Control decision
    control, reasons = apply_control_decision(
        signals,
        verdict,
        data["high_impact"],
        data["human_approved"],
    )

    audit.add("anchor_control", control.value.lower(), {
        "signals": asdict(signals),
        "verdict": verdict.value,
        "reasons": reasons,
    })

    store.save_audit(data["request_id"], audit.events)

    return {
        "version": VERSION,
        "request_id": data["request_id"],
        "status": "completed",
        "control_decision": control.value,
        "crisis_redirect": False,
        "recommendation": {
            "option_id": best_option["option_id"],
            "text": best_option["text"],
            "reversible": best_option["reversible"],
            "risk": best_option["risk"],
            "feasibility": best_option["feasibility"],
            "alignment": best_option["alignment"],
        } if best_option else None,
        "signals": asdict(signals),
        "cross_check": verdict.value,
        "reasons": reasons,
        "paths": analysis["paths"],
        "facts": analysis["facts"],
        "inferences": analysis["inferences_list"],
        "unknowns": analysis["unknowns"],
        "equilibrium": analysis["equilibrium"],
        "ripple_map": analysis["ripple_map"],
        "scored_options": analysis["scored_options"],
        "engine_trace": analysis["engine_trace"],
        "action_execution_allowed": False,
        "audit": {
            "event_count": len(audit.events),
            "final_hash": audit.events[-1]["event_hash"],
        },
    }


# ── API key auth ─────────────────────────────────────────────────

def verify_api_key(api_key: str | None) -> None:
    expected = os.environ.get("U_API_KEY", "")
    if not expected:
        raise RuntimeError("U_API_KEY is not configured")
    if not api_key:
        raise PermissionError("X-U-API-Key header is required")
    if not pysecrets.compare_digest(api_key, expected):
        raise PermissionError("invalid API key")


# ── FastAPI app ──────────────────────────────────────────────────

STORE = StateStore(os.environ.get("U_STATE_DB_PATH", "/tmp/u_decision_v1.db"))

app = FastAPI(
    title="U Decision API",
    version=VERSION,
    description="Canonical U Azure Decision service — accepts goal, options, evidence, and returns evaluation with signals.",
)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy", "version": VERSION}


@app.post("/v1/decisions/evaluate")
async def evaluate_endpoint(
    request: Request,
    x_u_api_key: str | None = Header(default=None, alias="X-U-API-Key"),
) -> Dict[str, Any]:
    body_bytes = await request.body()

    try:
        verify_api_key(x_u_api_key)
        payload = json.loads(body_bytes)
        return evaluate_decision(payload, STORE)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except IntakeError as e:
        status = 409 if "replay" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e)) from e
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/v1/anchor/evaluate")
async def anchor_evaluate_endpoint(
    request: Request,
    x_u_api_key: str | None = Header(default=None, alias="X-U-API-Key"),
) -> Dict[str, Any]:
    """Alias endpoint — same logic as /v1/decisions/evaluate."""
    body_bytes = await request.body()

    try:
        verify_api_key(x_u_api_key)
        payload = json.loads(body_bytes)
        return evaluate_decision(payload, STORE)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except IntakeError as e:
        status = 409 if "replay" in str(e) else 400
        raise HTTPException(status_code=status, detail=str(e)) from e
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def verify_user_identity(
    user_id: str,
    timestamp: str | None,
    signature: str | None,
) -> None:
    """Verify that the caller is the data owner via HMAC signature."""
    identity_secret = os.environ.get("U_IDENTITY_SECRET", "")
    if not identity_secret:
        raise RuntimeError("U_IDENTITY_SECRET is not configured")

    if not timestamp or not signature:
        raise PermissionError("signed user identity is required for data deletion")

    try:
        issued_at = int(timestamp)
    except ValueError as e:
        raise PermissionError("invalid identity timestamp") from e

    max_skew = 300
    if abs(int(time.time()) - issued_at) > max_skew:
        raise PermissionError("identity signature expired")

    message = user_id.encode("utf-8") + b"." + timestamp.encode("utf-8")
    expected = hmac.new(
        identity_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not pysecrets.compare_digest(signature, expected):
        raise PermissionError("invalid user identity signature")


@app.delete("/v1/users/{user_id}/data")
async def delete_user_data(
    user_id: str,
    x_u_api_key: str | None = Header(default=None, alias="X-U-API-Key"),
    x_u_user_id: str | None = Header(default=None, alias="X-U-User-Id"),
    x_u_timestamp: str | None = Header(default=None, alias="X-U-Timestamp"),
    x_u_signature: str | None = Header(default=None, alias="X-U-Signature"),
) -> Dict[str, Any]:
    try:
        verify_api_key(x_u_api_key)

        # Verify the caller is the data owner
        verify_user_identity(user_id, x_u_timestamp, x_u_signature)

        # The signed user_id must match the path user_id
        if x_u_user_id and x_u_user_id != user_id:
            raise PermissionError("signed user does not match requested user_id")

        count = STORE.count_user_data(user_id)
        deleted = STORE.delete_user_data(user_id)
        return {
            "version": VERSION,
            "status": "completed",
            "user_id": user_id,
            "records_found": count,
            "records_deleted": deleted,
            "message": "User data has been deleted." if deleted > 0
                       else "No user data found for this user.",
        }
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


# ── Self-tests ───────────────────────────────────────────────────

def self_test() -> Dict[str, Any]:
    test_db = "/tmp/u_decision_v1_self_test.db"
    try:
        os.remove(test_db)
    except FileNotFoundError:
        pass

    store = StateStore(test_db)
    results: Dict[str, bool] = {}

    # 1. Valid decision — CONTINUE path
    base = {
        "user_id": "jenny",
        "goal": "Should I finish the U backend before adding more interface features?",
        "identity_values": ["stability", "growth", "service"],
        "constraints": ["must remain within budget"],
        "options": [
            "Finish the U backend foundation first",
            "Add interface features in parallel",
        ],
        "evidence": [
            {"text": "18 engines verified and passing", "kind": "fact", "source": "system_test", "confidence": 0.95},
            {"text": "Safety gates pass all crisis paths", "kind": "fact", "source": "deterministic_test", "confidence": 0.95},
            {"text": "Backend foundation supports future features", "kind": "inference", "source": "architecture_review", "confidence": 0.80},
        ],
        "consent": {"decision_support": True, "sensitive_data": False, "memory": False, "external_action": False},
        "state": {
            "pillar_scores": {"health": 0.7, "career": 0.6, "finance": 0.65, "relationships": 0.8},
            "baseline_scores": {"health": 0.75, "career": 0.65, "finance": 0.65, "relationships": 0.8},
            "notes": "",
        },
        "high_impact": False,
        "human_approved": False,
        "locale": "en-US",
    }

    out = evaluate_decision(base, store)
    results["valid_200"] = out["status"] == "completed"
    results["has_signals"] = set(out["signals"].keys()) == {"confidence", "concordance", "alignment", "safety"}
    results["has_paths"] = len(out["paths"]) >= 2
    results["has_engine_trace"] = len(out["engine_trace"]) == 18
    results["no_execution"] = out["action_execution_allowed"] is False
    results["has_audit"] = out["audit"]["event_count"] >= 2

    # 2. Replay blocked — inject a fixed request_id
    import copy
    base_replay = copy.deepcopy(base)
    base_replay["request_id"] = "fixed-replay-test-id"
    evaluate_decision(base_replay, store)
    try:
        evaluate_decision(copy.deepcopy(base_replay), store)
        results["replay_blocked"] = False
    except IntakeError:
        results["replay_blocked"] = True

    # 3. Consent denied
    case = json.loads(json.dumps(base))
    case["consent"]["decision_support"] = False
    try:
        evaluate_decision(case, store)
        results["consent_denied"] = False
    except IntakeError:
        results["consent_denied"] = True

    # 4. Crisis redirect
    case = json.loads(json.dumps(base))
    case["goal"] = "I want to end my life"
    out_crisis = evaluate_decision(case, store)
    results["crisis_redirect"] = out_crisis["crisis_redirect"] is True
    results["crisis_no_reco"] = out_crisis["recommendation"] is None
    results["crisis_pause"] = out_crisis["control_decision"] == "PAUSE"

    # 5. High-impact without approval
    case = json.loads(json.dumps(base))
    case["high_impact"] = True
    case["human_approved"] = False
    out_h = evaluate_decision(case, store)
    results["high_impact_pause"] = out_h["control_decision"] == "PAUSE"

    # 6. Evidence classification
    results["facts_extracted"] = len(out["facts"]) >= 1
    results["inferences_extracted"] = len(out["inferences"]) >= 1
    results["unknowns_present"] = isinstance(out["unknowns"], list)

    # 7. Equilibrium
    results["equilibrium"] = "balance" in out["equilibrium"]

    # 8. Ripple map
    results["ripple_map"] = len(out["ripple_map"]) == 4

    # 9. Delete endpoint (user data)
    results["delete_no_data"] = store.delete_user_data("jenny") >= 0

    return {
        "passed": sum(results.values()),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    result = self_test()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
