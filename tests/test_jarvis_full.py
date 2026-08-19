from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

def request(**changes):
    data={"title":"Build U","situation":"I need to integrate the interface and backend.",
      "desired_outcome":"A cohesive governed system","pillars":["career","finance"],
      "facts":["JARVIS is the interface"],"unknowns":["deployment cost"],
      "constraints":["No automatic external action"],"values":["human agency"],
      "consent":{"analyze":True,"memory":False},"command":"decide"}
    data.update(changes)
    return data

def test_jarvis_routes_to_one_brain(tmp_path,monkeypatch):
    monkeypatch.setenv("U_DATABASE_PATH",str(tmp_path/"u.db"))
    with TestClient(app) as client:
        data=client.post("/api/jarvis",json=request()).json()
        assert data["interface"]=="JARVIS"
        assert len(data["decision"]["pillar_sub_brains"])==4
        assert data["decision"]["trajectory"]["review_in_days"]==14
        assert len(data["decision"]["ripple_map"])==4

def test_emergency_stops_analysis(tmp_path,monkeypatch):
    monkeypatch.setenv("U_DATABASE_PATH",str(tmp_path/"u.db"))
    with TestClient(app) as client:
        data=client.post("/api/emergency",json={"message":"I am in danger","immediate_danger":True}).json()
        assert data["analysis_stopped"] is True
        assert data["external_action_executed"] is False

def test_memory_requires_consent(tmp_path,monkeypatch):
    monkeypatch.setenv("U_DATABASE_PATH",str(tmp_path/"u.db"))
    with TestClient(app) as client:
        assert client.get("/api/memory/local-user").status_code==403

def test_approval_token_is_single_use(tmp_path,monkeypatch):
    monkeypatch.setenv("U_DATABASE_PATH",str(tmp_path/"u.db"))
    with TestClient(app) as client:
        client.post("/api/approvals",json={"session_id":"s1","proposal_id":"p1","user_id":"u1","approved":True})
        token=client.post("/api/action-token",json={"user_id":"u1","session_id":"s1","proposal_id":"p1"}).json()["approval_token"]
        payload={"user_id":"u1","session_id":"s1","proposal_id":"p1","approval_token":token}
        assert client.post("/api/execute",json=payload).status_code==200
        assert client.post("/api/execute",json=payload).status_code==403
