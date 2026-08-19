"""U Anchor Navigator v0.2 — hardened Azure Python service.

Required Azure environment variables:
    U_SERVICE_TOKEN
    U_IDENTITY_SECRET
    U_STATE_DB_PATH

Base44 submits raw options and evidence—not signal scores. Azure calculates
all four signals, enforces cross-check agreement, blocks request replay and
persists the audit chain.

This endpoint evaluates decisions only. It cannot execute external actions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from fastapi import FastAPI, Header, HTTPException, Request


VERSION = "0.2.0"
CONTINUE_MIN = 0.85
REDIRECT_BELOW = 0.65
MAX_EVIDENCE = 50
MAX_OPTIONS = 12
MAX_CLOCK_SKEW_SECONDS = 300


# Evidence quality is assigned by Azure policy.
# Base44 cannot assign its own evidence strength.

SOURCE_QUALITY = {
    "system_test": 0.95,
    "deterministic_test": 0.95,
    "verified_document": 0.90,
    "user_confirmed": 0.75,
    "observation": 0.70,
    "journal": 0.55,
    "unverified": 0.35,
}


class Decision(str, Enum):
    CONTINUE = "CONTINUE"
    PAUSE = "PAUSE"
    REDIRECT = "REDIRECT"


class Verdict(str, Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class IntakeError(ValueError):
    pass


@dataclass(frozen=True)
class Option:
    option_id: str
    title: str
    reversible: bool
    risk: float
    feasibility: float
    alignment: float


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    claim: str
    source_type: str
    user_confirmed: bool


@dataclass(frozen=True)
class ReasonerResult:
    option_id: str
    confidence: float


@dataclass(frozen=True)
class Signals:
    confidence: float
    concordance: float
    alignment: float
    safety: float


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest(value: Any) -> str:
    return hashlib.sha256(
        canonical(value).encode("utf-8")
    ).hexdigest()


def score(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise IntakeError(
            f"{name} must be a number from 0 to 1"
        )

    if not isinstance(value, (int, float)):
        raise IntakeError(
            f"{name} must be a number from 0 to 1"
        )

    result = float(value)

    if not 0 <= result <= 1:
        raise IntakeError(
            f"{name} must be between 0 and 1"
        )

    return round(result, 4)


class StateStore:
    """Persistent replay and audit storage."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.lock = Lock()

        with self._connect() as database:
            database.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL
                )
                """
            )

            database.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    request_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    PRIMARY KEY(request_id, sequence)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def claim_request(
        self,
        request_id: str,
    ) -> None:
        with self.lock:
            with self._connect() as database:
                try:
                    database.execute(
                        """
                        INSERT INTO requests (
                            request_id,
                            created_at
                        )
                        VALUES (?, ?)
                        """,
                        (
                            request_id,
                            int(time.time()),
                        ),
                    )

                except sqlite3.IntegrityError as error:
                    raise IntakeError(
                        "request_id replay blocked"
                    ) from error

    def save_audit(
        self,
        request_id: str,
        events: Sequence[Mapping[str, Any]],
    ) -> None:
        records = [
            (
                request_id,
                sequence,
                canonical(event),
                event["event_hash"],
            )
            for sequence, event in enumerate(events)
        ]

        with self.lock:
            with self._connect() as database:
                database.executemany(
                    """
                    INSERT INTO audit_events (
                        request_id,
                        sequence,
                        event_json,
                        event_hash
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    records,
                )


class AuditTrail:
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.events: List[Dict[str, Any]] = []

    def add(
        self,
        stage: str,
        status: str,
        details: Mapping[str, Any],
    ) -> None:
        prior_hash = (
            self.events[-1]["event_hash"]
            if self.events
            else "GENESIS"
        )

        body = {
            "stage": stage,
            "status": status,
            "details": dict(details),
            "prior_hash": prior_hash,
        }

        self.events.append({
            **body,
            "event_hash": digest(body),
        })


def strict_consent(
    value: Any,
) -> Dict[str, bool]:
    fields = (
        "analyze",
        "simulate",
        "external_action",
        "write_memory",
        "outcome_learning",
    )

    if not isinstance(value, Mapping):
        raise IntakeError(
            "consent must be an object"
        )

    unknown = sorted(
        set(value) - set(fields)
    )

    if unknown:
        raise IntakeError(
            "unknown consent fields: "
            + ", ".join(unknown)
        )

    invalid = sorted(
        key
        for key, item in value.items()
        if not isinstance(item, bool)
    )

    if invalid:
        raise IntakeError(
            "consent values must be Boolean: "
            + ", ".join(invalid)
        )

    return {
        key: value.get(key, False)
        for key in fields
    }


def parse_payload(
    payload: Any,
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise IntakeError(
            "payload must be an object"
        )

    required = (
        "request_id",
        "user_id",
        "consent",
        "options",
        "evidence",
    )

    missing = [
        key
        for key in required
        if key not in payload
    ]

    if missing:
        raise IntakeError(
            "missing required fields: "
            + ", ".join(missing)
        )

    request_id = str(
        payload["request_id"]
    ).strip()

    user_id = str(
        payload["user_id"]
    ).strip()

    if not request_id:
        raise IntakeError(
            "request_id cannot be empty"
        )

    if not user_id:
        raise IntakeError(
            "user_id cannot be empty"
        )

    options_raw = payload["options"]
    evidence_raw = payload["evidence"]

    if not isinstance(options_raw, list):
        raise IntakeError(
            "options must be an array"
        )

    if not 1 <= len(options_raw) <= MAX_OPTIONS:
        raise IntakeError(
            "options must contain 1–12 items"
        )

    if not isinstance(evidence_raw, list):
        raise IntakeError(
            "evidence must be an array"
        )

    if len(evidence_raw) > MAX_EVIDENCE:
        raise IntakeError(
            "evidence must contain 0–50 items"
        )

    options: List[Option] = []

    for item in options_raw:
        if not isinstance(item, Mapping):
            raise IntakeError(
                "each option must be an object"
            )

        if "option_id" not in item:
            raise IntakeError(
                "each option requires option_id"
            )

        reversible = item.get(
            "reversible",
            True,
        )

        if not isinstance(reversible, bool):
            raise IntakeError(
                "reversible must be Boolean"
            )

        options.append(
            Option(
                option_id=str(
                    item["option_id"]
                ),
                title=str(
                    item.get(
                        "title",
                        item["option_id"],
                    )
                ),
                reversible=reversible,
                risk=score(
                    "risk",
                    item.get("risk", 0.5),
                ),
                feasibility=score(
                    "feasibility",
                    item.get(
                        "feasibility",
                        0.5,
                    ),
                ),
                alignment=score(
                    "alignment",
                    item.get(
                        "alignment",
                        0.5,
                    ),
                ),
            )
        )

    option_ids = [
        option.option_id
        for option in options
    ]

    if len(set(option_ids)) != len(option_ids):
        raise IntakeError(
            "option_id values must be unique"
        )

    evidence: List[Evidence] = []

    for item in evidence_raw:
        if not isinstance(item, Mapping):
            raise IntakeError(
                "each evidence item must be an object"
            )

        for field_name in (
            "evidence_id",
            "claim",
        ):
            if field_name not in item:
                raise IntakeError(
                    f"evidence is missing {field_name}"
                )

        user_confirmed = item.get(
            "user_confirmed",
            False,
        )

        if not isinstance(
            user_confirmed,
            bool,
        ):
            raise IntakeError(
                "user_confirmed must be Boolean"
            )

        evidence.append(
            Evidence(
                evidence_id=str(
                    item["evidence_id"]
                ),
                claim=str(
                    item["claim"]
                ),
                source_type=str(
                    item.get(
                        "source_type",
                        "unverified",
                    )
                ),
                user_confirmed=user_confirmed,
            )
        )

    state = payload.get(
        "state",
        {},
    )

    if not isinstance(state, Mapping):
        raise IntakeError(
            "state must be an object"
        )

    for key in (
        "immediate_danger",
        "request_for_diagnosis",
    ):
        if (
            key in state
            and not isinstance(state[key], bool)
        ):
            raise IntakeError(
                f"{key} must be Boolean"
            )

    return {
        "request_id": request_id,
        "user_id": user_id,
        "consent": strict_consent(
            payload["consent"]
        ),
        "options": options,
        "evidence": evidence,
        "state": dict(state),
    }


def evidence_score(
    items: Sequence[Evidence],
) -> float:
    if not items:
        return 0.0

    values = []

    for item in items:
        source_quality = SOURCE_QUALITY.get(
            item.source_type,
            SOURCE_QUALITY["unverified"],
        )

        confirmation_factor = (
            1.0
            if item.user_confirmed
            else 0.8
        )

        values.append(
            source_quality
            * confirmation_factor
        )

    source_diversity = len({
        item.source_type
        for item in items
    })

    diversity = min(
        source_diversity / 3,
        1,
    )

    result = (
        sum(values) / len(values)
        * 0.85
        + diversity * 0.15
    )

    return round(
        min(1.0, result),
        4,
    )


def forward_reasoner(
    options: Sequence[Option],
    evidence_value: float,
) -> ReasonerResult:
    ranked = sorted(
        options,
        key=lambda option: (
            0.40 * option.alignment
            + 0.25 * option.feasibility
            + 0.20 * (1 - option.risk)
            + 0.15 * evidence_value
        ),
        reverse=True,
    )

    best = ranked[0]

    confidence = round(
        0.40 * best.alignment
        + 0.25 * best.feasibility
        + 0.20 * (1 - best.risk)
        + 0.15 * evidence_value,
        4,
    )

    return ReasonerResult(
        option_id=best.option_id,
        confidence=confidence,
    )


def reverse_checker(
    options: Sequence[Option],
    evidence_value: float,
) -> ReasonerResult:
    eligible = [
        option
        for option in options
        if option.reversible
        and option.risk < REDIRECT_BELOW
        and option.alignment >= REDIRECT_BELOW
        and evidence_value >= 0.35
    ]

    if not eligible:
        return ReasonerResult(
            option_id="",
            confidence=0.0,
        )

    ranked = sorted(
        eligible,
        key=lambda option: (
            option.alignment,
            option.feasibility,
            1 - option.risk,
        ),
        reverse=True,
    )

    best = ranked[0]

    confidence = round(
        0.45 * best.alignment
        + 0.25 * best.feasibility
        + 0.20 * (1 - best.risk)
        + 0.10 * evidence_value,
        4,
    )

    return ReasonerResult(
        option_id=best.option_id,
        confidence=confidence,
    )


def calculate_signals(
    data: Mapping[str, Any],
) -> Tuple[
    Signals,
    Verdict,
    Option,
]:
    evidence_value = evidence_score(
        data["evidence"]
    )

    forward = forward_reasoner(
        data["options"],
        evidence_value,
    )

    reverse = reverse_checker(
        data["options"],
        evidence_value,
    )

    selected = next(
        option
        for option in data["options"]
        if option.option_id == forward.option_id
    )

    if (
        evidence_value < 0.35
        or not reverse.option_id
    ):
        verdict = (
            Verdict.INSUFFICIENT_EVIDENCE
        )
        concordance = evidence_value

    elif (
        forward.option_id
        != reverse.option_id
    ):
        verdict = Verdict.DISAGREE

        concordance = round(
            0.25
            * min(
                forward.confidence,
                reverse.confidence,
            ),
            4,
        )

    else:
        verdict = Verdict.AGREE

        concordance = round(
            0.70
            + 0.30
            * min(
                forward.confidence,
                reverse.confidence,
            ),
            4,
        )

    if reverse.option_id:
        confidence = round(
            min(
                forward.confidence,
                reverse.confidence,
            )
            * 0.75
            + evidence_value * 0.25,
            4,
        )
    else:
        confidence = round(
            evidence_value * 0.5,
            4,
        )

    safety = round(
        0.30
        + 0.25 * (1 - selected.risk)
        + 0.20 * (
            1.0
            if selected.reversible
            else 0.35
        )
        + 0.25 * evidence_value,
        4,
    )

    signals = Signals(
        confidence=confidence,
        concordance=min(
            1.0,
            concordance,
        ),
        alignment=selected.alignment,
        safety=min(
            1.0,
            safety,
        ),
    )

    return signals, verdict, selected


def apply_control(
    signals: Signals,
    verdict: Verdict,
) -> Tuple[Decision, List[str]]:
    if verdict != Verdict.AGREE:
        return (
            Decision.PAUSE,
            [
                "Independent reasoners require "
                "additional review or evidence."
            ],
        )

    values = asdict(signals)

    low_signals = [
        name
        for name, value in values.items()
        if value < REDIRECT_BELOW
    ]

    if low_signals:
        return (
            Decision.REDIRECT,
            [
                f"{name} is below "
                f"{REDIRECT_BELOW:.2f}."
                for name in low_signals
            ],
        )

    if all(
        value >= CONTINUE_MIN
        for value in values.values()
    ):
        return (
            Decision.CONTINUE,
            [
                "All four server-calculated signals "
                "meet the prototype continuation threshold."
            ],
        )

    return (
        Decision.PAUSE,
        [
            f"{name} needs strengthening "
            "before continuation."
            for name, value in values.items()
            if value < CONTINUE_MIN
        ]
    )


def evaluate(
    payload: Any,
    store: StateStore,
) -> Dict[str, Any]:
    data = parse_payload(payload)

    store.claim_request(
        data["request_id"]
    )

    audit = AuditTrail(
        data["request_id"]
    )

    audit.add(
        "intake",
        "validated",
        {
            "payload_hash": digest(payload),
            "version": VERSION,
        },
    )

    pause_reasons: List[str] = []

    if not data["consent"]["analyze"]:
        pause_reasons.append(
            "Analysis consent is required."
        )

    if not data["consent"]["simulate"]:
        pause_reasons.append(
            "Simulation consent is required."
        )

    if not data["evidence"]:
        pause_reasons.append(
            "Evidence is required before Anchor "
            "can evaluate a direction."
        )

    crisis_redirect = (
        data["state"].get(
            "immediate_danger"
        ) is True
    )

    diagnosis_request = (
        data["state"].get(
            "request_for_diagnosis"
        ) is True
    )

    if crisis_redirect:
        pause_reasons.append(
            "Immediate danger requires the separate "
            "crisis pathway and human support."
        )

    if diagnosis_request:
        pause_reasons.append(
            "U does not diagnose people or conditions."
        )

    selected = None

    if pause_reasons:
        decision = Decision.PAUSE
        reasons = pause_reasons
        signals = Signals(
            confidence=0.0,
            concordance=0.0,
            alignment=0.0,
            safety=0.0,
        )
        verdict = (
            Verdict.INSUFFICIENT_EVIDENCE
        )

    else:
        (
            signals,
            verdict,
            selected,
        ) = calculate_signals(data)

        decision, reasons = apply_control(
            signals,
            verdict,
        )

    audit.add(
        "anchor_control",
        decision.value.lower(),
        {
            "signals": asdict(signals),
            "verdict": verdict.value,
            "reasons": reasons,
        },
    )

    store.save_audit(
        data["request_id"],
        audit.events,
    )

    facts = [
        item.claim
        for item in data["evidence"]
        if item.user_confirmed
    ]

    unknowns = [
        item.claim
        for item in data["evidence"]
        if not item.user_confirmed
    ]

    if not unknowns:
        unknowns = [
            "Real-world outcomes remain "
            "unknown until observed."
        ]

    return {
        "version": VERSION,
        "request_id": data["request_id"],
        "status": "completed",
        "control_decision": decision.value,
        "crisis_redirect": crisis_redirect,
        "recommendation": (
            asdict(selected)
            if selected
            and not crisis_redirect
            else None
        ),
        "signals": asdict(signals),
        "cross_check": verdict.value,
        "reasons": reasons,
        "facts": facts,
        "inferences": [
            "Signals were calculated by Azure "
            "and remain scenario estimates."
        ],
        "unknowns": unknowns,

        # Evaluation and execution are separated.
        "action_execution_allowed": False,

        "audit": {
            "event_count": len(
                audit.events
            ),
            "final_hash": (
                audit.events[-1]["event_hash"]
            ),
        },
    }


def verify_headers(
    service_token: str | None,
    user_id: str | None,
    timestamp: str | None,
    signature: str | None,
    body: bytes,
) -> None:
    expected_token = os.environ.get(
        "U_SERVICE_TOKEN",
        "",
    )

    identity_secret = os.environ.get(
        "U_IDENTITY_SECRET",
        "",
    )

    if (
        not expected_token
        or not identity_secret
    ):
        raise RuntimeError(
            "service authentication is not configured"
        )

    if not service_token:
        raise PermissionError(
            "invalid service token"
        )

    if not hmac.compare_digest(
        service_token,
        expected_token,
    ):
        raise PermissionError(
            "invalid service token"
        )

    if (
        not user_id
        or not timestamp
        or not signature
    ):
        raise PermissionError(
            "signed user identity is required"
        )

    try:
        issued_at = int(timestamp)
    except ValueError as error:
        raise PermissionError(
            "invalid identity timestamp"
        ) from error

    if (
        abs(int(time.time()) - issued_at)
        > MAX_CLOCK_SKEW_SECONDS
    ):
        raise PermissionError(
            "identity signature expired"
        )

    message = (
        user_id.encode("utf-8")
        + b"."
        + timestamp.encode("utf-8")
        + b"."
        + body
    )

    expected_signature = hmac.new(
        identity_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        signature,
        expected_signature,
    ):
        raise PermissionError(
            "invalid user identity signature"
        )


STORE = StateStore(
    os.environ.get(
        "U_STATE_DB_PATH",
        "/tmp/u_anchor.db",
    )
)


app = FastAPI(
    title="U Anchor Navigator",
    version=VERSION,
)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {
        "status": "healthy",
        "version": VERSION,
    }


@app.post("/api/u/anchor/evaluate")
async def anchor_endpoint(
    request: Request,
    x_u_service_token: str | None = Header(
        default=None
    ),
    x_u_user_id: str | None = Header(
        default=None
    ),
    x_u_timestamp: str | None = Header(
        default=None
    ),
    x_u_signature: str | None = Header(
        default=None
    ),
) -> Dict[str, Any]:
    body = await request.body()

    try:
        verify_headers(
            service_token=x_u_service_token,
            user_id=x_u_user_id,
            timestamp=x_u_timestamp,
            signature=x_u_signature,
            body=body,
        )

        payload = json.loads(body)

        if (
            str(payload.get("user_id", ""))
            != x_u_user_id
        ):
            raise PermissionError(
                "signed user does not match payload user"
            )

        return evaluate(
            payload,
            STORE,
        )

    except PermissionError as error:
        raise HTTPException(
            status_code=401,
            detail=str(error),
        ) from error

    except IntakeError as error:
        status_code = (
            409
            if "replay" in str(error)
            else 400
        )

        raise HTTPException(
            status_code=status_code,
            detail=str(error),
        ) from error

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


def self_test() -> Dict[str, Any]:
    test_database = (
        "/tmp/u_anchor_self_test.db"
    )

    try:
        os.remove(test_database)
    except FileNotFoundError:
        pass

    store = StateStore(
        test_database
    )

    base = {
        "request_id": "test-1",
        "user_id": "u-founder",
        "consent": {
            "analyze": True,
            "simulate": True
        },
        "options": [
            {
                "option_id": "integrate",
                "title": "Integrate Anchor",
                "reversible": True,
                "risk": 0.05,
                "feasibility": 0.98,
                "alignment": 0.98
            }
        ],
        "evidence": [
            {
                "evidence_id": "e1",
                "claim": "Architecture is modular",
                "source_type": "system_test",
                "user_confirmed": True
            },
            {
                "evidence_id": "e2",
                "claim": "Safety gates pass",
                "source_type": "deterministic_test",
                "user_confirmed": True
            },
            {
                "evidence_id": "e3",
                "claim": "Contract is validated",
                "source_type": "verified_document",
                "user_confirmed": True
            }
        ],
        "state": {}
    }

    results: Dict[str, bool] = {}

    output = evaluate(
        base,
        store,
    )

    results["server_signals"] = (
        set(output["signals"])
        == {
            "confidence",
            "concordance",
            "alignment",
            "safety",
        }
    )

    results["continue"] = (
        output["control_decision"]
        == "CONTINUE"
    )

    try:
        evaluate(base, store)
        results["replay"] = False
    except IntakeError:
        results["replay"] = True

    case = json.loads(
        json.dumps(base)
    )
    case["request_id"] = "test-2"
    case["consent"]["simulate"] = False

    results["consent_pause"] = (
        evaluate(
            case,
            store,
        )["control_decision"]
        == "PAUSE"
    )

    case = json.loads(
        json.dumps(base)
    )
    case["request_id"] = "test-3"
    case["state"] = {
        "immediate_danger": True
    }

    crisis_result = evaluate(
        case,
        store,
    )

    results["crisis"] = (
        crisis_result["crisis_redirect"]
        and crisis_result["recommendation"]
        is None
    )

    case = json.loads(
        json.dumps(base)
    )
    case["request_id"] = "test-4"
    case["evidence"] = []

    results["evidence_pause"] = (
        evaluate(
            case,
            store,
        )["control_decision"]
        == "PAUSE"
    )

    results["no_execution"] = (
        output["action_execution_allowed"]
        is False
    )

    return {
        "passed": sum(
            results.values()
        ),
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    test_result = self_test()

    print(
        json.dumps(
            test_result,
            indent=2,
        )
    )

    raise SystemExit(
        0
        if (
            test_result["passed"]
            == test_result["total"]
        )
        else 1
    )
