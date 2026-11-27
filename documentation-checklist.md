# Documentation reconciliation — 2026-11-24

## FastAPI migration — 2026-11-27

- [x] Replace built-in HTTP server with FastAPI/Uvicorn while preserving browser
  routes, explicit saves, graph locks, extraction subprocess and rebuild job.
- [x] Label and document the route, request-model and HTTP-protection layers in
  web_app.py, api_models.py and api_http.py. Keep domain logic in functions/.
- [x] backend-guide.md: explain the stack, every HTTP call, request fields,
  responses, errors, side effects, matching/drafts, preview/commit/retry and
  export/index switching. Include examples, a call diagram and reading order.
- [x] README.md: update architecture, code map and links to the detailed guide.
- [x] how-to-run.md: updated dependency install, compatible launcher, direct
  Uvicorn command, custom ports, one-worker rule, API docs and browser fixture.
- [x] workflow.md: update programmer diagram for Uvicorn/FastAPI and middleware.
  Main user/persistence diagram topology is unchanged; historical PNG retained.
- [x] limitations.md: document single-worker/local deployment, process interruption
  and request limits. Vector search remains a proposal, not implemented here.
- [x] Dependency resolution preserves previous pins and adds FastAPI/Uvicorn and
  their dependencies. Universal resolution targets Python 3.13; installation and
  tests used isolated Windows Python 3.14.8 in .venv-fastapi, not a WSL 3.13 run.
- [x] Validation: 119 Python tests, all three JavaScript suites and frontend syntax
  checks pass. Includes HTTP create/preview/confirm/retry/replace/verify against
  RDFLib, chunked-body size enforcement, error contracts and access protections.
- [x] Real Uvicorn localhost smoke: custom port, frontend assets, OpenAPI security
  schema, invalid source, rejected tokenless rebuild and private-file protection.
  Temporary server stopped afterward. Dependency consistency and whitespace checked.
- [ ] Live Docker/QLever/CampusAI and Playwright browser end-to-end checks were
  not performed for this migration. Playwright is not installed in this checkout.
  Existing mocked rebuild/recovery tests pass; no production compatibility claimed.

These migration notes describe this Windows checkout. The separate WSL checkout
has not been rewritten or synchronized, and no RDF source file has been changed.

## Pending: preserve review sections during confirmation

- [x] README.md/how-to-run.md: explain that confirmation and draft rerenders
  preserve open keyboard cards, nested review sections, the selected compact or
  expanded view, and scroll position. Fresh extractions use the default layout.
- [x] Regression coverage executes actual rendering and existing/new identity
  confirmation handlers with four compact cards, checking open/closed sections,
  manual density choices, changed names and scroll preservation. Existing save
  progress/retry interaction tests continue to pass. No live-browser test claimed.
- [x] Workflow diagrams: no data-flow or persistence changes required.

## Targeted entity inspection and catalog removal

- [x] Entity catalog removal: update README.md, workflow.md (including catalog
  diagram nodes), and how-to-run.md to remove generated entity_list.json claims.
  functions/entity_catalog.py now only provides the display-name helper. Setup,
  query-UI startup, confirmation and rebuild no longer export a name catalog or
  perform its extra full snapshot. The earlier completed catalog notes below are
  historical and superseded by this change. Property validation remains intact.
- [x] Follow-up live test attempt: Docker pipe access was denied and the QLever
  endpoint at 127.0.0.1:7072 refused connections even after Docker was started.
  No successful live-server test is claimed. No generated entity_list.json was
  present in this Windows checkout to delete; generation has been removed.

- [x] Offline validation: 111 Python tests pass, including five targeted
  inspection regressions; all three frontend comparison/planning/interaction
  suites pass. Tested using isolated Windows Python 3.14 environment with
  compatible dependencies, not the Python 3.13 lock environment.
- [x] Repository RDF comparison: Q1/Q13/Q34 return the same statement records
  with 97/171/142 related triples respectively versus 6,928 whole-graph triples.
- [ ] Live QLever compatibility/browser validation: Docker daemon and port 7072
  were unavailable; WSL execution was denied. Offline SPARQL execution uses RDFLib.

- [x] README.md and workflow.md: describe graph inspection as one bounded SPARQL
  query for the selected entity, linked offers, statements and quantity/reference
  metadata; inspection no longer returns an unused whole-graph revision.
- [x] limitations.md: distinguish targeted inspection's 100,000-related-triple
  guard from the unchanged full-snapshot limits in preview, commit, search and
  rebuild. Do not claim that all graph operations now scale independently of size.
- [x] Mermaid sources updated to remove catalog generation; inspection remains
  within the existing review step. The historical PNG is retained.
- [x] Preserve property_list.json: extraction and write validation actively read
  this cached catalog. The separate entity_list.json was the unused lookup input.

This review supersedes the earlier implementation queue. Reconcile affected docs
before each requested push; preserve original proposal documents as historical
material. Include exported RDF in requested pushes, not automatic application pushes.

## Completed for this push

- [x] README rewritten around implemented confirmed writes, editable/new entities,
  datatype/unit validation, price offers, persistence/rebuild and query verification.
- [x] Fresh-clone setup documents Python 3.13, venv dependencies, private .env,
  Docker Desktop installation/WSL integration and automatic QLever image/index setup.
- [x] how-to-run.md is canonical: Linux-filesystem checkout, startup commands,
  test_QLeverUI.py, port override, Q13 query, export/rebuild, rollback and migration.
- [x] Existing /mnt/c checkout workaround and unresolved directory-path cause are
  documented without promising that migration eliminates every runtime issue.
- [x] workflow.md includes user, module and persistence Mermaid diagrams. Updated
  mermaid-diagram.png is a compact companion rendering; visually inspected for
  readable text, arrows and complete steps. Branch details remain in Mermaid.
- [x] limitations.md distinguishes implemented functionality from remaining scope,
  single-writer/snapshot limits, unverified context, protected statements and UI tests.
- [x] UI walkthrough matches current buttons: Confirm this match with progress,
  Now editing on QID, duplicate-value choices, Apply/Create, Query saved values,
  Check previous update, and Save to keyboards.nt and rebuild index.
- [x] No obsolete UI screenshots are shipped. The walkthrough and diagram are
  current; new UI screenshots require a live visual session and are not fabricated.
- [x] Runtime files, private tokens, environments and credentials remain ignored.
- [x] Exported RDF parses successfully (6,928 triples). User-approved saved edits
  include Q1 keys 90, Q13 keys 60, Q34 keys 90 and Q34 width 135.6. Export also
  reorders triples, changes numeric serialization and blank-node identifiers.
  These are local review/test edits, not independently verified specifications.
- [x] Validation: 101 Python tests; comparison/unit/currency, review planning,
  duplicate choices, confirmation gate, loading/progress/retry interaction tests;
  JavaScript syntax and git whitespace checks. CLI help checked.
- [x] Earlier startup issue was followed by user running the app and querying
  saved values; shared exported RDF provides evidence of source export.

## Remaining validation limits (disclosed, not claimed complete)

- [ ] Automated live Docker restart/persistence and full rebuild rollback smoke
  test on the user's runtime. Offline tests use mocked Docker and in-memory RDF.
- [ ] Automated browser smoke and fresh UI screenshots. Browser access was denied
  earlier in this session; the latest UI was checked through offline interactions.
- [ ] Live test_QLeverUI.py launch on WSL. The launcher passed mocked lifecycle
  tests, but Windows could not reach the user's running QLever endpoint.
- [ ] Diagnose any remaining live recorded-but-unverified status using persisted
  mismatch predicates/read-error diagnostics. Equivalent decimals and xsd:string
  representations are covered by regression tests.

These limitations are also recorded in README.md and limitations.md. They do not
block the user's requested publication of the implemented code and documentation.


## Readability and orchestration cleanup

- [x] Move comparison SPARQL and extraction subprocess from web_app.py into
  functions/web_review.py; web adapters route through handler.review_action.
- [x] Document handler entry points and public RDF store/runtime/service methods.
- [x] Black-format orchestration, graph modules, launchers and affected tests.
- [x] README reading order and workflow module diagram include the read-only path.
- [x] Existing regression suite passes after refactor; functionality is unchanged.
- [x] Cleanup reviewed and grouped into the requested refactor, readability and
  documentation commits. All 101 Python tests and whitespace checks pass. The main user-flow
  PNG needs no topology change: these edits reorganize implementation boundaries.


## Candidate labels, entity catalog and new property-value entities

- [x] Candidate names load from live RDF before user confirmation; English labels
  are preferred deterministically.
- [x] functions/entity_catalog.py regenerates .anywikia/entity_list.json on setup,
  confirmed saves/retries and rebuilds. Failed cache refresh cannot undo or mask
  an acknowledged RDF write; it produces a separate warning.
- [x] Entity-valued properties identify missing IDs by property/name and allow
  explicit creation after search. Keyboard/value/offer IDs share the locked,
  revision-checked allocator; previews disclose new referenced entities.
- [x] README, run guide and limitations updated; 106 Python tests and JS checks pass.
- [x] Workflow creation branch and companion diagram updated for optional value
  entity creation and catalog refresh. Live visual testing remains outstanding.
  Changes are prepared in the Windows checkout for the requested push.


## Final requested publication

- [x] Launcher error suggests a different port rather than repeating the failed one.
- [x] Run guide distinguishes the root query-UI launcher from unittest modules,
  and explains occupied UI/server ports and how to run tests from the repo root.
- [x] QID allocation limits and namespace/upstream collision concerns documented.
- [x] No additional exported RDF changes are pending in this checkout. Previously
  committed snapshots remain included in history; runtime JSON/secrets stay ignored.
- [x] 106 Python tests plus JavaScript rule, interaction and syntax checks pass.
- [ ] End-to-end live/browser checks remain limited as described above; this push
  does not certify production readiness or close those validation gaps.
