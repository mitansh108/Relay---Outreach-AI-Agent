# Remaining work

This is a handoff for the next agent. The product goal and acceptance criteria are in [PRODUCT_PLAN.md](PRODUCT_PLAN.md), with diagrams in [PRODUCT_DIAGRAMS.md](PRODUCT_DIAGRAMS.md). Use those files for the full scope; this document tracks what still needs to be finished.

## Current state

- The new Relay frontend is in `frontend/`. `/` is the landing page with a clickable four-step visual walkthrough; `/workspace` is the sample app. The user confirmed the landing page display is fixed.
- The FastAPI backend is in `backend/`. It stores contacts, recommendations, reviews, sends, activity, connections, and experiments in a local SQLite database. Demo mode uses fictional contacts and simulated sends.
- The newer LangGraph workflow is in `agent/copilot.py`. It applies eligibility rules, recommends an action, pauses for human review, and resumes an approved send through a backend hook.
- A/B test logic is in `agent/experiments.py`, with API and UI support. The original requirements are in `Skills/A/A/B_TEST.md`.
- The older Streamlit prototype is still present in `Main_app/`, `model/`, `important_functions/`, and older `agent/` modules. The backend currently imports `important_functions/scoring.py`, so that directory cannot simply be deleted.
- Root `.gitignore` has been updated for local secrets, dependencies, caches, build output, and SQLite files. This folder is **not yet a Git repository** and has no remote configured.

## Priorities

### 1. Make the new app understandable to a first-time user

- Walk through `/` and `/workspace` on desktop and mobile. Check navigation, the four walkthrough steps, sample-mode labels, and the complete Today → Contact → Review → simulated send → Activity journey.
- Improve guidance where a new user cannot tell what to click or what a result means. Keep fictional data and simulated actions clearly labeled.
- Fix any broken or unclear loading, empty, validation, and error states. Verify keyboard navigation and focus states.
- Acceptance: someone without credentials can complete the sample journey without developer assistance.

### 2. Add usable LLM configuration and generation

- The **new frontend has no LLM API key or model settings**. Its current sample recommendations and drafts use rules and templates. The older Streamlit prototype has a separate Groq key field; that is not connected to the new workspace.
- Decide how a single-workspace deployment configures the model and credentials securely. Keep secrets on the server, never in browser storage or API responses. Provide a clear connection/status UI and recovery message for missing access or an invalid model.
- Connect model-backed drafting to the bounded agent without bypassing eligibility rules or individual approval. Preserve a working credential-free sample mode.
- Add focused tests for successful generation, invalid credentials/model, weak context, and safe fallback.
- Acceptance: a configured user can produce a grounded draft in the new workspace, while the UI accurately identifies rule/template output when no model is configured.

### 3. Verify live HubSpot and Gmail flows

- OAuth and connector code exists in `backend/connectors.py` and `backend/main.py`, but live accounts have **not** been verified end to end. Follow setup notes in [backend/README.md](backend/README.md).
- With test accounts, verify connect, token refresh, HubSpot initial and repeat sync, imported context, Gmail sending of one explicitly approved draft, disconnect, and recoverable errors.
- Check that edited drafts need fresh approval, skipped drafts cannot send, and repeat clicks or graph resume cannot produce duplicate sends.
- Acceptance: one complete live flow works and failed/uncertain sends remain visible without automatic retries.

### 4. Complete the remaining release checks

- Verify pending reviews and history survive backend restart, including the LangGraph checkpoint.
- Check CSV validation and duplicate preview, manual reply handling, experiment exposure counts, stable variant assignment, and conservative winner status.
- Run backend tests and frontend typecheck/build after changes. Test the integrated sample journey in a browser.
- Check the plan against the implementation, especially access protection and integration error handling; document any deliberate release limits.

### 5. Clean the folder and prepare GitHub publication

- The user asked for cleanup but postponed it after requesting only `.gitignore`. Do this when they resume that work.
- Move the backend's shared scoring dependency out of `important_functions/` before removing old Streamlit-only files. Review all imports first.
- Replace the root `README.md`: it currently describes the previous owner's Streamlit app and links to their repository/live demo. Write setup and architecture instructions for the new Relay frontend and API, with honest feature status.
- Decide whether to retain the older prototype as a clearly marked archive or delete it per the user's request. Remove obsolete screenshots/assets and local tool files only after checking references. Preserve `LICENSE` and any required attribution.
- Check for credentials and personal data before committing. Then initialize Git, review the staged file list, and prepare a clean initial commit. Do not assume a GitHub remote or push destination.

## Important constraints

- Never send a real email without approval of its exact recipient and draft version. Demo mode must never deliver email.
- Do not claim that OAuth, LLM generation, or a production deployment has been verified until tested.
- Keep the project usable without external credentials for demonstrations.
- Avoid putting secrets or local SQLite data into Git.
