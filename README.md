# Anywikia

Extract musical-keyboard facts from source text with CampusAI, attach matching
local Keyboards Wikibase IDs, and display the results with exact source evidence.
The local RDF informed the supported property catalog and supplies matching IDs
at runtime; it never replaces extracted values or units.
The current pipeline is read-only; comparison, approval, and population remain
future work. See [workflow.md](workflow.md) for the current flowchart and
[limitations.md](limitations.md) for follow-up work.

## Structure

```text
handler.py                      # Main entry point and step orchestration
functions/
  extract_input.py              # LLM extraction and exact-quote checks
  pydantic_models.py            # Typed grouped models and conversion to claims
  resolve_local.py              # Unique local QID/PID matching
  qlever_checks.py              # Server and dataset checks
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
3. extract_entities sends the passage and the typed model schema to CampusAI,
   returning claims grouped by keyboard and property with exact quotations.
4. to_claims creates individual claim records for downstream processing, while
   the grouped extraction remains a separate in-memory value in the handler.
5. extract_ids attaches unique local IDs using the existing resolver.
6. print_results prints individual records or machine-readable JSON.

Preflight failures stop before the LLM request. Extraction errors stop the run.
If a later lookup fails, the fact is retained with unresolved IDs and a warning.
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

Decimal values serialize as strings in JSON. The handler converts the grouped
claims to individual `subject`, `property`, `value`, `unit`, and `evidence`
records, then attaches IDs and warnings. Property names come from the explicit
field mapping, not arbitrary names invented by the LLM. The existing resolver
still looks up the property in QLever. `handler.py --json` prints a **list of
individual records**, not the grouped extraction or a combined envelope.

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
The 18 tests also check decimal precision, absent units, conflicting claims,
rejection of invalid quantities/extra fields, supported property mappings against
the catalog, and local generation of the structured-output schema. Schema
generation alone does not prove that the configured CampusAI model accepts it.
Use the standalone server checks for local service verification.

For a live smoke test, run both QLever checks above, then the extraction-only
command, then the handler on the same passage. Check the subject, property, value,
unit, and quoted evidence yourself. For the sample, expect width 1385 mm; local
Q1/P2 should attach if the current dataset is loaded. A passing offline suite
does not replace this live test. The new extraction schema has not yet been
verified end-to-end against the live CampusAI service in this update.

## Implementation status and continuation plan

| Stage | Status | Scope |
| --- | --- | --- |
| Local RDF and QLever | Implemented | Local index, startup helper, separate server/dataset checks |
| Property catalog | Implemented | 30 RDF definitions recorded in property_list.json |
| Typed extraction | Implemented | 23 supported properties, grouped entities, exact evidence checks |
| Claim preparation | Implemented | Separate individual records for downstream processing |
| Basic ID lookup | Existing behavior retained | Case-insensitive exact label/alias lookup; unique matches only |
| Improved entity resolution | Discussion/planning only | Candidate retrieval, alias normalization, ambiguity review |
| Existing-claim comparison | Planned | Duplicate, missing, conflicting, and uncertain classifications |
| Review and export | Planned | Human review and approved additions; no graph writes today |

The next step is to agree on entity resolution before implementing it. Retrieve
matching labels and aliases from the local RDF and group candidate names by
**QID**, not by shared spelling. Different QIDs must remain distinct candidates,
even when their aliases normalize to the same text. Lowercasing or stripping
punctuation may help retrieve candidates but cannot establish identity. No new
fuzzy matcher, alias-grouping system, or second LLM call has been implemented.
Whether an LLM helps with ambiguous candidates remains an open design choice.

After identities are resolved, compare each individual claim with the graph.
Entity matching and duplicate-statement detection are separate steps. Quantity
comparison will need explicit unit normalization while preserving the original
source value and evidence. Repeated/conflicting extractions currently stay intact;
they are not automatically merged, approved, or inserted.

The intended PoC will produce a reviewable report of existing, missing,
conflicting, and unresolved claims, then export approved additions. Evaluate it
on manually checked passages and a test copy with known facts removed. Do not
modify the original snapshot to manufacture a successful demo. The PoC will
remain limited by the local snapshot, selected properties, extraction accuracy,
entity ambiguity, and the fact that an exact quote is not proof of truth.

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
