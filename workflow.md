# Current Anywikia workflow

Run `python tests/start_qlever.py` before `python handler.py "Source text"`.
The diagram describes implemented behavior, not the future population workflow.

```mermaid
flowchart TD
    A[Source text and CLI options] --> B[handler.py]
    B --> C[check_server: execute a minimal SPARQL query]
    C --> D[check_dataset: verify Keyboards item and property definitions]
    C -- Failure --> Z[Report error and stop before LLM request]
    D -- Failure --> Z
    D --> E[extract_entities: CampusAI returns typed claims grouped by keyboard and property]
    E --> F[Keep supporting sentences for human review]
    E -- API or validation failure --> Z
    F --> P[resolve_extraction: retain grouped models and validate catalog mappings]
    P --> G[For each keyboard: resolve subject once]
    G --> H[Attach mapped PID and catalog type to each property group]
    H --> I{Property expects an entity value?}
    I -- Yes --> J[Look up the extracted value name]
    I -- No --> K[Keep literal value and unit unchanged]
    J --> L[Attach unique IDs; warn for missing or ambiguous matches]
    K --> L
    G -- Local lookup failure --> M[Preserve grouped source claims and any already-resolved IDs; add warning]
    L --> N[Collect grouped keyboards, properties, claims and matching candidates]
    M --> N
    N --> O[print_results: grouped readable output or JSON]
```

The local graph supplies matching IDs, not fact values. Supporting sentences are not checked for exact wording
or semantic support. The CLI does not compare existing values or modify RDF. The website adds the
read-only comparison and draft-review workflow below. The two server checks are in
`functions/qlever_checks.py`; every step module can also be executed independently.

The raw extraction and resolved output are separate typed grouped models.
The handler never calls to_claims. Exact case-insensitive label/alias retrieval
is retained; fuzzy similarity remains unimplemented. Browser comparison does not
write, replace, or approve RDF statements.

## Website review workflow

Start `python web_app.py` and open http://localhost:8000 after starting QLever.

```mermaid
flowchart TD
    A[Source text in browser] --> B[Local web server runs grouped pipeline in subprocess]
    B --> C[Display keyboards, claims and ID candidates]
    C --> D{Unique or manually confirmed keyboard QID?}
    D -- Yes --> E[Fetch direct RDF properties and available quantity units]
    E --> F[Compare each claim by mapped PID]
    F --> G[Show existing, differing, new or uncertain value]
    E -- Request failure --> H[Show error and retry; do not classify as new]
    D -- No --> I[Review candidates or unresolved name]
    I --> D
    C --> J[Edit review draft; preserve original extraction]
    J --> D
    G --> K[Export original result and review draft as JSON]
    I --> K
```

Entity values compare resolved QIDs, including IDs found through aliases. Numeric
comparisons require compatible recognized units; conversion, qualifiers, ranks,
and property cardinality are not handled. Supporting context is model-provided
and remains unverified. Manual match confirmation and the add-entity demo affect
only the browser draft. Persistent approval, replacement, creation, and RDF writes
remain future work.
