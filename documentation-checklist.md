# Documentation update tracker

Keep this file current as code changes. Record affected documents and concrete
pending edits during implementation; finish the documentation pass immediately
before pushing. A checked item means reviewed against current behavior, not just
that the file exists. Reset affected items when later changes make them stale.

## Pre-push review — 2026-11-21

- [x] **how-to-run.md** — updated on 2026-11-21 with setup, website/CLI commands,
  logging, review, comparison, compact mode, stopping/restarting, and checks.
- [x] **how-to-run.txt** — obsolete file removed; how-to-run.md is canonical.
- [x] **README.md** — reconcile feature status, examples, run commands and links
  with the final changes in this branch; distinguish browser comparison from CLI.
- [x] **limitations.md** — replace the outdated five-property scope with the
  current 23 supported properties; reflect implemented browser comparison and
  review export, unverified supporting context, and remaining RDF-write work.
- [x] **workflow.md** — review both CLI and website diagrams against the final
  pipeline, candidate selection, comparison, errors, and review export.
- [x] **mermaid-diagram.png** — check whether it reflects workflow.md; regenerate
  any outdated rendered diagram from the final Mermaid source before pushing.
- [x] **Code docstrings and CLI help** — check functions/, handler.py and web_app.py
  for obsolete exact-evidence validation or flattened-output descriptions.
- [x] **Final verification** — check links, commands, example output shapes and
  implementation-versus-planned labels; summarize validation in the commit.

## Change-to-document map

| Change | Review/update |
| --- | --- |
| Setup, dependencies, environment, ports or startup | how-to-run.md, README.md, .env.example when relevant |
| Extraction models, prompts, supported properties or evidence | README.md, limitations.md, workflow.md, model examples/docstrings |
| QID/PID lookup, candidate handling or comparison | README.md, limitations.md, workflow.md, affected module docs |
| Website controls, compact mode, editing or export | how-to-run.md, README.md, website workflow diagram |
| Pipeline ordering, error paths or new stages | workflow.md and mermaid-diagram.png, handler/module docstrings |
| Implemented limitation or new known gap | limitations.md and README.md status/roadmap |
| Test commands or required checks | how-to-run.md and README.md testing instructions |
| RDF schema/catalog changes | property_list.json consistency, README.md, limitations.md, model documentation |

The original **Project Proposal.docx** and **Project Proposal.pdf** are historical
proposal artifacts. Preserve them; do not rewrite them to reflect implementation
changes unless explicitly requested. RDF/index files are data/runtime artifacts,
not documentation to regenerate during the documentation pass.

## Before each push

1. Inspect the full diff since the last push and add any missing documentation tasks.
2. Complete each affected pending item; mark irrelevant items with a reason.
3. Review diagram source and rendered images together. Do not present an old image
   as the current workflow.
4. Verify commands and examples, run relevant checks, and ensure secrets/generated
   outputs are excluded from the commit.
5. Update this checklist with the review date and outcomes, then commit and push
   only when requested. Preserve a record of completed items until a new change
   makes them pending again.

No automated sync or background monitoring is installed; this checklist and
AGENTS.md are the repository's persistent maintenance instructions.

## Output limit change — 2026-11-21

- [x] Set CampusAI default and .env.example to 8192 output tokens; updated local .env.
- [x] Updated README.md and how-to-run.md token-limit references.
- [x] Before push, verify final configuration examples still match the code.
- Workflow diagrams and limitations need no change for this setting alone.

## Lazy similar-name suggestions — documentation review

- [x] README.md / how-to-run.md: document “Did you mean” suggestions after exact
  keyboard lookup fails, manual confirmation and reuse of RDF comparison.
- [x] limitations.md: distance < 3, top three distinct QIDs, P1-based keyboard
  candidate scope (records without key counts excluded), no automatic linking.
- [x] workflow.md / rendered diagram: add lazy server-cache and suggestion path.
- [x] Document five-minute lazy refresh, per-server-process memory only, restart
  clearing cache, and future cache invalidation after real RDF/index updates.
- [x] Added cache-update TODO in functions/similar_names.py for new QID, name and aliases.

## Timeout change — 2026-11-21

- [x] CampusAI default, local .env and .env.example now use 180 seconds.
- [x] Website subprocess limit raised to 300 seconds to leave room for RDF lookups.
- [x] Updated README.md and how-to-run.md timeout references.
- [x] Recheck timeout instructions against final code before pushing.

## Match-first review flow

- [x] README.md / how-to-run.md: explain matching above extracted values; confirmation
  replaces the reviewed name/QID, retains source name and editable claims, collapses
  choices and refreshes comparisons. Original extraction stays in the export.
- [x] workflow.md: reflect identity selection before compact claim editing.

- [x] UI guide/screenshots: distinct “Match the keyboard” and “Review the values”
  sections, prominent suggestion cards and direct confirmation buttons.

- [x] Match-choice guide: “Use as new entity (demo)” stays available after
  confirmation; clears selected QID/comparisons, restores source name, preserves
  edited claims and allows switching back to an existing record. No RDF writes.

Validation: 49 Python tests, 11 JavaScript comparison checks, JavaScript syntax
checks, git diff whitespace check and both live QLever checks passed. UI behavior
was exercised during implementation; no new live LLM call was needed for this
documentation/configuration pass. Secrets remain ignored. Proposal and RDF/index
files are unchanged.

Rendered the website Mermaid block from workflow.md into mermaid-diagram.png
and visually checked its readable nodes and branches. All current queue items
are complete; reopen affected items when implementation changes again.
