from datetime import date, timedelta
import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from functools import partial
from backend.db import WorkspaceSession
Session = partial(WorkspaceSession, info={"workspace_id": "demo", "user_id": None})

from backend.db import Base, get_db
from backend.main import app, api, seed
from backend.models import Connection


def approve_current(client, recommendation_id):
    rec = client.get(f"/api/recommendations/{recommendation_id}").json()
    contact = client.get(f"/api/contacts/{rec['contact_id']}").json()
    return client.post(f"/api/reviews/{recommendation_id}/approve", json={"version": rec["version"], "recipient": contact["contact"]})


def client_for_test(tmp_path):
    os.environ["COPILOT_CHECKPOINT_DB"] = str(tmp_path / "checkpoints.sqlite")
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)

    def override():
        with Session(engine) as db:
            yield db

    api.dependency_overrides[get_db] = override
    client = TestClient(app)
    client.test_engine = engine
    return client


def test_demo_approval_and_single_send(tmp_path):
    with client_for_test(tmp_path) as client:
        assert client.get("/api/summary").json()["total"] == 8
        contact = client.get("/api/contacts").json()["items"][0]
        rec = client.post(f"/api/recommendations/{contact['id']}").json()
        assert rec["action"] == "email"
        assert client.post(f"/api/sends/{rec['id']}").status_code == 409
        edited = client.patch(f"/api/recommendations/{rec['id']}/draft", json={"subject": "A test", "body": "Hi Priya, a short note."}).json()
        assert edited["version"] == 2
        assert approve_current(client, rec["id"]).status_code == 200
        first = client.post(f"/api/sends/{rec['id']}").json()
        second = client.post(f"/api/sends/{rec['id']}").json()
        assert first["status"] == "simulated"
        assert first["id"] == second["id"]
        assert client.get("/api/insights").json()["simulated"] == 1
    api.dependency_overrides.clear()


def test_replied_contact_is_blocked(tmp_path):
    with client_for_test(tmp_path) as client:
        contact = client.get("/api/contacts").json()["items"][0]
        client.post(f"/api/contacts/{contact['id']}/replied")
        rec = client.post(f"/api/recommendations/{contact['id']}").json()
        assert rec["action"] == "no_action"
        assert approve_current(client, rec["id"]).status_code == 409
    api.dependency_overrides.clear()


def test_csv_preview_and_import(tmp_path):
    with client_for_test(tmp_path) as client:
        content = "name,contact,next_followup\nTest Buyer,buyer@example.net,2026-10-02\nBad,bad-email,2026-10-03\n"
        result = client.post("/api/import/preview", json={"csv_text": content}).json()
        assert result["count"] == 1
        assert len(result["errors"]) == 1
        assert client.post("/api/import/commit", json={"csv_text": content}).json()["imported"] == 1
        assert client.get("/api/contacts?q=Test%20Buyer").json()["total"] == 1
    api.dependency_overrides.clear()


def test_experiment_requires_real_exposure(tmp_path):
    with client_for_test(tmp_path) as client:
        today = date.today()
        payload = {
            "name": "CTA trial", "variable": "cta", "start_date": (today - timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=13)).isoformat(), "min_per_variant": 100,
            "variants": [{"id": "a", "value": "soft", "weight": 50}, {"id": "b", "value": "direct", "weight": 50}],
        }
        created = client.post("/api/experiments", json=payload)
        assert created.status_code == 200, created.text
        test_id = created.json()["id"]
        contact = client.get("/api/contacts").json()["items"][0]
        rec = client.post(f"/api/recommendations/{contact['id']}").json()
        assert rec["experiment_id"] == test_id
        before = client.get(f"/api/experiments/{test_id}/results").json()
        assert sum(v["sent"] for v in before["variants"]) == 0
        approve_current(client, rec["id"])
        client.post(f"/api/sends/{rec['id']}")
        after = client.get(f"/api/experiments/{test_id}/results").json()
        assert sum(v["sent"] for v in after["variants"]) == 1
        assert after["winner"] is None
    api.dependency_overrides.clear()


def test_live_gmail_path_is_approval_gated_and_idempotent(tmp_path, monkeypatch):
    calls = []

    def fake_gmail(db, recipient, subject, body):
        calls.append((recipient, subject, body))
        return "gmail-test-id"

    monkeypatch.setenv("COPILOT_MODE", "live")
    monkeypatch.setenv("GOOGLE_SENDER_EMAIL", "seller@example.net")
    monkeypatch.setattr("backend.main.send_gmail", fake_gmail)
    with client_for_test(tmp_path) as client:
        with Session(client.test_engine) as db:
            db.get(Connection, "gmail").status = "connected"
            db.commit()
        payload = {"csv_text": "name,contact,company,status,interest_level,notes,next_followup\nCase User,case@example.net,Acme,Interested,High,Asked for demo,2026-01-01\n"}
        assert client.post("/api/import/commit", json=payload).json()["imported"] == 1
        contact = client.get("/api/contacts?q=Case%20User").json()["items"][0]
        rec = client.post(f"/api/recommendations/{contact['id']}").json()
        assert client.post(f"/api/sends/{rec['id']}").status_code == 409
        assert not calls
        approve_current(client, rec["id"])
        first = client.post(f"/api/sends/{rec['id']}").json()
        second = client.post(f"/api/sends/{rec['id']}").json()
        assert first == second
        assert first["status"] == "sent"
        assert first["provider_id"] == "gmail-test-id"
        assert len(calls) == 1
    api.dependency_overrides.clear()


def test_oauth_start_requires_configuration(tmp_path):
    with client_for_test(tmp_path) as client:
        response = client.get("/api/oauth/hubspot/start")
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
    api.dependency_overrides.clear()


def test_gmail_api_serializes_message_without_network(monkeypatch):
    import base64
    import httpx
    from backend import connectors

    observed = {}

    def handler(request):
        assert request.url.path == "/gmail/v1/users/me/messages/send"
        assert request.headers["Authorization"] == "Bearer fake-test-token"
        payload = __import__("json").loads(request.content)
        raw = payload["raw"] + "=" * (-len(payload["raw"]) % 4)
        observed["message"] = base64.urlsafe_b64decode(raw).decode()
        return httpx.Response(200, json={"id": "gmail-test-id"})

    real_client = httpx.Client
    monkeypatch.setenv("GOOGLE_SENDER_EMAIL", "seller@example.net")
    monkeypatch.setattr(connectors, "access_token", lambda db, provider: "fake-test-token")
    monkeypatch.setattr(connectors.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    assert connectors.send_gmail(None, "buyer@example.net", "Checking in", "Hello there") == "gmail-test-id"
    assert "To: buyer@example.net" in observed["message"]
    assert "From: seller@example.net" in observed["message"]
    assert "Subject: Checking in" in observed["message"]
    assert "Hello there" in observed["message"]


def test_pending_review_checkpoint_survives_reopen(tmp_path):
    from backend.main import graph_for

    with client_for_test(tmp_path) as client:
        contact = client.get("/api/contacts").json()["items"][0]
        rec = client.post(f"/api/recommendations/{contact['id']}").json()
        checkpoint_file = tmp_path / "checkpoints.sqlite"
        assert checkpoint_file.exists()
        with graph_for(rec["id"]) as (graph, config):
            state = graph.get_state(config)
            assert state.values["recommendation"]["action"] == "email"
            assert state.next == ("review",)
        assert approve_current(client, rec["id"]).status_code == 200
        assert client.post(f"/api/sends/{rec['id']}").json()["status"] == "simulated"
        with graph_for(rec["id"]) as (graph, config):
            assert graph.get_state(config).values["result"]["status"] == "simulated"
    api.dependency_overrides.clear()
