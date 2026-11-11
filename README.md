# Anywikia: musical keyboard fact extraction

Anywikia aims to extract evidence-backed facts from text, compare them with a
knowledge base, and prepare missing information for human review and addition.
The initial domain is musical keyboards and synthesizers.

**Current status:** CampusAI extracts subject, property, value, unit, and exact
source evidence. Local QLever resolution attaches Keyboards Wikibase IDs without
replacing source values. Automatic comparison, approval, and population are not implemented.

```bash
.venv/bin/python start_qlever.py
.venv/bin/python app.py "The Yamaha P-150 has a width of 1385 mm."
# Add --json for structured output. Offline regression checks:
.venv/bin/python -m unittest -v test_extraction_pipeline
```

The display separates Subject, Property, Value, Unit, Evidence, and local IDs.
Units remain as written (no conversion); absent units are null. Evidence must
occur verbatim in the input; this check does not prove the quote supports the claim.
Unknown or ambiguous names retain their extracted facts with unresolved IDs and
review warnings. Entity-valued properties also resolve the value name to a local QID.

## Prerequisites and fresh-clone setup

The local setup was verified in Ubuntu-22.04 under WSL2 with Python 3.13.
Install Git, Python with virtual-environment support (or uv), and Docker Desktop.
Enable Docker Desktop's WSL integration for Ubuntu and wait for its engine to
start before running QLever. CampusAI credentials are needed only for extraction.

Run in an Ubuntu/WSL terminal:

```bash
git clone https://github.com/hawks23/anywikia.git
cd anywikia
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
cd keyboards-index
../.venv/bin/qlever index
cd ..
python start_qlever.py
python test.py
```

Alternatively, create the environment using `uv venv --python 3.13 .venv`, then
install with `uv pip install --python .venv/bin/python -r requirements.lock.txt`.
The RDF snapshot is committed; generated indexes are excluded and must be built
on a fresh clone. Existing installations can reuse their index.

## Run extraction

Run the following from this directory with the project virtual environment active.

```bash
# First installation only; preserve an existing .env:
cp .env.example .env
# Edit .env and supply your CampusAI credentials before running:
python app.py
```

Put CAMPUSAI_API_KEY and CAMPUSAI_MODEL in the adjacent .env file. Optional settings are CAMPUSAI_API_URL and LLM_TIMEOUT (seconds, default 60). Edit the sample passage in app.py to try different input.

## How the files work

- **app.py** extracts from a passage argument (or the sample), attaches local IDs, and prints review fields. Use `--json` for structured records. Local service failures retain the extracted facts with warnings.
- **extract_input.py** defines the Entity and EntityList schemas. structured_completion sends messages and the schema to CampusAI and checks for refusals or missing output. extract_entities supplies the musical keyboard prompt and returns a dictionary containing an items list.
- **resolve_local.py** searches local English/Danish labels and aliases, case-insensitively. Only a unique exact match is assigned. Source values, units, and quotations remain unchanged.
- **extract_id.py** is the legacy public Wikidata resolver, no longer used by `app.py`.
- **try.py** contains separate experimental SPARQL helpers configured for local QLever, including label/alias lookup and ID parsing. The extraction app uses `resolve_local.py` instead.

## Legacy public resolver: timing and incomplete results

This section describes `extract_id.py`, which is retained for reference and is
not called by the current extraction pipeline.

Each Wikidata request waits one second before sending and has a 15-second network timeout. On HTTP 429 the resolver honors Retry-After with a one-second minimum. When the header is absent, it waits two seconds and then four seconds. Each lookup gets at most three attempts. The resolver caches up to 512 distinct label/type lookups per process, including searches that returned no match.

A missing label such as an unmatched key-count property produces an unresolved-triple message and processing continues. An HTTP or API failure stops further lookups and the app prints the results collected so far. The timing settings affect request traffic. Missing or ambiguous properties require a separate mapping decision.

## Issues to resolve

### Where speed and accuracy break down

- **Repeated network calls.** Before caching, ten facts about the Yamaha DX7 could require twenty sequential searches. The resolver now caches each label by search type. With a cold cache, ten distinct properties for that keyboard still require eleven searches before any retries. A network failure can still interrupt the batch, and restarting the process starts with an empty cache.
- **The correct keyboard has to appear among the candidates.** The resolver requests only the first hit. If the extractor drops a model suffix such as `II`, the search may return the original instrument, and the resolver never sees an alternative. Lai et al. used the mention **and its sentence context** to retrieve Wikidata candidates by title and description before ranking them. [Improving Candidate Retrieval with Entity Profile Generation for Wikidata Entity Linking](https://arxiv.org/abs/2202.13404)
- **A plausible name match can still be the wrong QID.** The resolver accepts the first ID without comparing its description or type with the source. ReFinED uses both entity descriptions and fine-grained types for this decision. Checking the instrument type could rule out an unrelated product, but distinguishing two synthesizers in the same family also requires the exact model designation. [ReFinED](https://arxiv.org/pdf/2207.04108)
- **Property matching is a separate accuracy problem.** In the Yamaha DX7 run, the extractor captured “61 keys” and the subject resolved correctly, but the search for `number of keys` returned no PID. An empty search leaves open whether another label expresses the same fact. Even when both IDs resolve, the extractor may have assigned the value to the wrong instrument. The cited papers evaluate entity linking. This pipeline needs a separate check of subject, property and value together.

## Local RDF setup in WSL

Project: `/home/sweet/anywikia`.
All RDF data, QLever configuration, generated indexes, and server logs live in
`keyboards-index/`. The source snapshot is `keyboards-index/keyboards.nt`.
`local_rdf.py` defines absolute data paths and the shared endpoint.

```bash
cd ~/anywikia
source .venv/bin/activate
python start_qlever.py
python test.py
```

Start Docker Desktop with Ubuntu WSL integration enabled first. The startup
helper works from any current directory and reuses the correctly mounted container.
The endpoint remains `http://127.0.0.1:7071`; the container is
`qlever.server.anywikia`, mounting `~/anywikia/keyboards-index` at `/index`.
Stop it with `docker stop qlever.server.anywikia`.

Manual commands (QLever must run from its configuration directory):

```bash
cd ~/anywikia/keyboards-index
../.venv/bin/qlever start
# Only if the index is missing or the snapshot has changed:
# ../.venv/bin/qlever index
```

For a fresh environment, run `python3 -m venv .venv` in the project root and
`.venv/bin/python -m pip install -r requirements.txt`.
`requirements.lock.txt` records the installed versions; install it instead of
`requirements.txt` to reproduce this environment. Generated QLever indexes are
excluded from Git. On a fresh clone, build them before starting:

```bash
cd keyboards-index
../.venv/bin/qlever index
cd ..
.venv/bin/python start_qlever.py
.venv/bin/python test.py
```

For LLM extraction, copy `.env.example` to `.env` and fill in the credentials.
The local RDF query test does not require credentials.

`test.py` and the experimental `try.py` helpers query local RDF. `app.py` uses
CampusAI for extraction and `resolve_local.py` for IDs from local QLever on port
7071. It does not fetch existing fact values to populate extracted claims.
`.env` remains private and excluded from Git.
See `limitations.md` for the PoC follow-up checklist.

## What the local test proves

`test.py` sends a read-only SPARQL query to QLever for Yamaha P-150 (`Q1`),
its English label, width (`P2`), and height (`P4`). Expected values are
**1385 mm wide and 159 mm high**. The snapshot contains **6,888 triples**.

The test does not call CampusAI or public Wikidata, extract new facts, or modify
data. It is a query demonstration, not a full application test suite.
Use `python test.py --endpoint http://127.0.0.1:7071` to specify an endpoint.

## Knowledge needed to continue development

### RDF and graph structure

RDF stores **subject -> predicate -> object** triples:

```text
Yamaha P-150 -> manufacturer -> Yamaha
Yamaha P-150 -> width        -> 1385
```

An object can be another resource or a literal such as text, a number, or a date.
Subject and object are roles: Yamaha can be an object in one fact and a subject
in another. `keyboards.nt` uses N-Triples syntax, with full resource identifiers
and literal language tags or datatypes where applicable.

A graph has no mandatory root or number of levels. Levels are traversal distances
from a chosen starting point. Cycles are possible, so traversal code should track
visited nodes and use depth limits where appropriate. No directed cycles were
found in the inspected snapshot; future data need not have that property.

### Keyboards Wikibase is separate from Wikidata

Local IDs and public Wikidata IDs are different namespaces. A local `Q1` or `P2`
must not be treated as the same ID on wikidata.org.

| Query prefix | Namespace | Meaning |
| --- | --- | --- |
| `kb:` | `https://keyboards.wikibase.cloud/entity/` | Local items and property definitions |
| `kbt:` | `https://keyboards.wikibase.cloud/prop/direct/` | Direct fact predicates |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` | Labels and schema vocabulary |
| `wikibase:` | `http://wikiba.se/ontology#` | Value types, predicate mappings, and metadata |

These URLs identify graph resources. Using them in a query sent to localhost
does not fetch those websites.

### Schema and types

The snapshot defines 30 properties. Each property has a label, value type, and
mappings to RDF predicates. For example:

```text
kb:P2 -> rdfs:label            -> "width"@en
kb:P2 -> wikibase:propertyType -> wikibase:Quantity
kb:P2 -> wikibase:directClaim  -> kbt:P2
```

Local `P11` means **instance of**: it can classify Yamaha as a manufacturer or
Japan as a country. Some items lack that classification, so type-based queries
can omit them. The inspected snapshot has no `rdfs:domain`, `rdfs:range`, or
`rdfs:subClassOf` triples. Observed property usage is not a required-field schema.

### Direct facts and full statements

Direct predicates are convenient for simple queries:

```sparql
PREFIX kb: <https://keyboards.wikibase.cloud/entity/>
PREFIX kbt: <https://keyboards.wikibase.cloud/prop/direct/>
SELECT ?width WHERE { kb:Q1 kbt:P2 ?width }
```

Full Wikibase statements also have statement nodes, ranks, and potentially
qualifiers and references. Quantity value nodes carry units and amounts. A direct
numeric value alone does not encode its unit. Comparison and export must preserve
this information rather than treating every fact as three strings.

### Pydantic and extraction

Pydantic validates the shape of extracted data. It does not prove a claim is true,
correctly linked, or absent from the knowledge base. Represent entity links using
references rather than recursively nesting the entire graph inside a model.
Keep extraction, resolution, evidence verification, comparison, and approval as
separate stages.

## Additional file guide

| File | Purpose |
| --- | --- |
| `local_rdf.py` | Shared endpoint and paths derived from the checkout location |
| `start_qlever.py` | Container mount validation, startup, and readiness check |
| `test.py` | Local SPARQL query example |
| `keyboards-index/keyboards.nt` | Versioned source RDF |
| `keyboards-index/Qleverfile` | Index and server configuration |
| `keyboards-index/Qleverfile-ui.yml` | Optional UI configuration; the startup helper does not launch the UI |
| `keyboards-index/keyboards.settings.json` | Supplied index settings |
| `requirements.lock.txt` | Recorded dependency versions |
| `.env.example` | Credential-free configuration template |
| `limitations.md` | PoC limitations and follow-up checklist |

## Planned PoC milestone

Support existing keyboard models and five properties: manufacturer, keys, width,
height, and weight.

1. Extract typed claims with exact quotations and source locations.
2. Resolve names and properties locally; preserve ambiguous or unknown matches.
3. Normalize quantities and units, then retrieve existing statements.
4. Classify claims as already present, candidate addition, conflict, or unresolved.
5. Review proposals and export approved additions to a separate RDF file.
6. Reload a demo graph and verify the facts exist and are not proposed twice.

Evaluate using manually checked examples and a test copy with selected known
facts removed. Preserve the original snapshot. Evidence supports an extraction
but does not establish source reliability, and absence locally does not establish
absence online. See [limitations.md](limitations.md) for further scope limits.

## Troubleshooting and maintenance

- **Docker unavailable or WSL Docker I/O error:** start Docker Desktop, confirm
  Ubuntu integration, and wait until `docker info` succeeds before retrying.
- **Index missing:** run `../.venv/bin/qlever index` from `keyboards-index/`.
- **Container points to an old directory:** inspect it with
  `docker inspect qlever.server.anywikia`. After confirming it is the old project
  container, stop and remove that container and rerun `python start_qlever.py`.
  Moving files does not update an existing Docker bind mount.
- **Connection refused:** run the startup helper and read
  `keyboards-index/keyboards.server-log.txt`. This setup uses port 7071, not 7070.
- **RDF changed:** stop the server, rebuild the index, and restart it. Editing
  `keyboards.nt` alone does not update the running index.
- **Unknown local entity:** inspect local labels and aliases; do not substitute
  a public Wikidata ID into the local namespace.

Only one checkout should use this container name and port at a time.

## Git hygiene

Commit code, source RDF, credential-free configuration, and documentation.
`.gitignore` excludes `.env`, virtual environments, Python caches, generated
indexes and vocabularies, logs, PIDs, and local databases. `.env.example` remains
versioned. Inspect staged changes before pushing: ignore rules do not untrack
files already committed.

## Background reading

- [Wikibase RDF format](https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format)
- [SPARQL query language](https://www.w3.org/TR/sparql11-query/)
- [QLever quickstart](https://docs.qlever.dev/quickstart/)
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
