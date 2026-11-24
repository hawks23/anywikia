# Implemented workflow

The source diagrams below describe the current application. Original project
proposals are historical plans. See [how-to-run.md](how-to-run.md) for commands.

## User workflow

```mermaid
flowchart TD
    A[Paste keyboard text] --> B[Extract supported properties with CampusAI]
    B --> C[Show possible local matches and original evidence]
    C --> D{User confirms identity}
    D -->|Existing keyboard| E[Now editing on QID; enable RDF comparisons]
    D -->|New keyboard| F[New entity draft; no QID allocated yet]
    E --> G[Edit or select properties; resolve duplicate values]
    F --> G
    G --> H[Apply changes or Create entity]
    H --> I[Server validates datatype, units and current graph revision]
    I --> J[User confirms property and value summary]
    J --> K[SPARQL Update with persistent operation ID]
    K --> L[Read back values and report verification status]
    L --> M[Query saved values with readable labels]
    L -->|Unknown outcome| R[Check previous update; retain newer draft edits]
    R --> L
    M --> N[Optional: Save to keyboards.nt and rebuild index]
    N --> O[Lock writes; export live graph; build staged index]
    O --> P[Verify staged graph; switch server; publish source RDF]
    P --> Q[Query fresh index; previous generation retained]
    O -->|Failure before switch| S[Keep current graph and source]
    P -->|Switch failure| T[Attempt rollback; setup recovers interrupted rebuild]
```

![Review, save and rebuild workflow](mermaid-diagram.png)

The PNG is a compact companion rendering of the same main steps; the Mermaid
source above includes the branch and recovery detail. New records receive local
QIDs, labels and statements only on confirmed save. A price creates a linked
offer with P24 pointing to the keyboard and P25 carrying amount/currency.

## Programmer workflow

```mermaid
flowchart LR
    WEB[web_app.py HTTP adapter] --> HANDLER[handler.py graph_action]
    WEB --> REVIEW[handler.py review_action]
    REVIEW --> READ[functions/web_review.py: compare and isolated extraction]
    REVIEW --> SUGGEST[functions/similar_names.py: candidate suggestions]
    SETUP[tests/start_qlever.py] --> HANDLER
    UI[test_QLeverUI.py] --> HANDLER
    HANDLER --> SERVICE[functions/rdf_service.py]
    SERVICE --> MODEL[functions/rdf_models.py: catalog and validation]
    SERVICE --> STORE[functions/rdf_store.py: preview, update, verification]
    SERVICE --> RUNTIME[functions/qlever_runtime.py: Docker and generations]
    SERVICE --> QUERYUI[functions/qlever_ui.py: query editor]
    STORE --> MODEL
    STORE --> RUNTIME
    QUERYUI --> RUNTIME
    RUNTIME --> GRAPH[QLever 7072: base index plus persistent updates]
    RUNTIME --> FILE[keyboards.nt: exported on rebuild]
```

The extraction subprocess calls `handler.run_pipeline`: check server and dataset,
extract typed grouped facts, resolve local IDs, retain unresolved facts with
warnings, and serialize results. The CLI prints those results without writes.
The website adds lazy fuzzy suggestions and review; comparison is gated on manual
identity confirmation. Server-side graph operations remain in functions/.

Previews are stored server-side with exact RDF deltas, graph revision and operation
ID. Confirmation rejects stale/expired previews; operation markers make retries
idempotent. Read-back compares numeric decimal values and RDF-equivalent strings.
A recorded operation with different current triples is reported separately from
unknown outcomes and fully verified writes.

## Persistence boundaries

```mermaid
flowchart LR
    SAVE[Confirmed save] --> LIVE[Live QLever graph plus update log]
    LIVE --> QUERY[Immediately visible to queries]
    LIVE --> EXPORT[Explicit export and rebuild]
    EXPORT --> NT[keyboards-index/keyboards.nt]
    EXPORT --> INDEX[Fresh verified index generation]
    NT --> GIT[Requested commit and push includes exported RDF]
```

No automatic Git push occurs. Runtime state and credentials remain ignored.
The managed graph and the managed query UI use 7072 and 8178 respectively; the
website uses 8000. Legacy Qleverfile port 7071 does not configure these helpers.
