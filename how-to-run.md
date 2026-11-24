# Running Anywikia

Use Ubuntu/WSL with Python 3.13. A fresh clone under `~/projects/anywikia`
avoids the mounted-directory problem observed in the Windows checkout. Use the
same environment for graph setup and the website.

## First-time setup, including QLever

Prerequisite installers: [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
and, optionally, [uv for Python installation](https://docs.astral.sh/uv/getting-started/installation/).

Install/start Docker Desktop on Windows and enable **Settings → Resources → WSL
Integration** for the Ubuntu distribution. In WSL, `docker info` must succeed.
A native Linux Docker Engine is also usable when its daemon is running and your
user has access. The Python helpers use Docker's command-line executable.

No preinstalled QLever server is required: the graph setup helper downloads its
Docker image, pins it locally, builds an initial index from the repository RDF,
and starts port 7072. `test_QLeverUI.py` separately downloads the query UI image
on first use. Do not run a manual legacy `qlever index`/`qlever start` sequence.

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

If Python 3.13 is not installed, install it before creating the environment. With
an existing `uv` installation, `uv python install 3.13` and
`uv venv --python 3.13 .venv313` provide an alternative environment setup.
Dependencies can then be installed with
`uv pip install --python .venv313/bin/python -r requirements.lock.txt`.

Set `CAMPUSAI_API_KEY` and `CAMPUSAI_MODEL` in `.env`. The example model is `chat`.
Optional settings: `CAMPUSAI_API_URL`, `LLM_TIMEOUT` (180 seconds by default), and
`LLM_MAX_TOKENS` (8192 by default). Never commit `.env`.
See README.md for environment and dependency details.

Setup below builds a dedicated writable index from `keyboards-index/keyboards.nt`
and pins the Docker image ID. It retains the original RDF and uses port **7072**;
the earlier container on port 7071 is untouched. Initial setup can take several
minutes. No manual `qlever index` step is needed.

## Start the website

```bash
cd ~/projects/anywikia
source .venv313/bin/activate
python tests/start_qlever.py
python functions/qlever_checks.py --check both
python web_app.py
```

Open **http://localhost:8000**. Keep this terminal open. Pipeline progress,
waiting messages, and errors appear here when a passage is submitted.
QLever runs separately at **http://127.0.0.1:7072**.
`python handler.py --setup-graph` is equivalent to the startup helper.

1. Paste text or choose **Load example**, then **Extract & match**.
2. Review the properties grouped under each keyboard. Names, values and units
   are editable; **Supporting context** contains LLM-provided sentences without
   exact-wording or semantic verification.
3. Under **Match the keyboard**, review **Did you mean…?** suggestions if shown.
   Expand **View stored properties**, then **Confirm this match**. The reviewed
   name/QID changes, choices collapse and your editable claims remain below.
4. Check comparisons: green means value exists; muted red means differing value;
   blue means no direct value is stored for that property; amber requires review.
   Unit ambiguity and unresolved entity values can prevent a definitive comparison.
   Unit conversion, qualifiers and ranks are not compared.
5. **Export review** downloads the original extraction plus your edited draft.
   This review format differs from CLI JSON. Refreshing loses the browser draft.

At four entities or more than twelve claims, compact mode activates automatically.
It uses collapsed entity summaries and a bounded scrolling pane. The view toggle
switches between compact and expanded modes without losing edits.

Count properties show **Unit (optional)**. For populated physical measurements,
enter a unit; missing or incompatible units block the RDF write preview.
Price (P25) uses a clickable currency dropdown with DKK, EUR, USD and GBP. These
are application choices, not currencies declared by the RDF. No default currency
is assumed. An unsupported source currency remains visible until you select one.
Try `The Yamaha P-150 is listed at 500 EUR.` and check the price and currency.
Draft export is still allowed with missing units; it is not approval to write RDF.
Existing prices require review of currency and offer context.

The extractor also handles explicit polyphony compounds such as `six-voice` and
`16-note`, retaining the supporting text and separating amount from unit.

## Save reviewed changes

1. Confirm an existing entity, or choose **Confirm this is a new entity** after
   reviewing the candidates. No match is only a candidate for discovery; inspect
   suggestions to avoid creating duplicates. Exact existing names/aliases block
   creation of another entity with the same name.
2. Edit extracted values. Use **+ Add property**, select a supported property and
   fill its value and required unit. Blank claims must be omitted from the save.
3. Existing records save only edited or explicitly selected properties. Editing
   a value checks **Include in this update** automatically. A single editable
   stored value is selected for replacement automatically; the row shows the old
   and new values. **Other save options** lets you retain old values and add another,
   or select a specific statement when several exist. New records include their
   extracted properties by default. Uncheck any property you do not want to save.
4. Click **Apply changes to QLever** (or **Create entity in QLever**). The app checks
   the selected changes and asks for one final confirmation showing the property
   names and values. It displays checking/applying progress, then **Changes applied
   and verified in QLever** after read-back. A failed/uncertain request retains the
   operation for **Check previous update**, even if you have edited the draft since.
   Resolving that operation preserves newer edits for a separate save. No field edit writes before this action.
5. Click **Query saved values**, or enter a QID and optional property in the bottom
   panel. The application shows its generated SELECT query and live results.

Repeated extracted values appear side by side under **Duplicate property values
extracted**. Choose one or enter a custom value; only one value is submitted for
that property. Automatic comparisons start only after identity confirmation, when
the card says **Now editing on QID**. Before confirmation it shows a possible match.

Query results display entity/property names and readable units; the raw query is
available under **Show SPARQL query**. Unitless Q199 means no measurement unit was
specified, except on count properties where a measurement unit is not needed.

Cards show the number of distinct properties, followed by the local match or
new-entity status. **+ Add property** sits below the property list; the entity's
apply/query controls stay visible at its bottom on desktop.

Supported units: length mm/cm/m, mass g/kg, power W, price DKK/EUR/USD/GBP.
Counts are nonnegative integers with optional count labels. Entity references
must already exist locally. URL, Wikidata ID and media filename checks validate
syntax, not external existence. Price is attached to a new offer linked to the
keyboard by P24, consistent with the dataset. Replacing a price edits the selected
offer's statement. Source text and review evidence accompany new statements.

Ordinary saves are immediately queryable and persist in QLever's update log;
they do **not** restart QLever or rewrite the source `.nt` file.
**Save to keyboards.nt and rebuild index** locks application writes, exports the live graph,
builds and verifies a fresh index, switches QLever, then updates
`keyboards-index/keyboards.nt`. Queries may briefly pause during the switch.
A failed switch attempts rollback to the previous index and source file.

Keep `.anywikia/`: it contains the active index, persistent updates, saved
previews, private access token, original RDF backup and retained old generations.
It is ignored by Git. Do not delete it to restart the app. Do not use external
SPARQL writers alongside this application; stale-preview protection assumes all
writes use its single-writer lock. The snapshot workflow is limited to 100,000
triples. Do not manually edit `keyboards.nt` expecting setup to import it after
the working runtime has been initialized.

If confirmation times out, retry the **same confirmation** or query the entity;
do not start another new-entity save. Operation IDs prevent duplicate retries.
For an interrupted rebuild, run `python tests/start_qlever.py` to recover.

## Start QLever and its query UI with one command

With Docker Desktop running and the project environment activated:

```bash
python test_QLeverUI.py
```

Open the printed URL (normally http://127.0.0.1:8178/default). The helper resumes
this checkout's persistent graph on 7072, prepares/reuses its own UI container,
and configures its endpoint on every launch. It does not rebuild the index or
write test RDF. Both containers continue running after the script exits.
UI state is retained in `.anywikia/query-ui/`. If 8178 is occupied by an older
UI, use `python test_QLeverUI.py --ui-port 8179`.

For the WSL working-directory problem, run the same script by absolute path
from `/tmp` with the project's `.venv313/bin/python`. The script adds its own
project directory to the import path. All lifecycle logic stays in functions/,
called through handler.py.

## CLI alternative

With the virtual environment active and QLever running:

```bash
python handler.py "The Yamaha P-150 has a width of 1385 mm."
mkdir -p outputs
python handler.py "$(cat sample_input.txt)" --json > outputs/result.json
python functions/display_results.py outputs/result.json
```

`--json` prints grouped JSON; shell redirection saves it. Progress goes to stderr.
Add `--quiet` to suppress progress. The CLI extracts and resolves IDs; the website
adds RDF value comparison and editable review.

Standalone tools:

```bash
python functions/extract_input.py "The Yamaha P-150 has a width of 1385 mm."
python functions/resolve_local.py
python functions/qlever_checks.py --check server
python functions/qlever_checks.py --check data
```

The resolver's built-in sample deliberately uses 999 cm to demonstrate that
lookup preserves extracted values. It does not change the stored width.

## Stop, restart and troubleshoot

- Stop the website with **Ctrl+C** in its terminal. Restart with `python web_app.py`.
- After Python changes, restart the server. After frontend changes, refresh the
  browser (export your review first if you need to keep it).
- If port 8000 is occupied, stop the earlier server in its terminal, or use
  `python web_app.py --port 8001` and open http://localhost:8001.
- Stop the managed QLever container using the container name printed by setup.
  Run `python tests/start_qlever.py` to resume it with its persistent updates.
- If Docker is unavailable, start Docker Desktop and check Ubuntu integration.
- If QLever checks fail, use `docker logs <container-name-from-setup>`.
  Fresh index build logs are under `.anywikia/generations/<generation>/build.log`.
- If extraction fails, read the server terminal and check CampusAI settings.
  The web request has a five-minute subprocess limit; shorter passages may help.
- Use the website rebuild button to export live edits and switch indexes safely.

## Checks before pushing

```bash
python -m unittest discover -s tests -v
node tests/test_comparison.cjs
node tests/test_review_plan.cjs
node tests/test_review_interactions.cjs
node --check frontend/app.js
node --check frontend/comparison.js
node --check frontend/rdf-review.js
node --check frontend/review-plan.js
git diff --check
```

Node.js is needed for the frontend rule/syntax checks, not to run the website.
Offline tests do not establish live provider availability. Also smoke-test the
website with a short passage and inspect one matched RDF record.

Use **documentation-checklist.md** to track documentation and diagram updates
throughout development and complete them immediately before pushing.

## Similar-name matching

After exact keyboard lookup fails, the website lazily fetches names/aliases and
QIDs into server memory. It suggests at most three distinct entities with
Levenshtein distance below 3. Confirm a suggestion manually or choose the new-entity
action. Records with P1 (key count) or the application Keyboard type are included.
The cache refreshes on demand after five minutes and is invalidated by writes,
rebuilds and server restarts; no JSON file is
created. It is not populated for successful or failed exact queries.


## Verify Q13 and migrate a checkout

In QLever UI (endpoint http://127.0.0.1:7072), execute:

```sparql
PREFIX kb: <https://keyboards.wikibase.cloud/entity/>
PREFIX kbt: <https://keyboards.wikibase.cloud/prop/direct/>
SELECT ?keys WHERE { kb:Q13 kbt:P1 ?keys . }
```

Run it once after applying an edit and again after a successful export/rebuild.
The UI queries the running graph, not the source file directly. To inspect the
exported file from WSL in the repository:

```bash
grep -F '<https://keyboards.wikibase.cloud/entity/Q13> <https://keyboards.wikibase.cloud/prop/direct/P1>' keyboards-index/keyboards.nt
```

Before moving to another checkout: export/rebuild, verify the source file, then
include that RDF file in the requested commit/push. Copy `.env` privately, create
a new virtual environment, and initialize a new managed runtime. Do not copy the
old venv. Stop the old managed graph container (name printed by setup) before
starting the new one on 7072. Retain the old checkout/backups until queries match.
Git does not transfer ignored runtime logs, indexes, tokens or unsaved browser drafts.

## Existing Windows-mounted checkout workaround

The existing checkout is at
`/mnt/c/Users/sweet/Desktop/Lecture notes/Sem-1/NLP/anywikia/anywikia`.
If Python cannot resolve that directory during startup, run by absolute path:

```bash
cd /tmp
project="/mnt/c/Users/sweet/Desktop/Lecture notes/Sem-1/NLP/anywikia/anywikia"
PYTHONPATH="$project" "$project/.venv313/bin/python" "$project/tests/start_qlever.py"
PYTHONPATH="$project" "$project/.venv313/bin/python" "$project/web_app.py"
```

For the query UI, use the same pattern with `$project/test_QLeverUI.py`.
This worked around the observed interpreter startup issue; its underlying WSL
mount/directory cause was not established. A fresh Linux-filesystem clone is
recommended. The extraction subprocess still uses the repo as its working
directory, so test extraction too if using this workaround.
