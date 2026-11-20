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
    E --> F[Validate exact evidence quotations against input]
    E -- API or validation failure --> Z
    F -- Invalid quotation --> Z
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

The local graph supplies matching IDs, not fact values. Exact quotation presence
does not prove semantic support. This pipeline does not compare existing values,
approve claims, or modify RDF. The two server checks are in
`functions/qlever_checks.py`; every step module can also be executed independently.

The raw extraction and resolved output are separate typed grouped models.
The handler never calls to_claims. Exact case-insensitive label/alias retrieval
is retained; fuzzy similarity and duplicate-claim comparison remain unimplemented.
