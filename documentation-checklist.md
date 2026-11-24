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
