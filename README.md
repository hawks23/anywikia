# Anywikia

Extract musical-keyboard facts from source text with CampusAI, attach matching
local Keyboards Wikibase IDs, and display the results with LLM-selected supporting context.
The local RDF informed the supported property catalog and supplies matching IDs
at runtime; it never replaces extracted values or units.
The CLI pipeline is read-only. The website adds stored-value comparison and
editable review drafts; approved RDF updates and population remain future work. See [workflow.md](workflow.md) for the current flowchart and
[limitations.md](limitations.md) for follow-up work.

## Structure

```text
handler.py                      # Main entry point and step orchestration
web_app.py                      # Local web server and read-only RDF inspection
frontend/                       # Browser review UI and value comparison rules
functions/
  extract_input.py              # LLM extraction and supporting context
  pydantic_models.py            # Typed extraction and catalog validation
  resolve_local.py              # Grouped QID resolution and mapped PIDs
  resolved_models.py            # Application-owned grouped result models
  qlever_checks.py              # Server and dataset checks
  progress.py                   # Progress messages and elapsed-time reporting
  display_results.py            # Readable or JSON output
property_list.json              # Catalog of 30 local RDF property definitions
local_rdf.py                    # Shared endpoint and file paths
tests/start_qlever.py            # Docker startup and readiness
keyboards-index/                # RDF, QLever config, generated indexes and logs
workflow.md                     # Mermaid flowchart
tests/test_extraction_pipeline.py # Offline pipeline regression tests
tests/test_pydantic_models.py    # Typed models and catalog consistency tests
```

The old app.py entry point, root extraction/resolution modules, public Wikidata
resolver, experimental try.py, and old test.py were removed. Their active roles
are now covered by the handler and functions package. Proposal files and RDF/index
files are retained.

## Setup in Ubuntu / WSL

Verified environment: Ubuntu-22.04, Python 3.13, Docker Desktop with Ubuntu WSL
integration enabled. Keep the checkout in the Linux filesystem, e.g. ~/anywikia.
Start Docker Desktop and wait until `docker info` succeeds.

```bash
git clone https://github.com/hawks23/anywikia.git
cd anywikia
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
# First installation only; preserve an existing .env:
cp .env.example .env
```

Set CAMPUSAI_API_KEY and CAMPUSAI_MODEL in .env for extraction. Optional settings
are CAMPUSAI_API_URL, LLM_TIMEOUT, and LLM_MAX_TOKENS. Local lookups and checks need no credentials.
The lock file records installed versions; requirements.txt allows broader versions.
With uv, use `uv venv --python 3.13 .venv` and
`uv pip install --python .venv/bin/python -r requirements.lock.txt`.

Generated indexes are excluded from Git. On a fresh clone, build once:

```bash
cd keyboards-index
../.venv/bin/qlever index
cd ..
python tests/start_qlever.py
```

The endpoint is http://127.0.0.1:7071; the container is qlever.server.anywikia.
It mounts this checkout's keyboards-index directory at /index. The startup helper
uses paths relative to its own script and verifies the container mount.
Stop with `docker stop qlever.server.anywikia`. Stop and rebuild the index after
changing keyboards.nt; editing RDF alone does not change the running index.

## Local review website

On the `front-end` branch, start QLever and the local web server:

```bash
cd ~/anywikia
source .venv/bin/activate
python tests/start_qlever.py
python web_app.py
```

Open **http://localhost:8000**. Use `--port 8001` if needed. No additional Python
packages or frontend build step are required. CampusAI credentials remain in `.env`
on the server; extraction uses the existing handler in an isolated subprocess.
Pipeline progress, waiting messages and errors stream live to the terminal running
`web_app.py`; JSON results are sent separately to the browser. Restart the web
server after changing Python code to load the changes.

- Paste text or load the example, then choose **Extract & match**.
- Review claims grouped by keyboard. Edit names, values and quantity units.
  With four or more entities, or more than twelve claims, results automatically
  switch to compact mode: collapsed entity summaries in a scrollable pane, with
  one entity open at a time. Toggle compact/expanded view at any time; edits and
  loaded RDF details are preserved.
- Expand **Inspect RDF record** for each candidate to fetch its stored direct
  properties, labels and available quantity-unit URIs from QLever. Qualifiers and
  references are not displayed. **Confirm this match** records a manual decision.
- Unmatched names offer **Add new entity (demo)** and show **ENTITY ADDED !**.
  This is a placeholder: no RDF file, index or server data is modified.
- **Export review** downloads the original result and a separate editable review
  draft. Reloading the page loses the draft. Evidence stays unchanged. Edited
  values are not automatically re-resolved or validated as facts; changing a
  value clears its value ID, and changing a name clears its manual match decision.
  Original automatic IDs remain available as historical lookup results.

This is a local development UI, bound to loopback. It is not a public multiuser
server. Exact label/alias matching is unchanged; an unmatched name is not proof
of a new entity. Lookup failures do not enable the add placeholder. Property PIDs
remain fixed by the supported schema. Review exports are separate from the
handler's JSON format and are not currently importable into the CLI.

## Run the complete pipeline

```bash
cd ~/anywikia
source .venv/bin/activate
python tests/start_qlever.py
python handler.py "The Yamaha P-150 has a width of 1385 mm."
python handler.py "The Yamaha P-150 has a width of 1385 mm." --json
```

The handler calls each step explicitly:

1. check_server confirms that the endpoint executes a minimal SPARQL query.
2. check_dataset verifies known Keyboards item/property definitions exist.
3. extract_entities sends the passage and the typed model schema to CampusAI,
   returning claims grouped by keyboard and property with supporting sentences.
4. resolve_extraction enriches the grouped model directly: resolve each keyboard
   once, attach catalog-validated PIDs, and resolve entity-valued claims.
5. print_results prints keyboards with nested property claims or grouped JSON.

Preflight failures stop before the LLM request. Extraction errors stop the run.
If a later lookup fails, the fact and mapped PID are retained with unresolved
entity IDs and a warning.
Unknown or ambiguous names are not guessed. Source evidence being present does
not prove it supports the extracted claim. Units are preserved without conversion.
No source facts are retrieved from the RDF to complete the extraction.

### Extraction schema and output formats

`property_list.json` records 30 properties from the local RDF, including labels,
descriptions, Wikibase value types, predicate mappings, and observed datatypes and
units. `functions/pydantic_models.py` defines a curated set of **23 keyboard
properties** based on that catalog. Offer, seller, price, date, and stored-query
metadata are outside this extraction model. The model is defined in Python; it
is not regenerated from the RDF or JSON catalog on each request.

The LLM receives the source passage, extraction instructions, and the Pydantic
schema with property descriptions. It fills supported fields only. Descriptions
include our extraction guidance, which is not a constraint declared by the RDF.

| Property kind | Pydantic claim value | Example |
| --- | --- | --- |
| Quantity, including counts | Finite `Decimal`, plus nullable source unit | width: 1385, unit: mm |
| Entity relationship | Name as `str`, pending ID resolution | manufacturer: Yamaha |
| Text, URL, external ID, media filename | `str` copied from input | explicitly supplied product URL |

Every property is a list of claims with evidence. Unmentioned properties are
empty lists; repeated or conflicting claims remain separate. Units are copied
from the source without conversion; an absent unit is `null`. Observed RDF unit
URIs do not justify inventing a source unit.

Extraction-only output is grouped. This shortened example omits empty fields:

```json
{
  "entities": [{
    "name": "Yamaha P-150",
    "width": [{
      "value": "1385",
      "unit": "mm",
      "evidence": "The Yamaha P-150 has a width of 1385 mm."
    }]
  }]
}
```

Decimal values stay typed in memory and serialize as strings only for JSON.
The handler does not call `to_claims()` or flatten records. The separate models
in `functions/resolved_models.py` describe the application-owned resolved result;
the LLM still receives only the extraction models.

Handler JSON now has this shape (empty properties and candidate metadata omitted
here for readability; the actual output preserves them):

```json
{
  "knowledge_base": "https://keyboards.wikibase.cloud",
  "entities": [{
    "name": "Yamaha P-150",
    "subject_id": "Q1",
    "warnings": [],
    "properties": {
      "width": {
        "property_id": "P2",
        "label": "width",
        "value_type": "Quantity",
        "claims": [{
          "value": "1385", "unit": "mm",
          "evidence": "The Yamaha P-150 has a width of 1385 mm.",
          "value_id": null, "value_candidates": [], "warnings": []
        }]
      }
    }
  }]
}
```

Property IDs and types come from the explicit field mapping validated against
`property_list.json`, not from the LLM or a repeated property-label search.
Catalog drift fails clearly. Keep the catalog synchronized with the RDF.
Subject and entity-value names use the existing exact, case-insensitive local
label/alias lookup. Candidate IDs are retained under `subject_candidates` and
`value_candidates`; multiple matches stay unresolved and produce warnings.
This preserves alias matching (e.g. P150), not fuzzy similarity or typo correction.
Names repeated within a run reuse lookup results; distinct extracted keyboard
records are never merged automatically. Repeated/conflicting claims remain intact.
Lookup failures preserve source content, mapped PIDs, and IDs already resolved.

`to_claims()` and `extract_ids()` remain legacy helpers for old flat exports;
neither is used by the main pipeline. The formatter can still read old flat JSON.

Existing consumers of the old flat handler output must now iterate
`entities`, then each entry in `properties`, then its `claims` list. Subject IDs
are stored once per entity and property IDs once per property group.

### Save and inspect your own results

`--json` prints to standard output; it does not automatically create a file.
Run these commands in Ubuntu/WSL from the project root:

```bash
mkdir -p outputs
# Put your own passage in sample_input.txt first.
# Grouped extraction only; requires CampusAI credentials.
python functions/extract_input.py "$(cat sample_input.txt)" > outputs/grouped.json
python -m json.tool outputs/grouped.json

# Full pipeline; requires CampusAI and running QLever.
python handler.py "$(cat sample_input.txt)" --json > outputs/claims.json
python functions/display_results.py outputs/claims.json
```

These are two independent LLM calls, so the results may differ. The handler does
not currently accept a saved grouped extraction as CLI input and does not save
its intermediate extraction automatically. `outputs/` is ignored by Git.

### Understanding Value and Value QID

`Value` is the content extracted from the input. `Value QID` identifies that
value only when the property expects another entity, such as a manufacturer.
The resolver uses the mapped property type from the local catalog (or QLever
for legacy facts without a PID) and looks up
the value name only for `wikibase:WikibaseItem` properties.

| Property | Extracted value | Unit | Value QID |
| --- | --- | --- | --- |
| manufacturer | Yamaha | none | Local `Q2`, if uniquely matched |
| width | 1385 | mm | Not applicable: a quantity |
| keys | 88 | none | Not applicable: a quantity |

For example, `Q1 --P6--> Q2` links Yamaha P-150 to its manufacturer Yamaha.
For width, `Q1 --P2--> 1385` has a numeric value rather than an entity QID;
the full quantity representation must also preserve the unit.

Grouped readable output shows Value QID only for entity-valued properties.
Quantities and text do not need QIDs. Unresolved entity values show warnings and,
when ambiguous, the candidate IDs. Grouped JSON retains nullable value_id fields.

## Run each module independently

### Progress while running

The handler prints short progress messages for QLever checks, CampusAI extraction,
and grouped keyboard/value ID lookups. Long steps print a waiting
message every ten seconds and report elapsed time when they finish or fail.
Waiting messages indicate that the call is still pending, not a completion estimate.
Source text and credentials are not included in these messages.

Progress goes to **stderr**; results go to **stdout**, so JSON redirects stay valid:

```bash
python handler.py "The Yamaha P-150 has a width of 1385 mm." --json > results.json
# Hide progress (errors are still reported):
python handler.py "The Yamaha P-150 has a width of 1385 mm." --json --quiet
```

Standalone extraction and resolution scripts also support `--quiet`.

### Standalone commands

Execute these from the project root; direct script paths and `python -m functions.NAME`
are both supported. Each module provides --help.

```bash
# Extraction only: needs CampusAI, not QLever.
python functions/extract_input.py "The Yamaha P-150 has a width of 1385 mm."

# Resolution only: needs QLever, not CampusAI. Uses a synthetic 999 cm sample.
python functions/resolve_local.py
# Resolve saved grouped output without another LLM call:
python functions/resolve_local.py --extraction-file outputs/grouped.json --source-file sample_input.txt > outputs/resolved.json
# Compatibility: resolve an older flat fact:
python functions/resolve_local.py --fact-json '{"subject":"Yamaha P-150","property":"width","value":"999","unit":"cm","evidence":"The Yamaha P-150 has a width of 999 cm."}'

# Two separate read-only checks; failures exit nonzero.
python functions/qlever_checks.py --check server
python functions/qlever_checks.py --check data
python functions/qlever_checks.py --check both

# Formatting only: no services. Accepts grouped JSON or legacy flat lists.
python functions/display_results.py
python functions/display_results.py results.json --json
```

The resolution sample should attach Q1/P2 while keeping 999 cm unchanged, even
though the current snapshot records a width of 1385 mm. This demonstrates source
preservation, not approval of the synthetic claim. The dataset check verifies
identity, not every triple or the correctness of every fact.

## Required concepts

- **RDF triples:** subject -> predicate -> object. Objects can be entities or
  literal values. A resource can be a subject in one fact and an object in another.
- **No fixed levels:** graph depth depends on the starting point and relationships
  followed. Use visited nodes and traversal limits if adding graph exploration.
- **Local IDs:** Keyboards Wikibase has its own QIDs/PIDs. They are not interchangeable
  with public Wikidata IDs. Local Q1 means Yamaha P-150; P2 means width; P4 means height.
- **Namespaces:** local entities use https://keyboards.wikibase.cloud/entity/;
  direct predicates use https://keyboards.wikibase.cloud/prop/direct/.
  These are identifiers, not websites fetched by the local query.
- **Schema:** properties describe value types and predicate mappings. The local
  P11 means instance of, but some items lack classification. Observed property
  usage is not a required-field validation schema.
- **Statements:** direct facts simplify queries; full statements can include ranks,
  qualifiers, references, and structured values. Quantity nodes carry units.
- **Pydantic:** validates extraction structure, not truth or correct entity matching.
  Use references for graph relationships instead of infinitely nested objects.

The supplied snapshot contains 6,888 triples and 30 property definitions. It is
not the whole Wikidata database and is not automatically synchronized online.

## Tests and current limitations

```bash
python -m unittest discover -s tests -v
# Requires Node.js; no npm dependencies or installation step.
node tests/test_comparison.cjs
```

Offline tests cover grouped resolution without legacy conversion, lookup caching,
preserved candidate IDs, source preservation, ambiguous/missing IDs, entity-valued
properties, supporting-context preservation, handler step order, preflight failures, failed
lookups, invalid server responses, and JSON formatting. They mock the LLM and
network; they do not establish live CampusAI availability or extraction accuracy.
The tests also check decimal precision, absent units, conflicting claims,
rejection of invalid quantities/extra fields, supported property mappings against
the catalog, and local generation of the structured-output schema. Schema
generation alone does not prove that the configured CampusAI model accepts it.
Use the standalone server checks for local service verification.

For a live smoke test, run both QLever checks above, then the extraction-only
command, then the handler on the same passage. Check the subject, property, value,
unit, and supporting context yourself. For the sample, expect width 1385 mm; local
Q1/P2 should attach if the current dataset is loaded. A passing offline suite
does not replace this live test. Provider availability and model behavior can change.

## Implementation status and continuation plan

| Stage | Status | Scope |
| --- | --- | --- |
| Local RDF and QLever | Implemented | Local index, startup helper, separate server/dataset checks |
| Property catalog | Implemented | 30 RDF definitions recorded in property_list.json |
| Typed extraction | Implemented | 23 supported properties, grouped entities, supporting sentences for review |
| Grouped resolution | Implemented | Separate typed output; subject per keyboard, mapped PIDs, per-claim value QIDs and candidates |
| Basic ID lookup | Existing behavior retained | Case-insensitive exact label/alias lookup; unique matches only |
| Improved entity resolution | Discussion/planning only | Candidate retrieval, alias normalization, ambiguity review |
| Existing-claim comparison | Implemented in website | Direct-value comparisons; matching, differing, missing and uncertain results; no unit conversion |
| Review and export | Implemented for drafts | Browser edits, manual match confirmation, JSON review export |
| Approved RDF updates | Planned | Keep/replace/add decisions with provenance and persistence; no graph writes today |

Further entity-resolution work can improve candidate retrieval. Retrieve
matching labels and aliases from the local RDF and group candidate names by
**QID**, not by shared spelling. Different QIDs must remain distinct candidates,
even when their aliases normalize to the same text. Lowercasing or stripping
punctuation may help retrieve candidates but cannot establish identity. No new
fuzzy matcher, alias-grouping system, or second LLM call has been implemented.
Whether an LLM helps with ambiguous candidates remains an open design choice.

After identities are resolved, the website compares each individual claim with
the graph. The CLI does not perform this comparison. Entity matching and
duplicate-statement detection are separate steps. Broader quantity comparison
will need explicit unit normalization while preserving the original
source value and evidence. Repeated/conflicting extractions currently stay intact;
they are not automatically merged, approved, or inserted.

The intended PoC will produce a reviewable report of existing, missing,
conflicting, and unresolved claims, then export approved additions. Evaluate it
on manually checked passages and a test copy with known facts removed. Do not
modify the original snapshot to manufacture a successful demo. The PoC will
remain limited by the local snapshot, selected properties, extraction accuracy,
entity ambiguity, and unverified supporting context.

## Troubleshooting and Git

CampusAI configuration: `CAMPUSAI_MODEL=chat` completed the current schema in
live testing. `LLM_TIMEOUT` defaults to 60 seconds (HTTP request timeout, not a
strict total runtime deadline); `LLM_MAX_TOKENS` defaults to 4096. Automatic SDK
retries are disabled. The client reports model, limits, and output token usage.

On 2026-11-20, the previous `google/gemma-4-26b-a4b` configuration answered plain
requests and a tiny schema, but generated incorrect, whitespace-repeating JSON
with the full keyboard schema and exhausted a 2048-token diagnostic limit.
This was not a QLever or connectivity failure. If it recurs, test another model
or a smaller schema; increasing timeouts alone does not resolve repetition.
Model availability and behavior may change. Evidence is displayed for review without source-text matching; schema acceptance
does not guarantee extraction accuracy.

- Docker unavailable: start Docker Desktop, enable Ubuntu integration, and retry
  once docker info succeeds.
- Index missing: run ../.venv/bin/qlever index from keyboards-index.
- Wrong container mount: inspect docker inspect qlever.server.anywikia; after
  confirming it is an obsolete project container, stop/remove it and run the helper.
- Query failures: inspect keyboards-index/keyboards.server-log.txt; port is 7071.
- CampusAI timeout: verify credentials, configured URL/model, and network access.
  Local checks can pass while the LLM service is unavailable.
- Supporting context: the LLM provides a short group of relevant sentences for each
  claim. No sentence IDs, exact-text checks, or whitespace repair are applied.
  The website shows this under a small expandable **Supporting context** label.
  These sentences are model-provided context, not automatically verified evidence.

.gitignore excludes credentials, virtual environments, caches, generated indexes,
vocabularies, logs, PIDs, and databases. Commit source RDF and credential-free
configuration. Never commit .env; .env.example is the public template.

## References

- [Wikibase RDF format](https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format)
- [SPARQL](https://www.w3.org/TR/sparql11-query/)
- [QLever](https://docs.qlever.dev/quickstart/)
- [Pydantic](https://docs.pydantic.dev/latest/concepts/models/)

### Comparing extracted values with RDF

The website automatically fetches direct properties for each uniquely matched
keyboard. It compares each claim by PID and shows stored values beneath it:

- Green: **Value exists** (one of the stored values matches).
- Muted red: **Conflicting value** (stored values differ).
- Blue: **New value for this property** (no direct value stored).
- Amber: **Needs review / verify units** (comparison cannot establish equality).

Comparison refreshes after value/unit edits or a manual candidate confirmation.
Changing the keyboard name suspends comparison until a match is confirmed. Failed
RDF requests show a retry action, never a new-value classification. Review exports
include comparison results; RDF remains unchanged.

Entity values compare QIDs; strings compare literally; quantities compare exact
numeric values with matching recognized units. Unit conversion is not implemented.
The snapshot uses Q199 (unitless) for some physical measurements, so these require
unit review. Missing units and unresolved value entities also require review.
A differing stored value is flagged for review, not proof that either claim is
wrong; qualifiers, ranks and multi-valued-property rules are not compared.
Run the frontend rules tests with `node tests/test_comparison.cjs`.
