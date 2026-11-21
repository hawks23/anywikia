# Running Anywikia

Run commands in Ubuntu/WSL from `~/anywikia`. Windows location:
`\\wsl.localhost\Ubuntu-22.04\home\sweet\anywikia`.

## First-time setup

Start Docker Desktop with Ubuntu WSL integration enabled. Then:

```bash
cd ~/anywikia
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
# Only if .env does not already exist:
cp -n .env.example .env
```

Set `CAMPUSAI_API_KEY` and `CAMPUSAI_MODEL` in `.env`. The example model is `chat`.
Optional settings: `CAMPUSAI_API_URL`, `LLM_TIMEOUT` (180 seconds by default), and
`LLM_MAX_TOKENS` (8192 by default). Never commit `.env`.
See README.md for environment and dependency details.

Generated QLever indexes are not committed. If the index is missing, build it once:

```bash
cd ~/anywikia/keyboards-index
../.venv/bin/qlever index
cd ..
```

## Start the website

```bash
cd ~/anywikia
source .venv/bin/activate
python tests/start_qlever.py
python functions/qlever_checks.py --check both
python web_app.py
```

Open **http://localhost:8000**. Keep this terminal open. Pipeline progress,
waiting messages, and errors appear here when a passage is submitted.
QLever runs separately at **http://127.0.0.1:7071**.

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

**Use as new entity (demo)** remains available under **Inspect or change match**,
even after confirmation. It clears the selected ID, restores the extracted name
unless manually edited, and preserves claim edits. It displays **ENTITY ADDED !** only. Neither edits,
comparisons, match confirmation nor this button writes to the RDF.

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
- Stop QLever separately with `docker stop qlever.server.anywikia`.
- If Docker is unavailable, start Docker Desktop and check Ubuntu integration.
- If QLever checks fail, inspect `keyboards-index/keyboards.server-log.txt`.
- If extraction fails, read the server terminal and check CampusAI settings.
  The web request has a five-minute subprocess limit; shorter passages may help.
- Changing the RDF file does not update a running index. Stop QLever, rebuild
  from `keyboards-index`, then start it again.

## Checks before pushing

```bash
python -m unittest discover -s tests -v
node tests/test_comparison.cjs
node --check frontend/app.js
node --check frontend/comparison.js
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
demo. Only records with P1 (key count) are currently included. The cache refreshes
on demand after five minutes and is cleared by a server restart; no JSON file is
created. It is not populated for successful or failed exact queries.
