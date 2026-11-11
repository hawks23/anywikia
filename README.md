# Anywikia

Extract musical-keyboard facts from source text with CampusAI, attach matching
local Keyboards Wikibase IDs, and display the results with exact source evidence.
The local RDF supplies IDs only: it never replaces extracted values or units.
The current pipeline is read-only; comparison, approval, and population remain
future work. See [workflow.md](workflow.md) for the current flowchart and
[limitations.md](limitations.md) for follow-up work.

## Structure

```text
handler.py                      # Main entry point and step orchestration
functions/
  extract_input.py              # Pydantic models, LLM extraction, quote validation
  resolve_local.py              # Unique local QID/PID matching
  qlever_checks.py              # Server and dataset checks
  display_results.py            # Readable or JSON output
local_rdf.py                    # Shared endpoint and file paths
tests/start_qlever.py            # Docker startup and readiness
keyboards-index/                # RDF, QLever config, generated indexes and logs
workflow.md                     # Mermaid flowchart
tests/test_extraction_pipeline.py # Offline regression tests
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
are CAMPUSAI_API_URL and LLM_TIMEOUT. Local lookups and checks need no credentials.
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
3. extract_entities sends the passage to CampusAI and validates exact quotations.
4. extract_ids attaches unique local IDs to each fact, preserving all source fields.
5. print_results prints numbered records or machine-readable JSON.

Preflight failures stop before the LLM request. Extraction errors stop the run.
If a later lookup fails, the fact is retained with unresolved IDs and a warning.
Unknown or ambiguous names are not guessed. Source evidence being present does
not prove it supports the extracted claim. Units are preserved without conversion.
No source facts are retrieved from the RDF to complete the extraction.

### Understanding Value and Value QID

`Value` is the content extracted from the input. `Value QID` identifies that
value only when the property expects another entity, such as a manufacturer.
The resolver checks the local property's `wikibase:propertyType` and looks up
the value name only for `wikibase:WikibaseItem` properties.

| Property | Extracted value | Unit | Value QID |
| --- | --- | --- | --- |
| manufacturer | Yamaha | none | Local `Q2`, if uniquely matched |
| width | 1385 | mm | Not applicable: a quantity |
| keys | 88 | none | Not applicable: a quantity |

For example, `Q1 --P6--> Q2` links Yamaha P-150 to its manufacturer Yamaha.
For width, `Q1 --P2--> 1385` has a numeric value rather than an entity QID;
the full quantity representation must also preserve the unit.

The current formatter prints `Value QID: not linked` whenever `value_id` is null.
For literal values this is normal, not a failed lookup. For entity-valued
properties it can indicate an unresolved match; inspect the review warnings.
A missing property match also prevents determining whether value lookup is needed.
Distinguishing "not applicable" from "unresolved" in the display is future work.

## Run each module independently

Execute these from the project root; direct script paths and `python -m functions.NAME`
are both supported. Each module provides --help.

```bash
# Extraction only: needs CampusAI, not QLever.
python functions/extract_input.py "The Yamaha P-150 has a width of 1385 mm."

# Resolution only: needs QLever, not CampusAI. Uses a synthetic 999 cm sample.
python functions/resolve_local.py
# Supply your own extracted fact:
python functions/resolve_local.py --fact-json '{"subject":"Yamaha P-150","property":"width","value":"999","unit":"cm","evidence":"The Yamaha P-150 has a width of 999 cm."}'

# Two separate read-only checks; failures exit nonzero.
python functions/qlever_checks.py --check server
python functions/qlever_checks.py --check data
python functions/qlever_checks.py --check both

# Formatting only: no services. Optionally pass a JSON file containing a list.
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
```

Offline tests cover source preservation, ambiguous/missing IDs, entity-valued
properties, quotation validation, handler step order, preflight failures, failed
lookups, invalid server responses, and JSON formatting. They mock the LLM and
network; they do not establish live CampusAI availability or extraction accuracy.
Use the standalone server checks for local service verification.

Next: compare existing statements, normalize units for comparison, classify
missing/duplicate/conflicting claims, and export human-approved additions.
Evaluate on manually checked inputs and a test copy with known facts removed.
Do not modify the original snapshot to manufacture a successful demo.

## Troubleshooting and Git

- Docker unavailable: start Docker Desktop, enable Ubuntu integration, and retry
  once docker info succeeds.
- Index missing: run ../.venv/bin/qlever index from keyboards-index.
- Wrong container mount: inspect docker inspect qlever.server.anywikia; after
  confirming it is an obsolete project container, stop/remove it and run the helper.
- Query failures: inspect keyboards-index/keyboards.server-log.txt; port is 7071.
- CampusAI timeout: verify credentials, configured URL/model, and network access.
  Local checks can pass while the LLM service is unavailable.
- Exact quotation failure: the extraction is rejected; this is not silently repaired.

.gitignore excludes credentials, virtual environments, caches, generated indexes,
vocabularies, logs, PIDs, and databases. Commit source RDF and credential-free
configuration. Never commit .env; .env.example is the public template.

## References

- [Wikibase RDF format](https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format)
- [SPARQL](https://www.w3.org/TR/sparql11-query/)
- [QLever](https://docs.qlever.dev/quickstart/)
- [Pydantic](https://docs.pydantic.dev/latest/concepts/models/)
