# CRM Outreach Copilot — Visual Plan

These diagrams describe the planned product in [PRODUCT_PLAN.md](PRODUCT_PLAN.md). They show the target architecture and workflows, not functionality already present in the current Streamlit demo. Mermaid diagrams render in GitHub and other Mermaid-compatible Markdown viewers.

## 1. User journey

```mermaid
flowchart LR
    A[Open app] --> B{Workspace mode}
    B -->|Sample| C[Seeded fictional leads]
    B -->|Connected| D[Sync HubSpot contacts]
    C --> E[Today action queue]
    D --> E
    E --> F[Inspect contact and source facts]
    F --> G[Review recommended action]
    G -->|Email| H[Edit and approve exact draft]
    G -->|Call| I[Create local task]
    G -->|Wait or no action| J[Record decision]
    H --> K{Workspace mode}
    K -->|Sample| L[Simulated send]
    K -->|Connected| M[Gmail API send]
    L --> N[Activity and insights]
    M --> N
    I --> N
    J --> N
```

## 2. Agent workflow and human approval

```mermaid
flowchart TD
    A[Contact selected] --> B[Gather contact, deal, notes, activity]
    B --> C{Eligibility rules}
    C -->|Blocked| D[Explain why and record no-send]
    C -->|Eligible| E[Model recommends next action]
    E --> F{Action}
    F -->|Email| G[Draft subject and body with source facts]
    F -->|Call task| H[Create local task after user decision]
    F -->|Wait or no action| I[Record recommendation]
    G --> J[Persist draft and interrupt graph]
    J --> K{Human review}
    K -->|Skip| L[Record skipped]
    K -->|Edit| J
    K -->|Approve exact version| M{Already sent?}
    M -->|Yes| N[Show existing result]
    M -->|No| O[Send once or simulate]
    O --> P[Record provider result and activity]
    D --> Q[Today queue updated]
    H --> Q
    I --> Q
    L --> Q
    N --> Q
    P --> Q
```

The rule check is deterministic and overrides the model. A separate idempotency record protects the external send if a workflow resumes or a user clicks twice.

## 3. System architecture

```mermaid
flowchart LR
    U[Salesperson in browser] --> W[Next.js web app]
    W --> API[FastAPI backend]
    API --> DB[(SQLite app records)]
    API --> LG[LangGraph workflow]
    LG --> CP[(Persistent checkpoints)]
    LG --> GROQ[Groq model API]
    API --> HS[HubSpot OAuth and CRM API]
    API --> GM[Gmail OAuth and send API]
    API --> SIM[Sample data and simulated sender]
    DB --> API
    CP --> LG
```

The browser receives records and connection status through the API. OAuth tokens stay encrypted on the backend. The sample path requires no HubSpot, Gmail, or Groq credentials; it uses seeded recommendations and drafts where needed for a reliable pitch demo.

## 4. Data flow and ownership

```mermaid
flowchart TD
    HS[HubSpot: CRM source] -->|OAuth read and sync| IMP[Import and field mapping]
    CSV[CSV: optional import] --> IMP
    IMP --> C[(Local contacts and context)]
    C --> R[Recommendation and draft]
    R --> A[(Approval and activity log)]
    A -->|Approved only| S{Mode}
    S -->|Sample| SIM[Simulated result]
    S -->|Connected| G[Gmail send API]
    G --> E[(Send attempt and message ID)]
    SIM --> E
    E --> I[Insights and contact timeline]
    A --> I
```

HubSpot fields are read-only in the first release. Local follow-up dates, manual reply status, drafts, approvals, and send results live in the app database. A CSV export lets users take the local records out.

## 5. Screen map

```mermaid
flowchart TD
    HOME[Today: prioritized queue] --> CONTACT[Contact workspace]
    HOME --> REVIEW[Review inbox]
    CONTACT --> REVIEW
    CONTACT --> ACTIVITY[Activity timeline]
    HOME --> INSIGHTS[Insights]
    HOME --> EXPERIMENTS[Experiments]
    HOME --> CONNECTIONS[Connections]
    CONNECTIONS --> HUBSPOT[HubSpot sync status]
    CONNECTIONS --> GMAIL[Gmail send status]
    CONNECTIONS --> SAMPLE[Sample mode]
```

The default pitch route is **Sample mode → Today → Contact → Review → Simulated send → Activity**. The connected route uses the same screens and replaces seeded records and simulated sending with HubSpot and Gmail.

## 6. A/B message testing

```mermaid
flowchart LR
    H[Hypothesis and one variable] --> T[Active two-variant test]
    T --> A[Stable contact assignment]
    A -->|Control| C[Control draft]
    A -->|Variant| V[Variant draft]
    C --> R[Individual review]
    V --> R
    R -->|Approved and sent| E[Exposure recorded]
    R -->|Skipped| S[No exposure]
    E --> O[Manual reply or conversion outcome]
    O --> D[Counts, rates, duration, cautious status]
```

Sample mode labels simulated sends and uses seeded outcomes. The results screen never declares a winner from a tiny sample.

## 7. Delivery milestones

```mermaid
flowchart LR
    A[1 Foundation and persistence] --> B[2 Frontend and sample journey]
    B --> C[3 Agent decisions and approval]
    C --> D[4 HubSpot and Gmail]
    D --> E[5 Pitch polish and verification]
```
