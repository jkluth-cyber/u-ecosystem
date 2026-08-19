import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def payload(**changes):
    base = {"title":"Career choice","situation":"I need to compare two paths carefully.",
      "desired_outcome":"Choose a safe next step","facts":["I have two options"],
      "unknowns":["Exact compensation"],"constraints":["Avoid irreversible commitments"],
      "values":["agency"],"pillars":["career"],"consent":{"analyze":True}}
    base.update(changes); return base

def test_config_valid():
    config=json.loads(Path("u_config.json").read_text())
    assert len(config["engines"]) >= 18
    assert config["safety"]["external_actions_default"] == "deny"

def test_health():
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200

def test_decision_has_three_options(tmp_path, monkeypatch):
    monkeypatch.setenv("U_DATABASE_PATH", str(tmp_path/"u.db"))
    with TestClient(app) as c:
        r=c.post("/api/decisions",json=payload())
        assert r.status_code == 200
        assert [x["name"] for x in r.json()["options"]] == ["stay","change","pause"]

def test_safety_precedes_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("U_DATABASE_PATH", str(tmp_path/"u.db"))
    with TestClient(app) as c:
        r=c.post("/api/decisions",json=payload(situation="I might hurt myself and can't stay safe"))
        data=r.json()
        assert data["risk"] == "crisis"
        assert data["engine_trace"][0]["engine"] == "safety"
        assert data["options"] == []

def test_no_analysis_without_consent(tmp_path, monkeypatch):
    monkeypatch.setenv("U_DATABASE_PATH", str(tmp_path/"u.db"))
    with TestClient(app) as c:
        r=c.post("/api/decisions",json=payload(consent={"analyze":False}))
        assert r.json()["options"] == []
