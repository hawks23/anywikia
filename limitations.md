# Anywikia PoC limitations

Implemented: grouped keyboard extraction, local ID resolution, website fuzzy-name
suggestions, editable review drafts, direct RDF value comparisons and JSON export.
The CLI extracts/resolves; the website adds suggestions and comparison. Neither
writes RDF. Approved RDF export and actual entity creation remain future work.

## Follow-up checklist

- [ ] **Scope:** 24 curated keyboard properties from a 30-property catalog, including price.
  Manufacturers are linked values, not independently extracted top-level records.
- [ ] **Price:** DKK/EUR/USD/GBP are application-defined currency choices, not
  RDF-declared constraints. Source prices retain seller/date context in evidence;
  separate offer records are not extracted. Existing-price comparison remains
  uncertain pending currency and offer handling. No currency conversion or guessing.
- [ ] **Units:** count units are optional; populated measurements require units,
  and prices require a listed currency. Inline errors block the new-entity demo,
  not draft export. Future write endpoints must invoke `validate_units_for_rdf`;
  this checks presence/currency membership, not full unit compatibility or truth.
- [ ] **Polyphony parsing:** explicit English numeric/count compounds are normalized
  without changing evidence. Ambiguous expressions and conflicting units remain
  invalid; this is not a general natural-language number parser.
- [ ] **Entity identity:** exact names/aliases and manual fuzzy suggestions do not
  prove identity. Add contextual/type checks; do not merge variants automatically.
- [ ] **Fuzzy candidate coverage:** only items with P1 (number of keys) are included.
  Missing P1 excludes a keyboard. Only distance < 3 and the best three distinct
  QIDs are returned; short aliases and near-identical model names need review.
- [ ] **Cache lifecycle:** five-minute lazy server-memory cache, one per process.
  Large datasets need indexed candidate retrieval. Future real creation must
  update/invalidate a loaded cache after RDF changes become queryable in QLever.
- [ ] **Unverified supporting context:** model-provided sentences are not checked
  for exact wording or semantic support. Pydantic validates structure, not truth.
- [ ] **Comparison:** direct values only; no unit conversion, qualifiers, ranks,
  cardinality reasoning or reference comparison. Unitless quantity metadata can
  make comparisons uncertain. A differing value is a review flag, not proof of error.
- [ ] **Editing:** changed entity values are not re-resolved automatically. Edits
  remain drafts; no persistent approval, replacement, conflict resolution or writes.
- [ ] **Creation:** ENTITY ADDED ! is a demo only. No new QID or RDF statement is
  generated. Preserve proposals and the original snapshot when implementing writes.
- [ ] **Persistence:** browser refresh loses drafts; export saves original output
  plus review JSON, not approved RDF. Importing review exports is not implemented.
- [ ] **Input/service limits:** pasted text only; website input limit is 20,000
  characters. CampusAI output limit defaults to 8192 tokens, HTTP timeout to 180
  seconds, and web subprocess limit to 300 seconds. No automatic provider retries.
- [ ] **Deployment:** local loopback development server, not a public multiuser app.
- [ ] **Snapshot:** absence locally does not establish absence online. Index rebuilds
  are required after editing RDF files; local and public Wikidata IDs differ.
- [ ] **Evaluation:** tests and smoke checks do not measure extraction accuracy.
  Evaluate unseen passages, wrong candidates and repeated/conflicting statements.

Future graph traversal must track visited IDs and impose depth limits. RDF can
contain cycles; it has no fixed hierarchy. Real population should be tested on a
copy, including repeat processing to ensure duplicate statements are not added.
