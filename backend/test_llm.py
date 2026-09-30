import json

import httpx
import pytest
from cryptography.fernet import Fernet
from functools import partial
from backend.db import WorkspaceSession
Session = partial(WorkspaceSession, info={"workspace_id": "demo", "user_id": None})

from agent.copilot import recommend
from backend.llm import GroqAdapter, ModelError, ModelConfiguration
from backend.main import api
from backend.test_api import client_for_test


@pytest.fixture(autouse=True)
def clean_configuration(monkeypatch):
    for name in ("GROQ_API_KEY", "GROQ_MODEL_ID", "COPILOT_ENCRYPTION_KEY", "COPILOT_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    yield
    api.dependency_overrides.clear()


def lead():
    return {"name": "Priya", "contact": "priya@example.net", "company": "Northstar", "notes": "Requested a product demo", "status": "New"}


def provider(status=200):
    def handle(request):
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "DO NOT EXPOSE KEY"}})
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "untrusted" in payload["messages"][0]["content"]
        data = {"action": "email", "reason": "Requested a product demo", "sources": [{"field": "notes", "value": lead()["notes"]}]}
        if "subject: string" in payload["messages"][0]["content"]:
            data = {"subject": "Your demo request", "body": "Hi Priya, would you like to discuss your product demo request?", "facts": [{"field": "notes", "value": lead()["notes"]}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(data)}}]})
    return httpx.MockTransport(handle)


def test_grounded_generation_and_weak_context():
    adapter = GroqAdapter("secret", "test-model", provider())
    result = recommend(lead(), llm=adapter)
    assert result["generation_source"] == "model"
    assert result["model_id"] == "test-model"
    assert result["draft"]["subject"] == "Your demo request"
    weak = recommend({**lead(), "notes": ""}, llm=adapter)
    assert weak["action"] == "call_task"
    assert weak["draft"] is None


@pytest.mark.parametrize("status,code", [(401, "invalid_credentials"), (404, "invalid_model"), (429, "rate_limited"), (500, "provider_unavailable")])
def test_safe_failure_and_truthful_fallback(status, code):
    adapter = GroqAdapter("secret", "test-model", provider(status))
    with pytest.raises(ModelError) as error:
        adapter.test()
    assert error.value.code == code
    result = recommend(lead(), llm=adapter)
    assert result["generation_source"] == "template"
    assert result["model_id"] == "rules-demo-v1"
    assert result["generation_error"]
    assert "secret" not in json.dumps(result)
    assert "DO NOT EXPOSE" not in json.dumps(result)


def test_model_not_in_active_models():
    with pytest.raises(ModelError, match="not available"):
        GroqAdapter("secret", "missing", provider()).test()


def test_config_encrypted_and_secret_free(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with client_for_test(tmp_path) as client:
        saved = client.put("/api/model", json={"model_id": "test-model", "api_key": "private-key"})
        assert saved.status_code == 200
        assert saved.json()["source"] == "workspace"
        assert "private-key" not in saved.text
        with Session(client.test_engine) as db:
            assert "private-key" not in db.get(ModelConfiguration, "groq").encrypted_key
        monkeypatch.setattr("backend.llm.GroqAdapter.test", lambda self: True)
        assert client.post("/api/model/test").json()["status"] == "connected"
        monkeypatch.setattr("backend.llm.GroqAdapter.test", lambda self: (_ for _ in ()).throw(ModelError("invalid_model", "Choose an active model.")))
        assert client.post("/api/model/test").json()["last_error"] == "Choose an active model."
        assert client.delete("/api/model").json()["configured"] is False


def test_missing_encryption_and_environment_fallback(tmp_path, monkeypatch):
    with client_for_test(tmp_path) as client:
        assert client.get("/api/model").json()["status"] == "unconfigured"
        rejected = client.put("/api/model", json={"model_id": "test-model", "api_key": "private-key"})
        assert rejected.status_code == 422
        assert "COPILOT_ENCRYPTION_KEY" in rejected.text
        monkeypatch.setenv("GROQ_API_KEY", "environment-secret")
        assert client.get("/api/model").json()["source"] == "environment"
        assert client.put("/api/model", json={"model_id": "test-model"}).status_code == 200
        assert client.delete("/api/model").json()["source"] == "environment"


def test_api_model_draft_persists_in_review_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "environment-secret")
    monkeypatch.setattr("backend.main.adapter_for", lambda db: GroqAdapter("secret", "test-model", provider()))
    with client_for_test(tmp_path) as client:
        c = client.get("/api/contacts").json()["items"][0]
        client.patch(f"/api/contacts/{c['id']}", json={"notes": lead()["notes"]})
        result = client.post(f"/api/recommendations/{c['id']}").json()
        assert result["generation_source"] == "model", result
        assert result["model_id"] == "test-model"
        assert client.get(f"/api/recommendations/{result['id']}").json()["body"] == result["body"]
        assert client.post(f"/api/reviews/{result['id']}/approve", json={"version": result["version"], "recipient": c["contact"]}).status_code == 200
        assert client.post(f"/api/sends/{result['id']}").json()["status"] == "simulated"


def test_validation_error_does_not_echo_secret(tmp_path):
    with client_for_test(tmp_path) as client:
        secret = "secret-value-" * 100
        result = client.put("/api/model", json={"model_id": "test-model", "api_key": secret})
        assert result.status_code == 422
        assert "secret-value" not in result.text


def test_changed_encryption_key_preserves_credential_free_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with client_for_test(tmp_path) as client:
        client.put("/api/model", json={"model_id": "test-model", "api_key": "private-key"})
        monkeypatch.setenv("COPILOT_ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert client.get("/api/model").json()["status"] == "error"
        contact = client.get("/api/contacts").json()["items"][0]
        result = client.post(f"/api/recommendations/{contact['id']}").json()
        assert result["generation_source"] == "template"
        assert result["generation_error"]
