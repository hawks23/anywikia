# Musical keyboard fact extraction

Run the following from this directory with the project virtual environment active.

```powershell
python -m pip install openai pydantic python-dotenv requests
python app.py
```

Put CAMPUSAI_API_KEY and CAMPUSAI_MODEL in the adjacent .env file. Optional settings are CAMPUSAI_API_URL and LLM_TIMEOUT (seconds, default 60). Edit the sample passage in app.py to try different input.

## How the files work

- **app.py** passes the passage to the extractor, prints its JSON and sends each triple to the resolver in order. The second JSON output contains successfully resolved records. Diagnostics go to standard error.
- **extract_input.py** defines the Entity and EntityList schemas. structured_completion sends messages and the schema to CampusAI and checks for refusals or missing output. extract_entities supplies the musical keyboard prompt and returns a dictionary containing an items list.
- **extract_id.py** searches English Wikidata labels using search_wikidata. extract_ids validates one triple and selects the first item match for its subject and the first property match for its predicate. The output includes subjectName, subject (QID), propertyName, property (PID) and the original value. A first-ranked match can be ambiguous.
- **try.py** contains separate experimental SPARQL helpers for executing queries, flattening bindings, matching labels or aliases, and parsing IDs from URIs. Running those queries requires supplying the logger, httpx2 client and SPARQL_ENDPOINT referenced in the module. The app uses the Wikidata search API directly.

## Timing and incomplete results

Each Wikidata request waits one second before sending and has a 15-second network timeout. On HTTP 429 the resolver honors Retry-After with a one-second minimum. When the header is absent, it waits two seconds and then four seconds. Each lookup gets at most three attempts. The resolver caches up to 512 distinct label/type lookups per process, including searches that returned no match.

A missing label such as an unmatched key-count property produces an unresolved-triple message and processing continues. An HTTP or API failure stops further lookups and the app prints the results collected so far. The timing settings affect request traffic. Missing or ambiguous properties require a separate mapping decision.

## Issues to resolve

### Where speed and accuracy break down

- **Repeated network calls.** Before caching, ten facts about the Yamaha DX7 could require twenty sequential searches. The resolver now caches each label by search type. With a cold cache, ten distinct properties for that keyboard still require eleven searches before any retries. A network failure can still interrupt the batch, and restarting the process starts with an empty cache.
- **The correct keyboard has to appear among the candidates.** The resolver requests only the first hit. If the extractor drops a model suffix such as `II`, the search may return the original instrument, and the resolver never sees an alternative. Lai et al. used the mention **and its sentence context** to retrieve Wikidata candidates by title and description before ranking them. [Improving Candidate Retrieval with Entity Profile Generation for Wikidata Entity Linking](https://arxiv.org/abs/2202.13404)
- **A plausible name match can still be the wrong QID.** The resolver accepts the first ID without comparing its description or type with the source. ReFinED uses both entity descriptions and fine-grained types for this decision. Checking the instrument type could rule out an unrelated product, but distinguishing two synthesizers in the same family also requires the exact model designation. [ReFinED](https://arxiv.org/pdf/2207.04108)
- **Property matching is a separate accuracy problem.** In the Yamaha DX7 run, the extractor captured “61 keys” and the subject resolved correctly, but the search for `number of keys` returned no PID. An empty search leaves open whether another label expresses the same fact. Even when both IDs resolve, the extractor may have assigned the value to the wrong instrument. The cited papers evaluate entity linking. This pipeline needs a separate check of subject, property and value together.
