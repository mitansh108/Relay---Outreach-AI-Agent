# Supabase foundation

Relay now has a Supabase-ready authentication and workspace data foundation. It is not yet a verified hosted deployment. The existing local demo stays available; customer mode requires explicit configuration.

## Architecture

- The browser uses `@supabase/supabase-js` for email/password signup, confirmation, login, session refresh, and local sign-out.
- Next.js forwards the signed-in access token and selected `X-Workspace-ID` through its existing `/api` proxy. CSV downloads use the same authenticated path.
- FastAPI verifies the access token with the configured Supabase project's `/auth/v1/user` endpoint. It never accepts a browser-supplied user ID. Verification failure blocks access.
- Workspace creation atomically inserts a workspace, its owner membership, and disconnected Gmail/HubSpot records. New workspaces are empty.
- FastAPI checks membership before opening a workspace session. ORM filters cover reads, aggregates, joins, updates, and bulk deletes. Writes validate ownership and related resource IDs.
- PostgreSQL stores product data in the **private `relay` schema**. The restricted `relay_app` role uses RLS with transaction-local user/workspace context and membership checks. Composite foreign keys also prevent cross-workspace relationships.
- Browser `anon` and `authenticated` roles have no access to product tables or credentials. Do not expose `relay` through Supabase Data API settings. All product data operations go through FastAPI.
- Credentials remain Fernet-encrypted server-side, keyed by workspace and provider. OAuth state records bind the callback to the initiating user/workspace and expire after ten minutes; removed members cannot finish connecting.
- Workspace model settings and Gmail sender addresses do not inherit deployment credentials in Supabase mode. Shared OAuth application client IDs/secrets remain server configuration.

## Configure later

1. Create a Supabase project. Enable email/password authentication and configure the site URL and allowed `/workspace` redirect URL for your deployed frontend. For local development use `http://localhost:3000/workspace`. Email confirmation remains supported; custom SMTP and account recovery can follow before public release.
2. Apply [the migration](supabase/migrations/202609300001_workspace_auth.sql) once using the Supabase SQL Editor or CLI. It is for a fresh install; it does not migrate the old SQLite file. It creates tables, RLS policies, relationships, and a `NOLOGIN` database role.
3. Give `relay_app` a strong password and enable login from an administrative connection:

   ```sql
   ALTER ROLE relay_app LOGIN PASSWORD '<choose a strong password privately>';
   ```

   Set the password directly in your database administration tool, not in chat, committed files, or shell command arguments. Do not run the API using the `postgres` owner or a role that bypasses RLS. Startup enforces the `relay_app` role.
4. Copy `backend/.env.example` to `backend/.env` and set:

   ```dotenv
   COPILOT_AUTH_MODE=supabase
   COPILOT_MODE=demo
   COPILOT_DATABASE_URL=postgresql+psycopg://relay_app:URL_ENCODED_PASSWORD@db.PROJECT.supabase.co:5432/postgres?sslmode=require
   SUPABASE_URL=https://PROJECT.supabase.co
   SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
   COPILOT_ENCRYPTION_KEY=YOUR_STABLE_FERNET_KEY
   ```

   Generate the encryption key with `.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Preserve it across deployments. Keep database passwords and provider secrets server-side. A Supabase service-role API key is not needed.

   Use the project's direct database endpoint where reachable, or its **session pooler** with the correct custom-role username from the Supabase connection settings. Transaction-pooler configuration is outside this initial base. Application connections set `search_path=relay` and transaction-local identity settings.
5. Copy `frontend/.env.example` to `frontend/.env.local` and set:

   ```dotenv
   API_URL=http://127.0.0.1:8000
   NEXT_PUBLIC_AUTH_MODE=supabase
   NEXT_PUBLIC_SUPABASE_URL=https://PROJECT.supabase.co
   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
   ```

   These frontend values are public project settings, not database/provider credentials. Restart/rebuild Next.js after changing them. Both frontend and backend auth modes must match.
6. Install dependencies and start:

   ```sh
   UV_CACHE_DIR=.uv-cache uv pip install --python .venv/bin/python -r requirements.txt -r backend/requirements.txt
   .venv/bin/uvicorn backend.main:app --env-file backend/.env --host 127.0.0.1 --port 8000
   ```

   From `frontend/`, run `npm ci` and `npm run dev`. Open `/workspace`, create an account, confirm email if required, create a workspace, and import contacts. Leave `COPILOT_MODE=demo` to simulate delivery while validating accounts and isolation.

The integration follows Supabase's [authentication guidance](https://supabase.com/docs/guides/auth/passwords), [database connection guidance](https://supabase.com/docs/guides/database/connecting-to-postgres), and [row security guidance](https://supabase.com/docs/guides/database/postgres/row-level-security).

## Local demo and legacy data

Without Supabase, keep both auth modes at `demo`. The current schema uses `backend/copilot_workspace.db` by default. The previous `backend/copilot.db` remains untouched. Pointing the API at a legacy schema produces a clear startup error instead of altering or deleting it. Export contacts from the old version and import the CSV into the intended workspace when ready; history/approval/credential migration needs a separately reviewed mapping. Never transfer approval or send history casually between workspaces.

## Validation

```sh
.venv/bin/python -m pytest backend agent/test_copilot.py -q
```

`backend/test_tenancy.py` verifies signed-in identity, membership checks, empty workspaces, cross-user resource access, aggregates, activity, exports, model keys, connector records, OAuth state, bulk deletes, and related-record validation. Supabase Auth/provider responses are mocked.

For database policy checks, apply the migration to an **isolated test PostgreSQL database**, create the `anon` and `authenticated` placeholder roles if testing outside Supabase, enable `relay_app` login, and set `RELAY_TEST_POSTGRES_URL` to its restricted-role connection string. Then run the same tenancy test file. It creates persistent test workspaces, so use a disposable database. The tests deliberately issue unfiltered SQL to check RLS independent of the API.

## Deferred

Team invitations and membership management, password recovery, account deletion, OAuth account identity validation, provider reconnect reconciliation, import/sync background jobs, quotas, production observability, shared durable checkpoint storage, and live Supabase/Gmail/HubSpot checks are later milestones. Current customer connections are shared within a workspace; per-member mailboxes are not implemented. Existing agent execution stays unchanged in this foundation pass.
