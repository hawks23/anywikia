# Anywikia PoC limitations

Planned PoC: extract keyboard facts from pasted text, resolve them against the
local Keyboards Wikibase snapshot, compare existing statements, review proposed
additions, and export approved additions to a separate local RDF file.
This describes the intended scope, not completed functionality.

## Follow-up checklist

- [ ] **Limited properties:** initially support manufacturer, keys, width, height,
  and weight. Extend the local property catalog and validation rules later.
- [ ] **Existing entities only:** unknown keyboards or manufacturers remain
  unresolved. Add a reviewed entity-creation workflow later.
- [ ] **Text input only:** add website extraction, PDF tables, and OCR after the
  basic pipeline works.
- [ ] **Local snapshot only:** absence locally does not prove absence online.
  Add snapshot freshness tracking and recheck the destination before publishing.
- [ ] **Evidence is not truth:** preserve quotations and source locations, but
  separately assess source reliability and whether the quotation supports the claim.
- [ ] **Ambiguous names:** compare candidate entities and model variants instead
  of accepting the first search result; retain unresolved cases for review.
- [ ] **Complex statements:** extend quantity normalization and support date
  precision, qualifiers, uncertainty, and multiple or conflicting sources.
- [ ] **Local additions only:** live Wikibase/Wikidata publishing needs explicit
  destination mapping, statement/reference conversion, and duplicate checks.
- [ ] **Small evaluation:** use manually checked examples and a test copy with
  known facts removed; later evaluate varied, unseen sources and report errors.

## Implementation reminders

- The inspected Anywikia resolver still uses public Wikidata; `test.py` only
  demonstrates local QLever querying. Replace the resolver with local lookups.
- Local Keyboards IDs and public Wikidata IDs are different namespaces.
- Pydantic validates structure, not factual correctness. Keep extraction,
  resolution, evidence checks, comparison, and approval as separate stages.
- Represent graph links with entity references. If traversing the graph, track
  visited nodes and bound depth; cycles are possible even though none were found
  in the inspected snapshot.
- Verify that approved additions appear in the demo graph and are not proposed
  again when the same input is processed twice.
