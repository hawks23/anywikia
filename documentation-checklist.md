# Documentation reconciliation — 2026-11-24

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
