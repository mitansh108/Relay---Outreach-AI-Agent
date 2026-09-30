# Copilot API

Start from the repository root:

```bash
UV_CACHE_DIR=.uv-cache uv pip install --python .venv/bin/python -r backend/requirements.txt
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000/api/docs` for the API. The SQLite file lives at `backend/copilot.db` unless `COPILOT_DATABASE_URL` is set. The database seeds eight fictional contacts on first start. The default `COPILOT_MODE=demo` simulates every send. `POST /api/demo/reset` clears the workspace and restores those contacts.

The frontend uses these primary routes: `/api/summary`, `/api/contacts`, `/api/recommendations/{contact_id}`, `/api/reviews/{recommendation_id}/approve`, `/api/sends/{recommendation_id}`, `/api/activity`, `/api/insights`, `/api/connections`, and `/api/experiments`. CSV preview, import, and export routes are also available.

For OAuth setup, register the exact callback URLs `http://localhost:8000/api/oauth/hubspot/callback` and `http://localhost:8000/api/oauth/gmail/callback` with HubSpot and Google. Set `HUBSPOT_CLIENT_ID`, `HUBSPOT_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_SENDER_EMAIL`, and `COPILOT_ENCRYPTION_KEY` as needed. Generate the key with `.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Set `COPILOT_PUBLIC_API_URL` and `COPILOT_PUBLIC_WEB_URL` when deployed. `COPILOT_ACCESS_TOKEN` protects the API with a bearer token; OAuth callbacks use one-time state instead.

`COPILOT_MODE=live` enables Gmail sends **only for non-demo contacts** after individual approval. An uncertain Gmail failure remains recorded and is never retried automatically. HubSpot sync is read-only, imports contacts with stable HubSpot IDs, and fetches up to three associated companies, deals, and notes per contact when accessible. Missing permissions or unavailable associations leave the context empty. Real connector calls require configured OAuth accounts and were not exercised in the automated tests.

Run focused tests with `.venv/bin/python -m pytest backend/test_api.py -q`.
