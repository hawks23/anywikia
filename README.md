# Anywikia

Extract musical-keyboard facts from text with CampusAI, review them against a local
Keyboards Wikibase graph, and save explicitly confirmed changes to QLever.

The CLI extraction pipeline is read-only. The website adds human confirmation,
property editing, new entities, persistent RDF writes, verification queries, and
export/rebuild of `keyboards.nt`. The graph supplies matching IDs; it does not
replace extracted facts with stored values.

## Install and run

The backend uses **FastAPI**, served locally by **Uvicorn**. The browser uses plain
JavaScript, HTML and CSS. CampusAI extracts typed facts; QLever stores the RDF.
For a step-by-step explanation, API call table, examples and library descriptions,
read [Understanding the backend](backend-guide.md).

Prerequisite installers: [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
and, optionally, [uv for Python installation](https://docs.astral.sh/uv/getting-started/installation/).

Recommended: Ubuntu/WSL, Python **3.13**, and Docker Desktop with integration enabled
for your Ubuntu distribution. Keep a new checkout in WSL's Linux filesystem.

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/hawks23/anywikia.git
cd anywikia
python3.13 -m venv .venv313
source .venv313/bin/activate
python -m pip install -r requirements.lock.txt
cp -n .env.example .env
```

Set `CAMPUSAI_API_KEY` and `CAMPUSAI_MODEL` in `.env`. Never commit credentials.
If Python 3.13 is unavailable, install it first (for example with `uv python install
3.13`, then `uv venv --python 3.13 .venv313`).

**No QLever installed?** Start Docker Desktop, enable **Settings → Resources → WSL
Integration** for Ubuntu, and check `docker info` from WSL. The startup helper
fetches the QLever Docker image, pins its image ID locally, builds the initial
index from the included RDF, and starts the server. A separate native QLever
installation or manual `qlever index` command is not needed. The Python lock file
also includes the QLever CLI and dependencies used by the project.

```bash
python tests/start_qlever.py
python web_app.py
```

Open **http://localhost:8000**. The writable QLever endpoint is
**http://127.0.0.1:7072**. First startup can take several minutes.

For QLever's own query editor, run this in another activated terminal:

```bash
python test_QLeverUI.py
```

Open the printed URL, normally **http://127.0.0.1:8178/default**. This helper
starts/resumes the graph and its query UI. Use `--ui-port 8179` if 8178 is occupied.
The UI image is downloaded on first use. Containers keep running after the helper
exits. See [how-to-run.md](how-to-run.md) for the complete guide, WSL path workaround,
verification queries, migration and recovery.

## Review and save

1. Paste text and choose **Extract & match**. Each card reports distinct properties
   extracted. Suggested IDs remain unconfirmed until you inspect the candidate.
2. Click **Confirm this match**. A spinner appears during lookup; the card then
   says **Now editing on QID** and comparisons become available. Alternatively,
   explicitly confirm a new entity after checking candidates.
3. Edit values. Existing records include only edited/selected properties. A single
   stored editable value is automatically selected for replacement. Use **Other
   save options** for multiple statements or to retain an old value and add another.
   Duplicate extracted values share one editor: choose an alternative or enter
   your own. **+ Add property** adds a supported property not already displayed.
4. Click **Apply changes to QLever** or **Create entity in QLever**, then confirm
   the property/value summary. The UI reports progress and read-back verification.
5. Use **Query saved values** to inspect readable entity/property/unit names and
   optionally reveal the generated SPARQL query.
6. When ready, click **Save to keyboards.nt and rebuild index**. This exports the
   live graph, builds/verifies a fresh index and switches QLever to it.

Confirmation and draft rerenders preserve open cards, nested sections, your
compact/expanded view choice and scroll position. Fresh extractions use the
default layout.

A field edit alone never writes RDF. New entity IDs and full statements are
allocated server-side. Entity-valued properties can explicitly create a missing
value entity after searching; its label and QID are included in the same save. Prices create offers linked to keyboards by P24; P25 is
stored on the offer. Existing prices can be replaced by selecting their statement.

## Persistence and validation

| Action | Running graph | Source `keyboards.nt` |
| --- | --- | --- |
| Confirm a save | Updated immediately; persistent update log | Unchanged |
| Export and rebuild | Switches to verified fresh index | Updated from live graph |

Ordinary saves need no restart. Rebuild locks application writers and briefly
interrupts queries during the switch. Prior generations and source backups are
retained. Run setup again to recover an interrupted rebuild.

The server validates property mappings against the actual graph, value datatypes,
units, confirmed existing or explicitly created entity references, and the preview's graph revision. Counts are
nonnegative integers; length accepts mm/cm/m, mass g/kg, power W, and price
DKK/EUR/USD/GBP. Count units are optional. Q199 on a physical measurement means
no measurement unit was specified; it does not imply mm, cm, or kg. URLs,
Wikidata IDs and media filenames receive syntax checks, not online verification.

If the result is uncertain, **Check previous update** checks/completes the original
operation without creating a second entity. Newer draft edits are preserved.
A recorded update with a verification mismatch is distinguished from a fully
verified save; diagnostic predicates are retained server-side.

Candidate display names are fetched from the live graph before confirmation.
Entity inspection uses one targeted query for the selected entity, linked offers,
statements and quantity/reference metadata, without a whole-graph revision hash.
Exact lookup queries QLever; fuzzy suggestions use a lazy in-memory name cache.
The unused entity_list.json export is no longer generated or required. Existing
copies in older checkouts are ignored and can be deleted without changing RDF.

Keep `.anywikia/`: it holds indexes, persistent updates, private access tokens,
operation previews, UI state and backups. It is ignored by Git. Browser drafts
are not durable; **Export review** preserves original extraction and draft JSON,
but importing that export is not implemented. Do not use external SPARQL writers
alongside the application's single-writer workflow.

## Code organization

```text
handler.py                Main orchestrator and graph action dispatcher
web_app.py                FastAPI routes, frontend files and Uvicorn launcher
api_models.py             Typed HTTP request fields and strict approval booleans
api_http.py               Local request protections, body limit and error responses
test_QLeverUI.py          One-command graph/query-UI launcher
tests/start_qlever.py     Compatibility graph setup launcher
functions/
  extract_input.py        CampusAI extraction and supporting context
  pydantic_models.py      Curated extraction schema and catalog mapping
  resolve_local.py        Local entity/name resolution
  resolved_models.py     Grouped resolved records
  similar_names.py       Lazy fuzzy-match cache
  web_review.py          Read-only comparison queries and extraction subprocess
  entity_catalog.py      Readable graph entity-label helper
  rdf_service.py         Graph workflow and background rebuild jobs
  rdf_models.py          Trusted write schema and datatype/unit checks
  rdf_store.py           Preview, SPARQL updates, verification and queries
  qlever_runtime.py      Docker lifecycle, persistence, rebuild and rollback
  qlever_ui.py           Managed QLever query UI
  qlever_checks.py       Server/dataset checks
  display_results.py     CLI output
  progress.py            Progress reporting
frontend/                 Plain JavaScript/CSS review interface; no build step
property_list.json        Catalog of 30 local properties; 24 supported for review
keyboards-index/          Versioned RDF and legacy Qleverfile
```

The legacy Qleverfile targets 7071 and is retained as a reference. The application
uses the managed 7072 runtime; its helpers do not use the legacy server settings.
CLI extraction remains available with `python handler.py "Source passage" --json`.

## Reading the code

Start with `handler.py`: `run_pipeline` coordinates extraction, `review_action`
coordinates read-only browser helpers, and `graph_action` dispatches persistence
and lifecycle operations. `web_app.py` translates HTTP requests/responses and
forwards application operations to that handler. CLI launchers do the same.

Follow an operation into `functions/rdf_service.py`, then its implementation in
`rdf_models.py` (validation), `rdf_store.py` (RDF), or `qlever_runtime.py` (Docker
and indexes). Read-only browser work lives in `functions/web_review.py`. Public
entry points and the runtime/store operations have docstrings explaining purpose
and side effects. Frontend interactions stay in `frontend/`; they send requests
rather than implementing backend persistence.

The orchestration and graph modules use conventional Black-formatted Python.
The full call map and persistence boundaries are in [workflow.md](workflow.md).
The detailed function walkthrough and HTTP contracts are in
[backend-guide.md](backend-guide.md). With the website running, `/docs` exposes
the interactive API reference and `/openapi.json` its schema. Use one web worker;
the runtime remains a local single-user application.

## Limits and testing

The current workflow targets a small local graph (at most 100,000 triples).
Supporting sentences are model-generated and not verified for truth or exact
quotation. Fuzzy suggestions require human confirmation; no match does not prove
an entity is new. Unit conversion and general qualifier/rank editing are not
implemented. See [limitations.md](limitations.md) for the full scope.

```bash
python -m unittest discover -s tests -v
node tests/test_comparison.cjs
node tests/test_review_plan.cjs
node tests/test_review_interactions.cjs
node --check frontend/app.js
node --check frontend/comparison.js
node --check frontend/review-plan.js
node --check frontend/rdf-review.js
git diff --check
```

Node is needed for frontend tests, not to run the website. Offline tests exercise
RDF updates using RDFLib and mock Docker lifecycle operations; they are not a live
QLever compatibility guarantee. User testing established visible saved values and
an exported RDF snapshot; full automated browser and restart/rebuild checks remain
outstanding in this environment.

## Versioned RDF and migration

Include exported `keyboards-index/keyboards.nt` in requested commits/pushes.
The application does not automatically commit or push. Live updates absent from
that file will not transfer through Git. Export/rebuild before migrating and keep
the old checkout until the new checkout's queries match. The current RDF includes
local review/test edits; it is not a pristine upstream snapshot or a statement of
verified keyboard specifications. Reordering and numeric lexical changes may
accompany QLever export.

See [workflow.md](workflow.md) for diagrams and
[documentation-checklist.md](documentation-checklist.md) for release evidence.
