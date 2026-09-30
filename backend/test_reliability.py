"""Release safety checks. Provider requests use MockTransport; no email is sent."""
import base64
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from functools import partial
from backend.db import WorkspaceSession
Session = partial(WorkspaceSession, info={"workspace_id": "demo", "user_id": None})

from backend import connectors
from backend.db import Base, get_db
from backend.main import api, app, graph_for, seed
from backend.models import Connection, Contact, OAuthCredential, OAuthPending, now
from backend.test_api import approve_current

REAL_HTTP_CLIENT = httpx.Client


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setenv("COPILOT_MODE", "demo")
    monkeypatch.delenv("COPILOT_ACCESS_TOKEN", raising=False)
    engine = create_engine(f"sqlite:///{tmp_path / 'workspace.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)

    def override():
        with Session(engine) as db:
            yield db

    api.dependency_overrides[get_db] = override
    yield TestClient(app), engine
    api.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def oauth_env(monkeypatch):
    monkeypatch.setenv("COPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    for key in ("HUBSPOT_CLIENT_ID", "HUBSPOT_CLIENT_SECRET", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        monkeypatch.setenv(key, "test-only-value")


def provider_mock(monkeypatch, handler):
    monkeypatch.setattr(connectors.httpx, "Client", lambda **kwargs: REAL_HTTP_CLIENT(transport=httpx.MockTransport(handler), **kwargs))


def first_recommendation(client):
    contact = client.get("/api/contacts").json()["items"][0]
    response = client.post(f"/api/recommendations/{contact['id']}")
    assert response.status_code == 200, response.text
    return contact, response.json()


def test_oauth_configuration_rejects_invalid_encryption_key(monkeypatch, oauth_env):
    assert connectors.configured("gmail")
    monkeypatch.setenv("COPILOT_ENCRYPTION_KEY", "invalid-key")
    assert not connectors.configured("gmail")
    assert not connectors.configured("unknown")


def test_oauth_pkce_exchange_consumes_state_and_encrypts_tokens(workspace, oauth_env, monkeypatch):
    _, engine = workspace
    seen = []

    def handler(request):
        seen.append(parse_qs(request.content.decode()))
        return httpx.Response(200, json={"access_token": "secret-access", "refresh_token": "secret-refresh", "expires_in": 3600})

    provider_mock(monkeypatch, handler)
    with Session(engine) as db:
        params = parse_qs(urlparse(connectors.authorization_url(db, "gmail")).query)
        state = params["state"][0]
        pending = db.get(OAuthPending, state)
        verifier = pending.code_verifier
        expected = base64.urlsafe_b64encode(__import__("hashlib").sha256(verifier.encode()).digest()).decode().rstrip("=")
        assert params["code_challenge"] == [expected]
        connectors.exchange_code(db, "gmail", state, "test-code")
        assert seen[0]["code_verifier"] == [verifier]
        assert db.get(OAuthPending, state) is None
        credential = db.get(OAuthCredential, "gmail")
        assert "secret-access" not in credential.encrypted_token
        assert "secret-refresh" not in credential.encrypted_refresh_token
        assert connectors.access_token(db, "gmail") == "secret-access"
        with pytest.raises(ValueError, match="invalid or expired"):
            connectors.exchange_code(db, "gmail", state, "test-code")
        assert len(seen) == 1


def test_expired_and_wrong_provider_oauth_states_never_call_provider(workspace, oauth_env, monkeypatch):
    _, engine = workspace
    provider_mock(monkeypatch, lambda request: pytest.fail("Invalid OAuth state must not make a request"))
    with Session(engine) as db:
        db.add(OAuthPending(state="expired", provider="gmail", expires_at=now() - timedelta(minutes=1)))
        db.add(OAuthPending(state="different", provider="hubspot", expires_at=now() + timedelta(minutes=1)))
        db.commit()
        for state in ("expired", "different", "missing"):
            with pytest.raises(ValueError, match="invalid or expired"):
                connectors.exchange_code(db, "gmail", state, "code")


def test_cached_oauth_state_cannot_be_reused_by_another_session(workspace, oauth_env, monkeypatch):
    _, engine = workspace
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"access_token": "test-access"})

    provider_mock(monkeypatch, handler)
    with Session(engine) as first, Session(engine) as second:
        state = parse_qs(urlparse(connectors.authorization_url(first, "gmail")).query)["state"][0]
        cached = second.get(OAuthPending, state)
        assert cached is not None
        connectors.exchange_code(first, "gmail", state, "code")
        with pytest.raises(ValueError, match="already been used|invalid or expired"):
            connectors.exchange_code(second, "gmail", state, "code")
        assert len(calls) == 1


def test_refresh_preserves_refresh_token_and_records_recoverable_error(workspace, oauth_env, monkeypatch):
    _, engine = workspace
    with Session(engine) as db:
        connectors.save_tokens(db, "gmail", {"access_token": "old", "refresh_token": "refresh", "expires_in": 3600})
        credential = db.get(OAuthCredential, "gmail")
        refresh_encrypted = credential.encrypted_refresh_token
        credential.expires_at = now() - timedelta(seconds=1)
        db.commit()
        calls = []

        def success(request):
            calls.append(parse_qs(request.content.decode()))
            return httpx.Response(200, json={"access_token": "new", "expires_in": 3600})

        provider_mock(monkeypatch, success)
        assert connectors.access_token(db, "gmail") == "new"
        assert calls[0]["refresh_token"] == ["refresh"]
        assert db.get(OAuthCredential, "gmail").encrypted_refresh_token == refresh_encrypted
        credential.expires_at = now() - timedelta(seconds=1)
        db.commit()
        provider_mock(monkeypatch, lambda request: httpx.Response(400, json={"error": "invalid_grant", "description": "private-provider-details"}))
        with pytest.raises(ValueError, match="Reconnect"):
            connectors.access_token(db, "gmail")
        error = db.get(Connection, "gmail").last_error
        assert "Reconnect" in error
        assert "private-provider-details" not in error


def test_short_lived_tokens_are_not_used_beyond_expiry(workspace, oauth_env):
    _, engine = workspace
    with Session(engine) as db:
        connectors.save_tokens(db, "gmail", {"access_token": "short", "expires_in": 30})
        expiry = db.get(OAuthCredential, "gmail").expires_at
        assert expiry.replace(tzinfo=now().tzinfo) <= now()
        with pytest.raises(ValueError, match="reconnect"):
            connectors.access_token(db, "gmail")
        assert "expired" in db.get(Connection, "gmail").last_error
        with pytest.raises(ValueError):
            connectors.save_tokens(db, "gmail", {"access_token": "", "expires_in": 3600})


def test_rotated_encryption_key_reports_reconnect_without_exposing_secrets(workspace, oauth_env, monkeypatch):
    _, engine = workspace
    with Session(engine) as db:
        connectors.save_tokens(db, "gmail", {"access_token": "secret-token"})
        monkeypatch.setenv("COPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
        with pytest.raises(ValueError, match="Restore.*reconnect"):
            connectors.access_token(db, "gmail")
        assert "secret-token" not in db.get(Connection, "gmail").last_error


def test_hubspot_pagination_context_and_partial_failure(workspace, oauth_env, monkeypatch):
    _, engine = workspace
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["Authorization"] == "Bearer hubspot-test"
        path = request.url.path
        if path.endswith("/contacts"):
            if request.url.params.get("after") == "next-page":
                return httpx.Response(200, json={"results": [{"id": "2", "properties": {"email": "second@example.net"}}]})
            return httpx.Response(200, json={"results": [{"id": "1", "properties": {"email": "first@example.net"}, "associations": {"companies": {"results": [{"id": "10"}]}, "deals": {"results": [{"id": "20"}]}, "notes": {"results": [{"id": "30"}]}}}], "paging": {"next": {"after": "next-page"}}})
        if path.endswith("/companies/10"):
            return httpx.Response(200, json={"properties": {"name": "Example Co"}})
        if path.endswith("/deals/20"):
            return httpx.Response(403, json={"message": "no access"})
        if path.endswith("/notes/30"):
            return httpx.Response(200, json={"properties": {"hs_note_body": "<p>Asked for &amp; pricing</p>"}})
        pytest.fail(f"Unexpected request {request.url}")

    provider_mock(monkeypatch, handler)
    with Session(engine) as db:
        connectors.save_tokens(db, "hubspot", {"access_token": "hubspot-test"})
        records = connectors.fetch_hubspot_contacts(db)
    assert len(records) == 2
    assert records[0]["_context"] == ["Company: Example Co", "Note: Asked for & pricing"]
    assert records[0]["_context_errors"] == 1
    assert len(requests) == 5


def test_hubspot_repeated_cursor_aborts_instead_of_looping(workspace, oauth_env, monkeypatch):
    _, engine = workspace
    provider_mock(monkeypatch, lambda request: httpx.Response(200, json={"results": [], "paging": {"next": {"after": "same"}}}))
    with Session(engine) as db:
        connectors.save_tokens(db, "hubspot", {"access_token": "hubspot-test"})
        with pytest.raises(ValueError, match="repeated page cursor"):
            connectors.fetch_hubspot_contacts(db)


def test_repeat_hubspot_sync_updates_stable_record_and_preserves_local_flags(workspace, monkeypatch):
    client, engine = workspace
    record = {"id": "crm-1", "properties": {"email": "CRM@example.net", "firstname": "First", "company": "Old"}, "_context": ["Note: Asked for demo"]}
    monkeypatch.setattr("backend.main.fetch_hubspot_contacts", lambda db: [record])
    with Session(engine) as db:
        db.get(Connection, "hubspot").status = "connected"
        db.commit()
    assert client.post("/api/connections/hubspot/sync").json()["synced"] == 1
    contact = client.get("/api/contacts?q=crm@example.net").json()["items"][0]
    assert client.patch(f"/api/contacts/{contact['id']}", json={"replied": True, "do_not_contact": True, "next_followup": "2026-10-02"}).status_code == 200
    record["properties"]["company"] = "Updated"
    client.post("/api/connections/hubspot/sync")
    after = client.get(f"/api/contacts/{contact['id']}").json()
    assert after["company"] == "Updated"
    assert after["replied"] and after["do_not_contact"]
    assert after["next_followup"] == "2026-10-02"
    with Session(engine) as db:
        assert db.scalar(select(func.count(Contact.id)).where(Contact.source_id == "hubspot:crm-1")) == 1


def test_api_access_and_disconnect_never_expose_credentials(workspace, oauth_env, monkeypatch):
    client, engine = workspace
    with Session(engine) as db:
        connectors.save_tokens(db, "gmail", {"access_token": "do-not-expose", "refresh_token": "also-private"})
    monkeypatch.setenv("COPILOT_ACCESS_TOKEN", "workspace-secret")
    assert client.get("/api/contacts").status_code == 401
    assert client.get("/api/contacts", headers={"Authorization": "Bearer wrong"}).status_code == 401
    headers = {"Authorization": "Bearer workspace-secret"}
    connection = client.get("/api/connections", headers=headers)
    assert connection.status_code == 200
    assert "do-not-expose" not in connection.text and "also-private" not in connection.text
    assert client.get("/api/oauth/gmail/callback?state=missing&code=code").status_code == 400
    assert client.post("/api/connections/gmail/disconnect", headers=headers).status_code == 200
    with Session(engine) as db:
        assert db.get(OAuthCredential, "gmail") is None
        assert db.get(Connection, "gmail").status == "disconnected"


def test_edited_recipient_and_replied_contacts_require_new_approval(workspace):
    client, _ = workspace
    contact, rec = first_recommendation(client)
    assert approve_current(client, rec["id"]).status_code == 200
    assert client.patch(f"/api/recommendations/{rec['id']}/draft", json={"subject": "New draft", "body": "New reviewed context."}).status_code == 200
    assert client.post(f"/api/sends/{rec['id']}").status_code == 409
    approve_current(client, rec["id"])
    assert client.patch(f"/api/contacts/{contact['id']}", json={"contact": "changed@example.net"}).status_code == 200
    assert client.post(f"/api/sends/{rec['id']}").status_code == 409
    approve_current(client, rec["id"])
    client.post(f"/api/contacts/{contact['id']}/replied")
    assert client.post(f"/api/sends/{rec['id']}").status_code == 409


def test_skipped_draft_cannot_send_and_approval_persists(workspace):
    client, _ = workspace
    _, rec = first_recommendation(client)
    client.post(f"/api/reviews/{rec['id']}/skip")
    assert client.post(f"/api/sends/{rec['id']}").status_code == 409
    _, pending = first_recommendation(client)
    approve_current(client, pending["id"])
    # A fresh client/session and reopened SQLite checkpointer model a restart.
    reopened = TestClient(app)
    assert reopened.get(f"/api/recommendations/{pending['id']}").json()["status"] == "approved"
    with graph_for(pending["id"]) as (graph, config):
        assert graph.get_state(config).next == ("review",)
    assert reopened.post(f"/api/sends/{pending['id']}").json()["status"] == "simulated"
    assert reopened.get("/api/insights").json()["simulated"] == 1


def test_uncertain_gmail_failure_is_visible_and_never_retried(workspace, monkeypatch):
    client, engine = workspace
    calls = []

    def uncertain(*args):
        calls.append(args)
        raise httpx.ReadTimeout("Provider may have accepted the message")

    monkeypatch.setenv("COPILOT_MODE", "live")
    monkeypatch.setenv("GOOGLE_SENDER_EMAIL", "test-seller@example.net")
    monkeypatch.setattr("backend.main.send_gmail", uncertain)
    with Session(engine) as db:
        db.get(Connection, "gmail").status = "connected"
        db.commit()
    payload = {"csv_text": "name,contact,notes,next_followup\nTest Buyer,uncertain@example.net,Requested pricing,2026-01-01\n"}
    client.post("/api/import/commit", json=payload)
    contact = client.get("/api/contacts?q=uncertain@example.net").json()["items"][0]
    rec = client.post(f"/api/recommendations/{contact['id']}").json()
    approve_current(client, rec["id"])
    first = client.post(f"/api/sends/{rec['id']}").json()
    second = TestClient(app).post(f"/api/sends/{rec['id']}").json()
    assert first == second
    assert first["status"] == "failed" and "Check Gmail" in first["error"]
    assert len(calls) == 1
    assert client.get("/api/insights").json()["failed"] == 1


def test_competing_send_reservations_call_provider_once(workspace, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from backend.main import execute_approved_send

    client, engine = workspace
    started, release = Event(), Event()
    calls = []

    def sender(*args):
        calls.append(args)
        started.set()
        assert release.wait(timeout=5)
        return "provider-test-id"

    monkeypatch.setenv("COPILOT_MODE", "live")
    monkeypatch.setenv("GOOGLE_SENDER_EMAIL", "test-seller@example.net")
    monkeypatch.setattr("backend.main.send_gmail", sender)
    with Session(engine) as db:
        db.get(Connection, "gmail").status = "connected"
        db.commit()
    client.post("/api/import/commit", json={"csv_text": "name,contact,notes,next_followup\nRace Buyer,race@example.net,Requested a demo,2026-01-01\n"})
    contact = client.get("/api/contacts?q=race@example.net").json()["items"][0]
    rec = client.post(f"/api/recommendations/{contact['id']}").json()
    assert approve_current(client, rec["id"]).status_code == 200

    def execute():
        with Session(engine) as db:
            return execute_approved_send(rec["id"], db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(execute)
        try:
            assert started.wait(timeout=5)
            competing = pool.submit(execute).result(timeout=5)
            assert competing["status"] == "reserved"
            assert len(calls) == 1
        finally:
            release.set()
        completed = first.result(timeout=5)
    assert competing["id"] == completed["id"]
    assert completed["status"] == "sent"


def test_csv_duplicates_and_invalid_dates_are_previewed_without_writes(workspace):
    client, _ = workspace
    content = "name,contact,next_followup\nBuyer,Case@EXAMPLE.net,2026-10-02\nDuplicate,case@example.net,2026-10-02\nBad Date,other@example.net,not-a-date\n"
    preview = client.post("/api/import/preview", json={"csv_text": content}).json()
    assert preview["count"] == 1
    assert len(preview["errors"]) == 2
    assert client.get("/api/summary").json()["total"] == 8
    assert client.post("/api/import/commit", json={"csv_text": content}).json()["imported"] == 1
    assert client.post("/api/import/commit", json={"csv_text": content}).json()["imported"] == 0


def test_experiment_assignment_and_exposure_are_stable_across_reloads(workspace):
    client, _ = workspace
    today = date.today()
    payload = {"name": "Approval test", "variable": "cta", "start_date": (today - timedelta(days=1)).isoformat(), "end_date": (today + timedelta(days=13)).isoformat(), "variants": [{"id": "a", "value": "soft", "weight": 50}, {"id": "b", "value": "direct", "weight": 50}]}
    experiment = client.post("/api/experiments", json=payload).json()
    contact, rec = first_recommendation(client)
    again = TestClient(app).post(f"/api/recommendations/{contact['id']}").json()
    assert rec["variant_id"] == again["variant_id"]
    results_url = f"/api/experiments/{experiment['id']}/results"
    assert sum(v["sent"] for v in client.get(results_url).json()["variants"]) == 0
    approve_current(client, rec["id"])
    client.post(f"/api/sends/{rec['id']}")
    client.post(f"/api/sends/{rec['id']}")
    client.post(f"/api/contacts/{contact['id']}/replied")
    client.post(f"/api/contacts/{contact['id']}/replied")
    results = TestClient(app).get(results_url).json()
    assert sum(v["sent"] for v in results["variants"]) == 1
    assert sum(v["replied"] for v in results["variants"]) == 1
    assert results["winner"] is None
    client.post(f"/api/experiments/{experiment['id']}/pause")
    other = client.get("/api/contacts").json()["items"][1]
    assert client.post(f"/api/recommendations/{other['id']}").json()["experiment_id"] is None


def test_approval_requires_exact_reviewed_version_and_recipient(workspace):
    client, _ = workspace
    contact, rec = first_recommendation(client)
    url = f"/api/reviews/{rec['id']}/approve"
    snapshot = {"version": rec["version"], "recipient": contact["contact"]}
    assert client.post(url).status_code == 422
    assert client.post(url, json={**snapshot, "recipient": "other@example.net"}).status_code == 409
    changed = client.patch(f"/api/recommendations/{rec['id']}/draft", json={"subject": "Reviewed revision", "body": "New context for review."}).json()
    assert client.post(url, json=snapshot).status_code == 409
    snapshot["version"] = changed["version"]
    client.patch(f"/api/contacts/{contact['id']}", json={"contact": "changed@example.net"})
    assert client.post(url, json=snapshot).status_code == 409
    snapshot["recipient"] = "changed@example.net"
    assert client.post(url, json=snapshot).status_code == 200
