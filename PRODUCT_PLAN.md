# CRM Outreach Copilot — Product Requirements and Build Plan

## Product brief

**Goal:** Turn the current CSV and Streamlit demo into a polished sales follow-up copilot that can be pitched to small B2B teams and customized for one company at a time.

**Promise:** Open a follow-up queue, see who needs attention and why, review a context-aware next action, and keep the record current.

**First release:** A single-workspace demo application with seeded sample data and working HubSpot and Gmail connections. The complete demo must work without external credentials. Connecting real accounts demonstrates the same flow with live data. This is not a multi-tenant SaaS product.

**Primary user:** A salesperson managing follow-ups. A manager can inspect queue and activity, but team roles and permissions are deferred.

### Success criteria

- A prospect can explore the full sample-data workflow within two minutes.
- A connected user can sync HubSpot contacts, generate grounded recommendations, review each email, send through Gmail, and see the outcome recorded.
- No email is sent without separate approval for its exact recipient and draft version.
- Refreshing or restarting preserves contacts, recommendations, drafts, approvals, and send history.
- Connection, sync, model, and send failures show clear recovery actions.

### Release boundaries

No autonomous sending, email sequences, automatic mailbox reading, billing, multiple company workspaces, or claimed improvements in reply rates. Users mark replies manually in the first release. Calls become tasks; the app does not place calls.

### A/B message testing

The first experiment feature follows [Skills/A/A/B_TEST.md](Skills/A/A/B_TEST.md) and tests **one message element at a time**. A user creates a hypothesis, selects one variable (such as greeting, tone, or CTA), writes a control and one variant, chooses a 50/50 split, and starts or pauses the test. Assignment is deterministic per contact and experiment, so reruns never switch a contact's variant. Both variants still pass through individual human review before sending.

Show exposures as approved sends (or clearly marked simulated sends), not generated drafts. The user can mark replied and converted outcomes manually in this release. Results show counts, rates, duration, and a cautious status: collecting data, inconclusive, or eligible for a winner after the preset sample and duration requirements. Do not present significance or a winner from a small demo sample. Keep experiment and variant IDs on the recommendation, draft, send attempt, and outcome records for traceability. Sample mode includes a seeded experiment so the feature can be pitched without real sends.

## User experience

### Main journey

1. **Enter:** Choose **Explore sample workspace** or **Connect your accounts**. Sample mode is labeled clearly and simulates sending.
2. **Review Today:** See prioritized contacts with a due date, proposed action, and short reason. Filter by urgency, status, and action.
3. **Inspect:** Open a contact to see CRM fields, notes, related deal context, activity, prior drafts and sends, and the evidence behind the recommendation.
4. **Prepare:** The agent recommends `email`, `call_task`, `wait`, or `no_action`. Email recommendations include an editable subject and body grounded in source data.
5. **Decide:** Edit, approve this send, skip, or change the action. The approval applies to the exact draft version displayed.
6. **Record:** Show the simulated or Gmail send result, record activity, and suggest a next follow-up date. Never silently retry a send.
7. **Sync:** Show HubSpot and Gmail connection state, last sync, counts, errors, and a manual refresh action.

### Required screens

| Screen | Required behavior |
| --- | --- |
| Today | Focused action queue, urgency metrics, filters, clear reasons |
| Contacts | Searchable list, contact detail, notes, deal context, timeline |
| Review | Draft and source context side by side; edit, approve, skip |
| Activity | Recommendation, approval, send, failure, and manual reply events |
| Insights | Completed, pending, skipped, failed, and time-to-action counts based on observed events |
| Connections | OAuth connect/disconnect, last sync, errors, sample-mode controls |
| Experiments | Hypothesis, single variable, two variants, assignment and outcome counts, cautious results |

The interface should be light-first, responsive, keyboard accessible, and centered on **Today → Contact → Review**. Provide realistic seeded data plus deliberate loading, empty, and error states.

## Agent requirements

Replace the current fixed generate–review–send graph with bounded decision making:

1. **Gather:** Read the contact, company, deal, note, and activity context available locally or through predefined read-only HubSpot tools.
2. **Check hard rules:** Block an unusable email, do-not-contact or replied status, closed records without a scheduled follow-up, and recent sends. Rules override the model.
3. **Recommend:** Choose one of `email`, `call_task`, `wait`, or `no_action`; return a short reason and references to the source facts. Limit tool calls per recommendation.
4. **Draft:** Generate subject and body only for `email`. Surface insufficient context instead of inventing facts.
5. **Review:** Persist the draft and pause for a human decision.
6. **Execute:** Send an approved draft once, record provider response or error, and update the local timeline. A call action becomes a task; wait and no-action remain recorded recommendations.

Record model ID, prompt version, inputs, outputs, decision path, and human edits for debugging. The send operation must use a persistent idempotency key because graph nodes may run again after resume or retry. Every real send requires approval.

## Data connections

### HubSpot

- Use OAuth and a pinned, supported date-based API version.
- Import contacts with stable HubSpot IDs, associated company/deal context, and relevant notes or activities.
- Run an initial sync and incremental manual refresh; show field mapping and sync errors.
- Keep HubSpot read-only in this release. Local edits do not overwrite CRM fields.

### Gmail

- Replace app passwords and SMTP with Google OAuth and the Gmail API using `gmail.send`.
- Store the returned message ID and send outcome. An approved draft can be attempted once; a failure requires an explicit user retry decision.
- In sample mode, use a simulated sender with a visibly simulated result.

### CSV and replies

- Retain CSV import/export for demos and customization, with a preview of validation errors and duplicates before import.
- Give every imported record a stable local ID. Match synced CRM records by provider ID; do not silently merge on name alone.
- Provide **Mark replied**, immediately removing that contact from suggested follow-ups. Automatic mailbox reading is deferred.

## Technical architecture and interfaces

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, and a consistent component system. The current Streamlit app remains a reference during the rebuild.
- **Backend:** FastAPI. Refactor existing Python Groq and LangGraph code into services behind API endpoints.
- **Storage:** SQLAlchemy with SQLite for this portable single-workspace demo, including a persistent LangGraph checkpoint. Keep database access behind a repository layer so a company deployment can move to PostgreSQL.
- **Access:** One password-protected workspace session. Store OAuth tokens encrypted with a deployment secret, never in browser storage or API responses.
- **Execution:** The backend enforces contact eligibility, approval, exact draft version, workspace mode, and duplicate-send protection. No unattended scheduling in this release; recommendations and sync run on user request.

### Core records

`Contact`, `CompanyDealContext`, `Activity`, `Recommendation`, `DraftVersion`, `Approval`, `SendAttempt`, `Connection`, and `SyncRun`. A recommendation references a contact and its source facts. A send attempt stores its idempotency key, approved draft version, provider result, and timestamp.

### Backend interface groups

| Group | Behavior |
| --- | --- |
| Contacts | List/search/detail, CSV preview/import/export, mark replied, update local follow-up date |
| Recommendations | Generate for one contact or today's queue; return action, reason, sources, optional draft |
| Reviews | Edit, approve, skip, inspect draft and decision history |
| Sends | Execute only an approved, unsent draft; return simulated or Gmail result |
| Connections | OAuth start/callback/disconnect, status, HubSpot sync |
| Activity and insights | Read recorded events and aggregate observed counts |

## Build milestones

| Milestone | Deliverable | Exit check |
| --- | --- | --- |
| 1. Foundation | API, database, seeded demo, stable IDs, event history, workspace access | Data and pending reviews survive restart |
| 2. Frontend | Today, Contacts, Review, Activity, Insights, Connections | Full sample journey works on desktop and mobile |
| 3. Agent | Context gathering, eligibility, recommendation, grounded drafts, persistent human review | Every recommendation has a reason; rules cannot be bypassed |
| 4. Integrations | HubSpot OAuth/sync and Gmail OAuth/send | Live sync and one approved test send work; failures are visible |
| 5. A/B testing and pitch polish | Two-variant experiment, seeded results, guided demo, refined sample data, deployment guide | Assignment is stable, exposures and outcomes are traceable, and a new viewer completes the demo without credentials |

## Tests and acceptance

- **Demo:** With no credentials, inspect contacts, get recommendations, edit and approve a draft, and see a simulated send and activity event.
- **Connections:** Use a HubSpot test account and Gmail test user to verify sync and one approved send; expired tokens and OAuth errors are recoverable.
- **Safety:** Ineligible contacts cannot be sent to; edited versions need their own approval; double-clicks, retries, and graph resume cannot send twice; skipped drafts never send.
- **Durability:** Restart the backend during a pending review; the draft and review state remain available.
- **Data quality:** Cover missing fields, invalid dates/emails, duplicate CSV rows, repeated sync, and source records changed since the previous sync.
- **Agent quality:** Evaluate a fixed set of example leads for action choice, grounded facts, useful tone, and abstention when context is weak.
- **Experiments:** Assignment remains stable across reloads; one contact receives one variant; drafts are not counted as exposures; manual outcomes attach to sent messages; small samples never produce a winner; pausing prevents new assignments.
- **Frontend:** Verify keyboard navigation, narrow screens, empty/loading/error states, and the complete guided journey.

## Decisions and assumptions

- First buyer: small B2B sales teams. First CRM: HubSpot. First email provider: Gmail.
- One company workspace per installation; this is a customizable demo, not multi-tenant SaaS.
- Real integrations coexist with a credential-free sample mode.
- Each real send needs individual human approval. Reply status is manual in the first release.
- Groq remains the initial model provider; model ID and prompt version become configuration rather than source edits.

## Reference documentation

- [LangGraph interrupts](https://reference.langchain.com/python/langgraph/types/interrupt) and [persistent checkpoints](https://reference.langchain.com/python/langgraph/checkpoints)
- [HubSpot API versioning](https://developers.hubspot.com/changelog/introducing-date-based-api-versioning) and [webhooks for future sync](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/features/configure-webhooks)
- [Gmail send API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send) and [OAuth scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Next.js App Router](https://nextjs.org/docs/app)
