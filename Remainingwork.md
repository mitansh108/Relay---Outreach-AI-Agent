# Remaining work

The product goal is in [PRODUCT_PLAN.md](PRODUCT_PLAN.md), with architecture in [PRODUCT_DIAGRAMS.md](PRODUCT_DIAGRAMS.md). This handoff distinguishes implemented work from checks that still need real accounts.

## Supabase foundation — September 30, 2026

The scope is a base for future multi-user development, not a completed production launch. Agent/LangGraph expansion is deferred at the user's request.

### Implemented locally

- Supabase email/password signup, confirmation handling, login, SDK-managed session refresh, and sign-out wrap the workspace and Connections routes. Users select or create a workspace before its data loads.
- FastAPI verifies sessions through the configured Supabase Auth service, checks workspace membership, and shares verified identity within a request. Invalid sessions, unknown auth modes, and verification failures do not fall back to demo access.
- Workspace creation atomically records its owner membership and disconnected provider records. New customer workspaces start empty. Workspace switching remounts the workspace UI to clear the previous customer's loaded data.
- Contacts, recommendations, activities, experiments, assignments, send attempts, OAuth state, connector credentials/status, and model configuration now carry workspace ownership. Reads, resource-ID lookups, aggregates, exports, writes, and bulk deletes use workspace-scoped sessions. Cross-workspace related IDs are rejected.
- Versioned migration: `supabase/migrations/202609300001_workspace_auth.sql`. It creates a private `relay` schema, a restricted `relay_app` role, forced RLS policies, scoped uniqueness, and composite relationship constraints. Browser roles cannot access product tables or credential records. Startup requires the restricted role in Supabase mode.
- OAuth callbacks resolve their initiating user/workspace from expiring single-use state and recheck membership. Model keys and Gmail sender settings are workspace-specific. Customer workspaces do not inherit shared deployment model keys or sender addresses.
- CSV export carries the same authentication/workspace headers as ordinary API calls. Demo reset is disabled for customer workspaces.
- The original `backend/copilot.db` is preserved. The updated demo defaults to `backend/copilot_workspace.db`; legacy schemas are rejected with migration guidance.
- Setup instructions and configuration examples are in `SUPABASE.md`, `backend/.env.example`, and `frontend/.env.example`.

### Validation and limits

- Existing backend checks remain passing. New tenancy checks cover session validation, membership, empty workspaces, cross-user IDs, summaries/activity/exports, credentials, OAuth state, and bulk/relationship isolation. Supabase Auth/provider calls are mocked.
- The migration was applied successfully to an isolated local PostgreSQL 14 database. Restricted-role tests verify RLS independently using unfiltered SQL, including a forged workspace context and attempted deletion of another workspace's contact. This is local PostgreSQL validation, not a live Supabase deployment.
- Final local checks: **54 tests passed, 1 PostgreSQL-only test skipped, 10 subtests passed**. The separate SQLite/PostgreSQL tenancy run passed **9 tests**, with the SQLite-only RLS case skipped. Frontend TypeScript and production build pass. Browser verification of Supabase signup/login remains pending.
- No live Supabase project was connected, remote schema changed, live provider call made, or real outreach sent.

### Next session

1. Create/configure the Supabase project and auth redirect URLs. Apply the reviewed migration; enable `relay_app` login with a privately configured password. Keep `relay` out of exposed Data API schemas.
2. Configure the backend database URL, Supabase URL/publishable key, and stable encryption key. Configure matching frontend public settings. Start with simulated delivery.
3. Verify real signup/email confirmation/login/refresh/logout and two independent users/workspaces on Supabase. Confirm the restricted role and database policies in the hosted project.
4. Verify real Gmail/HubSpot account connections, token refresh, disconnect, workspace sender identity, import, and persistence.
5. Later add team invitations/membership management, account recovery/deletion, per-member mailboxes if needed, background sync/import jobs, quotas, observability, and deployment backups. Plan migration of legacy data separately. Existing checkpoints are still local SQLite and need shared durable storage before scaling backend processes.

The original single-workspace release plan below remains historical; the Supabase foundation above supersedes its shared-access assumptions.

## Earlier implementation state — September 30, 2026

- `frontend/` is the Next.js app. `/` explains sales outreach agents with human review. Its split hero prepares context and draft automatically, then waits for click/tap approval before illustrating simulated delivery. It pauses preparation offscreen/in hidden tabs and retains the approval gate in reduced motion. The four sticky walkthrough cards retain the pinned heading and left-side step navigation.
- `/workspace` is the real sample app; `/connections` opens Connections. Groq model settings, encrypted key submission, status, testing, and removal are available there. Landing playbook goal/tone controls remain a local concept preview, not saved agent configuration.
- `backend/` stores contacts, recommendations, approvals, send attempts, model configuration, activity, and experiments in SQLite. Sample mode uses fictional contacts and simulated sends.
- `backend/llm.py` supports Groq model-backed decisions and structured drafts with explicit source references. Missing/invalid credentials and invalid output fall back to clearly labeled rules/templates. Keys use the server environment or encrypted workspace storage; the latter requires a stable `COPILOT_ENCRYPTION_KEY`.
- `agent/copilot.py` enforces eligibility and weak-context rules before model use, preserves the exact prepared recommendation in its persistent checkpoint, pauses for review, and validates the approval fingerprint on resume. Model inputs, outputs, source references, failures, and edits are recorded without API keys.
- Approval requests require the displayed `{version, recipient}`. Edits invalidate approval; stale recipients/versions, newly replied contacts, and recent-send cooldowns block approval/execution. Reservations protect duplicate sends; failed or uncertain sends are never retried automatically.
- OAuth handling includes single-use state, PKCE where applicable, encrypted credentials, recovery messages, bounded HubSpot pagination, and warnings for unavailable associated context. HubSpot sync stays read-only.
- A/B tests retain deterministic contact assignment, approval-gated exposures, manual outcomes, and cautious small-sample results.
- Backend/API and agent verification: **50 tests passed, 10 subtests passed**. Provider calls are mocked. Browser checks completed a sample recommendation → edit → exact approval → simulated send, confirmed generation labels and model settings, and checked desktop/mobile layouts and hero playback. No live model call or real email was made.

## Still required for live release

### 1. Configure and verify a live Groq account

- Set `GROQ_API_KEY` and `GROQ_MODEL_ID` on the server, or configure a stable `COPILOT_ENCRYPTION_KEY` and save credentials through Connections.
- Verify actual model access, structured JSON generation, recoverable provider errors, and grounded drafts against representative leads.
- The current source-reference and hard-fact checks reduce unsupported output; they do not prove the truth of every generated sentence. Human review remains required.
- Full customizable agent playbooks (goals, tone, tools, saved instructions) remain planned. Model configuration is implemented separately.

### 2. Verify live HubSpot and Gmail accounts

- Follow [backend/README.md](backend/README.md) for OAuth credentials, encryption, and exact callback URLs.
- Use authorized test accounts to verify initial/repeat HubSpot sync, associated context, token expiry/refresh, disconnect, and one explicitly approved Gmail test send.
- Mocked tests exercise recovery and safety, but do not verify actual account scopes, provider delivery, or production deployment.

### 3. Finish deployment access and broader release validation

- Supabase login and workspace isolation are now implemented as the base described above. Hosted verification and broader team permission features remain pending; `COPILOT_ACCESS_TOKEN` is only a demo gate.
- Run backend checks: `.venv/bin/python -m pytest backend agent/test_copilot.py -q`.
- Run frontend checks from `frontend/`: `npm run typecheck` and `npm run build`.
- Broaden fixed-lead model evaluations, integration browser checks with configured accounts, and recovery UX tests. Model tests currently use mocked Groq responses.
- FastAPI startup still uses deprecated `on_event`; migrate to lifespan during maintenance.

## Publication and remaining cleanup

- The root `README.md` still describes the older Streamlit prototype. Rewrite it around the current Next.js/API setup before publication.
- The backend still imports `important_functions/scoring.py`; move that dependency before removing the old prototype.
- Decide whether to archive or delete the older Streamlit files. Preserve `LICENSE` and required attribution.
- Publication was prepared from an isolated checkout of `https://github.com/mitansh108/Relay---Outreach-AI-Agent.git` on `landing-page-optmised-supabase-base-ready`. This working folder inherits an unrelated home-directory Git repository; use the Relay checkout for future Git work. Private environment files, local databases, caches, and generated build output are excluded.

## Constraints

- No real send without separate approval for the exact recipient and draft version.
- Demo mode never delivers email. No autonomous email sequences or automatic mailbox reading.
- Credentials stay on the server; do not place keys in browser storage, public environment variables, API responses, logs, or checkpoints.
- Do not describe live Groq, OAuth, Gmail delivery, or a production deployment as verified until exercised with configured test accounts.
