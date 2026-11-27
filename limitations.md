# Current limitations

Anywikia implements reviewed writes and new entity creation, in addition to
extraction, resolution, comparisons, persistence and export/rebuild.

- **FastAPI deployment:** the backend is a local single-user app served by one
  Uvicorn worker. It does not provide user accounts or public-service authentication.
  Host/origin checks and a CSRF token protect local browser calls. Multiple workers
  need shared token/job state; writer locks alone do not solve that. Avoid reload
  during writes/rebuilds. A process shutdown can interrupt a background rebuild;
  existing setup recovery remains necessary. HTTP tests use TestClient and a
  disposable RDF backend; they do not certify live Docker/CampusAI behavior.
- **HTTP limits:** JSON bodies are limited to 500,000 received bytes and source
  text to 20,000 characters. Extraction still has its five-minute subprocess
  timeout. FastAPI does not accelerate model inference or graph rebuilds.

- **Scope:** 24 curated keyboard properties from a 30-property catalog. Seller,
  date, question and stored-query metadata are not editable through the catalog.
  Relationship targets must be confirmed existing local entities or explicitly
  created as labeled value entities. Creation does not infer a full ontology
  classification or enrich the new value entity from external sources.
- **Identity:** exact names/aliases and up to three fuzzy suggestions (distance
  below 3) do not prove identity. Creation checks exact existing names/aliases,
  but cannot guarantee semantic uniqueness. Users confirm matches and creation.
- **Candidate cache:** five-minute lazy in-process cache, invalidated after writes
  and rebuild. Candidates have P1 or the application's Keyboard type; other
  incompletely classified keyboards may be missed.
- **Extraction:** supporting sentences are unverified model output. Schema checks
  establish structure, not factual accuracy. English polyphony compounds are
  handled, but this is not a general number parser. Duplicate extracted values
  are alternatives in one editor, not multiple automatic writes.
- **Comparison:** no unit/currency conversion or general qualifier/reference/rank
  reasoning. Q199 is unitless and leaves physical measurements ambiguous.
- **Writes:** selected properties must pass actual graph/catalog datatype checks.
  Qualified, non-normal-ranked or ambiguous-quantity statements cannot be replaced.
  One explicit statement is replaced; unselected statements remain. Shared old
  quantity/reference nodes are retained, so orphan cleanup is not implemented.
- **Price:** DKK/EUR/USD/GBP are application choices, not RDF currency constraints.
  New price entries create linked offer entities. Seller/date may remain only in
  source evidence; no complete commercial offer extraction workflow exists.
- **Validation:** finite numeric values, integer counts, supported units, local
  entity references, URL/ID/media syntax. External existence and truth are not
  verified. New top-level entities require a name and at least one selected value.
- **Inspection:** entity inspection fetches only the selected entity and related
  offers/statements/quantity/reference nodes, with a 100,000-related-triple guard.
  Preview, commit, entity search and rebuild still use full snapshots; this change
  does not remove their whole-graph size limit. Targeted query equivalence was
  tested offline against RDFLib and the repository RDF; live QLever compatibility
  has not yet been verified from the editing environment.
- **Concurrency:** whole-graph snapshot/revision checks and a process/file lock
  coordinate application writers. External SPARQL writers bypass that lock and
  are unsupported. Snapshots are limited to 100,000 triples.
- **Persistence:** live updates are in QLever's persistent log until export/rebuild.
  Git carries only committed files, not ignored .anywikia state. Browser refresh
  loses the draft; JSON export is available but import is not implemented.
- **Verification:** equivalent decimals/plain strings are normalized for read-back.
  A saved operation marker prevents duplicate retries. Recorded-but-unverified
  results need inspection; a marker alone is not proof every expected triple is
  still present. Diagnostics record mismatched predicates or query error classes.
- **Rebuild:** staged index verification and rollback retain old generations and
  source backups; storage is not automatically reclaimed. Switching briefly
  interrupts queries. Rerun setup after an interrupted rebuild. Image upgrades
  and moving an existing managed runtime across OS paths are not automatic.
- **Input/services:** pasted text, 20,000 characters; CampusAI output defaults to
  8192 tokens, request timeout 180 seconds, subprocess limit 300 seconds. No
  automatic provider retries or extraction-accuracy benchmark is supplied.
- **Deployment:** loopback development server with local request protections,
  not a hardened public multiuser service. Keep API keys and access tokens private.
- **Validation evidence:** offline tests pass; user testing has shown live changes
  and exported RDF. Automated end-to-end browser, Docker restart/persistence and
  full rebuild compatibility checks have not all been run in this environment.

Keep original proposals as historical design documents. The exported dataset
contains user test edits and should not be mistaken for a pristine source dump.

- **Local QID allocation:** uses maximum existing numeric QID plus one, guarded
  by application locks and revision checks. It is not a durable never-reuse
  sequence: deleting the highest ID can allow reuse. Independent writers or
  future upstream imports can collide because local additions use the snapshot's
  original namespace. A dedicated namespace/central allocator is needed before
  independently merging datasets or deploying a distributed writer.

- **Uploaded sources:** one PDF/PNG/JPEG/WebP up to 20 MB; PDF rendering needs
  Poppler and OCR needs a vision-capable CampusAI model. Every page makes a model
  request; pdf2image holds rendered pages in memory. Long OCR output remains
  subject to the 20,000-character extraction limit, with full text retained for
  editing. There is no automatic batching or browser per-page progress stream.
  The 500,000-byte JSON body limit excludes `/ocr`, whose multipart body limit is
  20 MB plus form overhead. Uploaded files are not retained after the request.
