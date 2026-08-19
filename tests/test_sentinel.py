"""Tests for the Symbiotic Sentinel cognitive governance layer."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.sentinel import sentinel, SentinelResult
from app.engines import Context, safety, CRISIS
from app.models import DecisionRequest, Consent

def test_sentinel_initialization():
    """Sentinel loads the behavioral contract correctly."""
    assert sentinel.contract_version == "1.0.0"
    assert len(sentinel.principles) >= 8
    assert len(sentinel.decision_paths) == 3
    assert "low" in sentinel.risk_levels
    assert "crisis" in sentinel.risk_levels
    assert sentinel.max_words == 450

def test_cognitive_directive_structure():
    """The cognitive directive schema contains all required layers."""
    req = DecisionRequest(
        title="Career transition decision",
        situation="I'm considering leaving my job to start a business",
        desired_outcome="Confident decision with managed risk",
        consent=Consent(analyze=True),
    )
    ctx = Context(req)
    safety(ctx)
    
    directive = sentinel.build_cognitive_directive(
        ctx=ctx,
        engine_outputs={"engines_run": 18},
        consent_state={"analyze": True, "memory": False, "research": False, "external_actions": False, "sensitive_data": False},
        options=[{"name": "stay", "score": 0.58, "summary": "Keep current course"}],
        pillars={"career": {"relevance": 0.8, "signal": "primary"}},
        trajectory={"direction": "change", "confidence": 0.64, "dominant_driver": "career"},
        ripple=[{"pillar": "career", "estimated_impact": 0.8}],
        equilibrium={"balance": 0.75, "pressure_pillar": "career"},
    )
    
    # All layers must be present
    assert "COGNITIVE DIRECTIVE SCHEMA" in directive
    assert "COGNITIVE CONSTRAINTS" in directive
    assert "CONSENT BOUNDARIES" in directive
    assert "SAFETY REFLEX" in directive
    assert "ENGINE LENSES" in directive
    assert "RESPONSE COGNITIVE FRAMEWORK" in directive
    
    # Consent boundaries must reflect state
    assert "ANALYSIS: GRANTED" in directive
    assert "MEMORY: BLOCKED" in directive
    assert "RESEARCH: BLOCKED" in directive

def test_safety_reflex_crisis_redirect():
    """When crisis is detected, the directive includes crisis redirect."""
    req = DecisionRequest(
        title="I want to end my life",
        situation="I can't take it anymore, I want to die",
        desired_outcome="Relief from pain",
        consent=Consent(analyze=True),
    )
    ctx = Context(req)
    safety(ctx)  # This should set risk to crisis
    
    assert ctx.risk == "crisis"
    
    directive = sentinel.build_cognitive_directive(
        ctx=ctx,
        consent_state={"analyze": True, "memory": False, "research": False, "external_actions": False, "sensitive_data": False},
    )
    
    assert "CRISIS REDIRECT" in directive
    assert "safety" in directive.lower()

def test_govern_output_crisis_detection():
    """Sentinel detects crisis patterns in generated output."""
    result = sentinel.govern_output(
        "I understand you want to commit suicide. Let's think about this.",
        confidence=0.8,
        risk="low"
    )
    
    assert result.redirected
    assert "crisis_redirect" in result.cognitive_state
    assert "immediate danger" in result.governed_output

def test_govern_output_diagnosis_detection():
    """Sentinel detects and strips diagnostic language."""
    result = sentinel.govern_output(
        "Based on what you've described, you have depression and should seek treatment for your condition.",
        confidence=0.7,
        risk="low"
    )
    
    assert result.redirected
    all_violations = " ".join(result.violations).lower()
    assert "diagnos" in all_violations

def test_govern_output_false_certainty():
    """Sentinel detects and qualifies false certainty."""
    result = sentinel.govern_output(
        "This will definitely work and is guaranteed to succeed.",
        confidence=0.9,
        risk="low"
    )
    
    assert "false certainty" in " ".join(result.violations).lower()
    assert "this may" in result.governed_output

def test_govern_output_word_limit():
    """Sentinel enforces the 450-word limit."""
    long_text = " ".join(["word"] * 500)
    result = sentinel.govern_output(long_text, confidence=0.7, risk="low")
    
    assert "Word limit exceeded" in " ".join(result.violations)
    assert len(result.governed_output.split()) <= 450

def test_govern_output_nominal():
    """Clean output passes governance without violations."""
    clean_output = (
        "I understand you're considering a career change. "
        "Let's explore stay, change, and pause options. "
        "Staying preserves stability while change pursues your goal. "
        "Pause creates thinking room. "
        "Consider the most reversible first step."
    )
    result = sentinel.govern_output(clean_output, confidence=0.7, risk="low")
    
    # Should be governed but not redirected
    assert result.governed
    assert not result.redirected
    assert result.cognitive_state in ("nominal", "nominal_with_flags")

def test_sentinel_status():
    """Sentinel status reports the correct governance mode."""
    status = sentinel.status()
    
    assert status["sentinel"] == "Symbiotic Sentinel"
    assert "pre_conditioning" in status["cognitive_layers"]
    assert "embedded_governance" in status["cognitive_layers"]
    assert "real_time_monitoring" in status["cognitive_layers"]
    assert "L5" in status["autonomy_level"]
    assert status["governance_mode"] == "embedded_cognitive_directive"

def test_consent_boundary_embedding():
    """Consent state shapes the cognitive directive's perimeter."""
    req = DecisionRequest(
        title="Financial decision",
        situation="Should I invest my savings?",
        desired_outcome="Financial security",
        consent=Consent(analyze=True, memory=True, research=True),
    )
    ctx = Context(req)
    safety(ctx)
    
    directive = sentinel.build_cognitive_directive(
        ctx=ctx,
        consent_state={"analyze": True, "memory": True, "research": True, "external_actions": False, "sensitive_data": False},
    )
    
    assert "MEMORY: GRANTED" in directive
    assert "RESEARCH: GRANTED" in directive
    assert "EXTERNAL ACTIONS: BLOCKED" in directive

def test_engine_lens_layer():
    """Engine outputs become cognitive lenses in the directive."""
    req = DecisionRequest(
        title="Health decision",
        situation="I need to improve my sleep schedule",
        desired_outcome="Better energy and focus",
        pillars=["health"],
        consent=Consent(analyze=True),
    )
    ctx = Context(req)
    safety(ctx)
    
    directive = sentinel.build_cognitive_directive(
        ctx=ctx,
        engine_outputs={"engines_run": 18},
        consent_state={"analyze": True, "memory": False, "research": False, "external_actions": False, "sensitive_data": False},
        pillars={"health": {"relevance": 0.85, "signal": "primary"}},
        trajectory={"direction": "change", "confidence": 0.7, "dominant_driver": "health"},
        ripple=[{"pillar": "health", "estimated_impact": 0.85}],
        equilibrium={"balance": 0.6, "pressure_pillar": "health"},
    )
    
    assert "HEALTH: relevance=0.85" in directive
    assert "Direction: change" in directive
    assert "Balance: 0.60" in directive

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"  ✅ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {test.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} sentinel tests passed")
