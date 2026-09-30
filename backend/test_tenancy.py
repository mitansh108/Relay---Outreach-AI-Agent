"""Multi-user tests use real API/session scoping and mocked Supabase Auth only.

Set RELAY_TEST_POSTGRES_URL to a migrated, isolated DB using relay_app to also
exercise the PostgreSQL RLS policies. This creates test workspaces in that DB.
"""
import os
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend import auth, db as persistence, main
from backend.db import Base, WorkspaceSession, configure_context
from backend.models import Contact, Membership, OAuthCredential, Recommendation
from backend.llm import ModelConfiguration

REAL_CLIENT = httpx.Client
DATABASES = ["sqlite"] + (["postgres"] if os.getenv("RELAY_TEST_POSTGRES_URL") else [])


@pytest.fixture(params=DATABASES)
def tenants(request, tmp_path, monkeypatch):
    postgres = request.param == "postgres"
    url = os.getenv("RELAY_TEST_POSTGRES_URL") if postgres else f"sqlite:///{tmp_path / 'tenants.db'}"
    engine = create_engine(url, connect_args={"options": "-csearch_path=relay"} if postgres else {"check_same_thread": False})
    if not postgres:
        Base.metadata.create_all(engine)
    monkeypatch.setenv("COPILOT_AUTH_MODE", "supabase")
    monkeypatch.setenv("COPILOT_MODE", "demo")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable")
    monkeypatch.setenv("COPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("COPILOT_CHECKPOINT_DB", str(tmp_path / "checkpoints.sqlite"))
    monkeypatch.setenv("GROQ_API_KEY", "deployment-key-must-not-leak")
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(persistence, "engine", engine)
    monkeypatch.setattr(persistence, "SessionLocal", sessionmaker(bind=engine, class_=WorkspaceSession, expire_on_commit=False))
    identities = {"alice": str(uuid4()), "bob": str(uuid4())}
    calls = []

    def verify(request):
        assert str(request.url) == "https://test.supabase.co/auth/v1/user"
        assert request.headers["apikey"] == "test-publishable"
        token = request.headers["Authorization"].removeprefix("Bearer ")
        calls.append(token)
        if token == "unavailable":
            return httpx.Response(503)
        if token not in identities:
            return httpx.Response(401)
        return httpx.Response(200, json={"id": identities[token], "email": f"{token}@example.net", "is_anonymous": False})

    monkeypatch.setattr(auth.httpx, "Client", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(verify), **kw))
    main.api.dependency_overrides.clear()
    client = TestClient(main.app)
    yield client, engine, identities, calls, postgres
    client.close()
    engine.dispose()


def headers(user, workspace=None):
    result = {"Authorization": f"Bearer {user}"}
    if workspace:
        result["X-Workspace-ID"] = workspace
    return result


def create(client, user):
    response = client.post("/api/workspaces", headers=headers(user), json={"name": f"{user}'s team"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def import_contact(client, user, workspace):
    response = client.post("/api/import/commit", headers=headers(user, workspace), json={"csv_text": "name,contact,notes,next_followup\nBuyer,buyer@example.net,Asked for pricing,2026-01-01\n"})
    assert response.status_code == 200, response.text
    return client.get("/api/contacts", headers=headers(user, workspace)).json()["items"][0]["id"]


def test_sessions_and_membership_are_required(tenants):
    client, _, _, calls, _ = tenants
    assert client.get("/api/contacts").status_code == 401
    assert client.get("/api/workspaces", headers=headers("forged")).status_code == 401
    assert client.get("/api/workspaces", headers=headers("unavailable")).status_code == 503
    workspace = create(client, "alice")
    assert client.get("/api/contacts", headers=headers("alice")).status_code == 403
    assert client.get("/api/contacts", headers=headers("bob", workspace)).status_code == 403
    calls.clear()
    assert client.get("/api/contacts", headers=headers("alice", workspace)).status_code == 200
    assert calls == ["alice"]  # Router and DB dependency share one verified identity.


def test_lists_ids_aggregates_and_exports_are_isolated(tenants):
    client, _, _, _, _ = tenants
    a, b = create(client, "alice"), create(client, "bob")
    assert client.get("/api/summary", headers=headers("alice", a)).json()["total"] == 0
    contact = import_contact(client, "alice", a)
    import_contact(client, "bob", b)  # Same email is legal across customers.
    rec = client.post(f"/api/recommendations/{contact}", headers=headers("alice", a)).json()
    assert "id" in rec, rec
    assert client.get(f"/api/contacts/{contact}", headers=headers("bob", b)).status_code == 404
    assert client.get(f"/api/recommendations/{rec['id']}", headers=headers("bob", b)).status_code == 404
    assert client.post(f"/api/sends/{rec['id']}", headers=headers("bob", b)).status_code == 404
    assert client.get("/api/summary", headers=headers("bob", b)).json()["pending_reviews"] == 0
    assert client.get("/api/activity", headers=headers("bob", b)).json()["items"] == []
    assert client.get("/api/insights", headers=headers("bob", b)).json()["recommendations"] == 0
    assert client.get("/api/recommendations", headers=headers("bob", b)).json()["items"] == []
    assert client.get("/api/export.csv", headers=headers("bob", b)).text.count("buyer@example.net") == 1
    assert client.get("/api/workspaces", headers=headers("bob")).json()["items"][0]["id"] == b
    assert client.post("/api/demo/reset", headers=headers("alice", a)).status_code == 403


def test_connections_models_and_oauth_state_are_isolated(tenants, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    client, engine, identities, _, _ = tenants
    a, b = create(client, "alice"), create(client, "bob")
    for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
        monkeypatch.setenv(key, "test")
    result = client.get("/api/oauth/gmail/start", headers=headers("alice", a))
    assert result.status_code == 200, result.text
    state = parse_qs(urlparse(result.json()["authorization_url"]).query)["state"][0]
    with WorkspaceSession(engine, info={"workspace_id": b, "user_id": identities["bob"]}) as db:
        from backend.models import OAuthPending
        assert db.get(OAuthPending, state) is None
    assert client.get("/api/oauth/gmail/callback?state=forged&code=x").status_code == 400
    assert client.put("/api/model", headers=headers("alice", a), json={"model_id": "test-model", "api_key": "alice-secret"}).status_code == 200
    assert client.get("/api/model", headers=headers("bob", b)).json()["configured"] is False
    assert client.delete("/api/model", headers=headers("bob", b)).status_code == 200
    assert client.get("/api/model", headers=headers("alice", a)).json()["configured"] is True
    assert client.put("/api/connections/gmail/settings", headers=headers("alice", a), json={"sender_email": "alice@example.net"}).status_code == 200
    bob_connections = client.get("/api/connections", headers=headers("bob", b)).json()["items"]
    assert next(c for c in bob_connections if c["provider"] == "gmail")["sender_email"] is None
    # Store distinct provider tokens without making any live provider request.
    from backend.connectors import save_tokens
    for workspace, user in ((a, "alice"), (b, "bob")):
        with WorkspaceSession(engine, info={"workspace_id": workspace, "user_id": identities[user]}) as db:
            save_tokens(db, "gmail", {"access_token": user + "-token"})
    assert client.post("/api/connections/gmail/disconnect", headers=headers("bob", b)).status_code == 200
    with WorkspaceSession(engine, info={"workspace_id": a, "user_id": identities["alice"]}) as db:
        assert db.get(OAuthCredential, "gmail") is not None
        assert "alice-secret" not in db.get(ModelConfiguration, "groq").encrypted_key


def test_cross_workspace_relationship_and_bulk_delete_blocked(tenants):
    client, engine, identities, _, _ = tenants
    a, b = create(client, "alice"), create(client, "bob")
    contact = import_contact(client, "alice", a)
    import_contact(client, "bob", b)
    with WorkspaceSession(engine, info={"workspace_id": b, "user_id": identities["bob"]}) as db:
        db.add(Recommendation(contact_id=contact, action="wait", reason="Forbidden"))
        with pytest.raises(Exception, match="outside this workspace"):
            db.commit()
        db.rollback()
        db.query(Contact).delete()
        db.commit()
    assert client.get("/api/summary", headers=headers("alice", a)).json()["total"] == 1
    assert client.get("/api/summary", headers=headers("bob", b)).json()["total"] == 0


def test_database_rls_blocks_unfiltered_queries_and_forged_workspace(tenants):
    client, engine, identities, _, postgres = tenants
    if not postgres:
        pytest.skip("PostgreSQL policy test requires RELAY_TEST_POSTGRES_URL")
    main.startup()  # Runtime role and migration checks.
    a, b = create(client, "alice"), create(client, "bob")
    contact = import_contact(client, "alice", a)
    import_contact(client, "bob", b)
    # Plain sessions deliberately omit the application's query filter.
    with Session(engine, info={"workspace_id": b, "user_id": identities["bob"]}) as db:
        assert db.scalar(text("SELECT count(*) FROM contacts")) == 1
        assert db.scalar(text("SELECT count(*) FROM contacts WHERE id = :id"), {"id": contact}) == 0
        assert db.execute(text("DELETE FROM contacts WHERE id = :id"), {"id": contact}).rowcount == 0
        db.rollback()
    with Session(engine, info={"workspace_id": a, "user_id": identities["bob"]}) as db:
        assert db.scalar(text("SELECT count(*) FROM contacts")) == 0
    with Session(engine) as db:
        assert db.scalar(text("SELECT count(*) FROM contacts")) == 0
    assert client.get("/api/summary", headers=headers("alice", a)).json()["total"] == 1
