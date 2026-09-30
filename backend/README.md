# Copilot API

For the Supabase authentication and isolated workspace foundation, see [SUPABASE.md](../SUPABASE.md). Set both backend and frontend auth modes to `supabase` only after applying its migration and configuring the project. Default `demo` mode remains a shared local sample workspace.

Start from the repository root:

```bash
UV_CACHE_DIR=.uv-cache uv pip install --python .venv/bin/python -r backend/requirements.txt
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000/api/docs` for the API. The SQLite file lives at `backend/copilot_workspace.db` unless `COPILOT_DATABASE_URL` is set. Local demo mode seeds eight fictional contacts on first start. Supabase workspaces start empty. The default `COPILOT_MODE=demo` simulates every send. `POST /api/demo/reset` clears the workspace and restores those contacts.

The frontend uses these primary routes: `/api/summary`, `/api/contacts`, `/api/recommendations/{contact_id}`, `/api/reviews/{recommendation_id}/approve`, `/api/sends/{recommendation_id}`, `/api/activity`, `/api/insights`, `/api/connections`, and `/api/experiments`. CSV preview, import, and export routes are also available.

For OAuth setup, register the exact callback URLs `http://localhost:8000/api/oauth/hubspot/callback` and `http://localhost:8000/api/oauth/gmail/callback` with HubSpot and Google. Set `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_SENDER_EMAIL`, and `COPILOT_ENCRYPTION_KEY` as needed. Generate the key with `.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Set `COPILOT_PUBLIC_API_URL` and `COPILOT_PUBLIC_WEB_URL` when deployed. In local demo mode `COPILOT_ACCESS_TOKEN` optionally protects the API with a shared bearer token. In Supabase mode authenticated users select a workspace; OAuth callbacks use workspace-bound one-time state instead. Save the Gmail sender address in Connections for each customer workspace.

`COPILOT_MODE=live` enables Gmail sends **only for non-demo contacts** after individual approval. An uncertain Gmail failure remains recorded and is never retried automatically. HubSpot sync is read-only, imports contacts with stable HubSpot IDs, and fetches up to three associated companies, deals, and notes per contact when accessible. Missing permissions or unavailable associations leave the context empty. Real connector calls require configured OAuth accounts and were not exercised in the automated tests.

Run focused tests with `.venv/bin/python -m pytest backend/test_api.py -q`.

## Groq model configuration

Keep model credentials on the server. Set `GROQ_API_KEY` and optionally `GROQ_MODEL_ID` (default `llama-3.3-70b-versatile`), or save a key through the workspace Connections screen with a stable `COPILOT_ENCRYPTION_KEY`. Workspace keys are Fernet-encrypted in the configured database. Preserve this encryption key across restarts; changing it requires restoring it or replacing stored credentials. Never put `GROQ_API_KEY` in a `NEXT_PUBLIC_` variable. Use HTTPS and Supabase authentication for customer installations; the optional shared token is only a local-demo gate.

`GET /api/model` exposes configuration/status without credentials; `PUT /api/model` accepts `{model_id, api_key?}`; omitting `api_key` preserves the saved key or server environment key. `POST /api/model/test` checks Groq credentials and the selected active model. This access check does not guarantee chat/JSON capabilities: the first generation reports incompatible models with a recovery message. `DELETE /api/model` removes workspace configuration; in local demo mode a server environment key remains configured until removed on the server. Supabase workspaces never inherit the deployment model key. `credential_source` distinguishes encrypted workspace credentials from environment credentials.

The bounded agent checks eligibility before calling the model. It permits at most two model calls (decision, draft), requests structured source references, validates those references, and falls back to a visibly labeled template on invalid output/provider failure. The prompt treats CRM notes as untrusted data. Model-backed drafts still require individual approval; model access never enables sending. Source-reference and numeric/link checks reduce unsupported output, but do not prove semantic faithfulness: users must review every draft. No live Groq account has been verified in the automated tests.

Recommendations expose `generation_source` (`rules`, `template`, or `model`), `model_id`, `prompt_version`, `model_status`, `generation_error`, and `decision_path`. The server stores source inputs and structured outputs for debugging in the recommendation audit. No API key enters these records or the LangGraph checkpoint. Model and connector credentials survive demo resets.

Run backend checks with `.venv/bin/python -m pytest backend -q`. Provider tests use mocked HTTP responses; live OAuth sync and one explicitly approved real send still require test accounts.

Approval requests must include the reviewed snapshot: `POST /api/reviews/{id}/approve` with `{version, recipient}`. The API rejects stale versions or changed recipients and rechecks current eligibility/recent sends before approval and execution. Draft edits clear previous approval and append the exact human-edited content to the server audit.
