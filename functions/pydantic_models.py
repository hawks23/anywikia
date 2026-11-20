"""Typed source-extraction models for keyboard properties in property_list.json.

Field descriptions are extraction instructions, not constraints asserted by RDF.
Each property holds a list so repeated or conflicting claims retain their own
evidence. Empty lists mean no claim was extracted, not that a value is zero.
Quantity values use Decimal, matching the snapshot's xsd:decimal representation
even for counts. Entity-valued properties contain source names, never guessed IDs.
Offer, seller and stored-query properties are intentionally outside this model.
"""
import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SourceClaim(BaseModel):
    """An exact supporting quotation; presence is checked against source later."""

    model_config = ConfigDict(extra="forbid")
    evidence: str = Field(min_length=1, description=(
        "Exact contiguous quotation from the input supporting this claim. Include "
        "enough context to identify the keyboard; never paraphrase the quotation."))


class QuantityClaim(SourceClaim):
    """Finite decimal amount and its source unit, without conversion or inference."""

    value: Decimal = Field(allow_inf_nan=False, description=(
        "Numeric amount explicitly stated in the input, without the unit. Preserve "
        "decimal precision; do not convert units, calculate, or copy database values."))
    unit: str | None = Field(description=(
        "Unit exactly as written in the input (for example mm, cm, kg or keys). "
        "Use null if no unit is stated. Never supply a unit from general knowledge."))


class EntityClaim(SourceClaim):
    """The source name of an entity; matching its QID is a separate operation."""

    value: str = Field(min_length=1, description=(
        "Entity name or class term supported by the source. Preserve the name; "
        "do not replace it with a QID or infer it from background knowledge."))


class TextClaim(SourceClaim):
    """A text value or identifier copied from the source, not constructed."""

    value: str = Field(min_length=1, description=(
        "Text, URL, or identifier explicitly supplied by the input. Preserve it "
        "as written; do not invent links, filenames, or identifiers."))


class KeyboardExtraction(BaseModel):
    """One named keyboard and its supported source claims, grouped by property."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, description=(
        "Full musical keyboard model name from the source. Keep model variants "
        "separate. Resolve pronouns only when the referent is clear."))
    keys: list[QuantityClaim] = Field(default_factory=list, description=(
        "P1 keys: number of physical keys on this instrument. Exclude computer "
        "keyboards, polyphony counts, and specifications of other variants."))
    width: list[QuantityClaim] = Field(default_factory=list, description=(
        "P2 physical width of the instrument itself. Exclude cases, stands, "
        "packaging and shipping dimensions. Preserve each source measurement."))
    depth: list[QuantityClaim] = Field(default_factory=list, description=(
        "P3 physical front-to-back depth of the instrument. Do not confuse with "
        "width or height; exclude packaging and accessories."))
    height: list[QuantityClaim] = Field(default_factory=list, description=(
        "P4 physical height of the instrument itself, not its stand, case or rack."))
    url: list[TextClaim] = Field(default_factory=list, description=(
        "P5 URL explicitly associated with this instrument in the source. "
        "Do not construct a product URL or assign unrelated links."))
    manufacturer: list[EntityClaim] = Field(default_factory=list, description=(
        "P6 maker of the instrument explicitly identified in the source. "
        "Do not substitute a seller, retailer, distributor or accessory maker."))
    weight: list[QuantityClaim] = Field(default_factory=list, description=(
        "P7 weight of the instrument alone. Exclude cases, shipping bundles and "
        "accessories. Keep conflicting weights as separate evidence-bearing claims."))
    polyphony: list[QuantityClaim] = Field(default_factory=list, description=(
        "P8 polyphony: simultaneous notes/voices explicitly stated for this "
        "instrument. Do not confuse with physical keys or preset counts."))
    color: list[EntityClaim] = Field(default_factory=list, description=(
        "P9 color explicitly stated for this keyboard. Do not infer from a model "
        "name or assign the color of its case or accessories."))
    loudspeakers: list[QuantityClaim] = Field(default_factory=list, description=(
        "P10 number of built-in loudspeakers. Exclude external speakers. "
        "Do not invent a count from a vague statement about sound output."))
    instance_of: list[EntityClaim] = Field(default_factory=list, description=(
        "P11 instrument class explicitly stated, such as digital piano or "
        "synthesizer. Do not classify from background knowledge alone."))
    midi_in: list[QuantityClaim] = Field(default_factory=list, description=(
        "P12 number of MIDI input connections explicitly stated. General MIDI "
        "support does not establish a count; distinguish input from output."))
    headphone_outputs: list[QuantityClaim] = Field(default_factory=list, description=(
        "P13 number of headphone outputs explicitly stated for this instrument."))
    midi_out: list[QuantityClaim] = Field(default_factory=list, description=(
        "P14 number of MIDI output connections explicitly stated; not MIDI inputs."))
    midi_through: list[QuantityClaim] = Field(default_factory=list, description=(
        "P15 number of MIDI through connections explicitly stated; do not infer "
        "from MIDI input/output support."))
    power_consumption: list[QuantityClaim] = Field(default_factory=list, description=(
        "P16 power consumption of the instrument. Do not substitute amplifier "
        "output power, supply voltage, or an accessory's rating."))
    wikidata_item: list[TextClaim] = Field(default_factory=list, description=(
        "P17 public Wikidata identifier explicitly supplied for this keyboard. "
        "This is an ExternalId string, not a guessed local QID."))
    image: list[TextClaim] = Field(default_factory=list, description=(
        "P18 CommonsMedia filename explicitly identifying an image of this "
        "keyboard. Do not invent a filename or turn a generic image URL into one."))
    country: list[EntityClaim] = Field(default_factory=list, description=(
        "P19 country explicitly related to this keyboard itself. A manufacturer's "
        "headquarters or a seller's location alone does not establish this claim. "
        "Skip ambiguous country relationships rather than guessing their meaning."))
    audio_outputs: list[QuantityClaim] = Field(default_factory=list, description=(
        "P20 number of audio outputs explicitly stated; distinguish outputs from "
        "inputs and do not calculate counts from vague connectivity descriptions."))
    microphone_inputs: list[QuantityClaim] = Field(default_factory=list, description=(
        "P21 number of microphone inputs explicitly stated for the instrument."))
    audio_inputs: list[QuantityClaim] = Field(default_factory=list, description=(
        "P22 number of audio inputs explicitly stated; distinguish from outputs."))
    usb_type_b: list[QuantityClaim] = Field(default_factory=list, description=(
        "P29 number of USB Type B connections explicitly stated. General USB "
        "support does not establish the connector type or number."))


# Explicit mapping keeps Python-safe field names aligned with local RDF labels.
# This identifies properties only; this module performs no entity resolution.
PROPERTY_FIELDS = {
    "keys": ("P1", "keys"), "width": ("P2", "width"),
    "depth": ("P3", "depth"), "height": ("P4", "height"),
    "url": ("P5", "URL"), "manufacturer": ("P6", "manufacturer"),
    "weight": ("P7", "weight"), "polyphony": ("P8", "polyphony"),
    "color": ("P9", "color"), "loudspeakers": ("P10", "loudspeakers"),
    "instance_of": ("P11", "instance of"), "midi_in": ("P12", "MIDI in"),
    "headphone_outputs": ("P13", "headphone outputs"), "midi_out": ("P14", "MIDI out"),
    "midi_through": ("P15", "MIDI through"), "power_consumption": ("P16", "power consumption"),
    "wikidata_item": ("P17", "Wikidata item"), "image": ("P18", "image"),
    "country": ("P19", "country"), "audio_outputs": ("P20", "audio outputs"),
    "microphone_inputs": ("P21", "microphone inputs"), "audio_inputs": ("P22", "audio inputs"),
    "usb_type_b": ("P29", "USB Type B"),
}


@lru_cache(maxsize=1)
def _property_catalog() -> dict:
    """Load the checked-in RDF catalog once per process; no endpoint request."""
    path = Path(__file__).resolve().parents[1] / "property_list.json"
    return {p["property_id"]: p for p in json.loads(path.read_text())["properties"]}


def validate_mapped_property(pid: str, label: str) -> dict:
    """Validate a supported PID, canonical label and model type against the catalog.

    A supplied PID is never silently replaced by a label search. Catalog drift
    requires updating the catalog/model together; this is not a live RDF check.
    """
    field = next((name for name, pair in PROPERTY_FIELDS.items()
                  if pair == (pid, label)), None)
    prop = _property_catalog().get(pid)
    if field is None or prop is None or prop["property_name"] != label:
        raise ValueError(f"Property mapping does not match local catalog: {label} ({pid})")
    claim_type = KeyboardExtraction.model_fields[field].annotation.__args__[0]
    expected = (QuantityClaim if prop["wikibase_value_type"] == "Quantity" else
                EntityClaim if prop["wikibase_value_type"] == "WikibaseItem" else TextClaim)
    if claim_type is not expected:
        raise ValueError(f"Property datatype does not match extraction model: {pid}")
    return prop


class Extraction(BaseModel):
    """One record per keyboard; unsupported or absent facts stay unfilled."""

    model_config = ConfigDict(extra="forbid")
    entities: list[KeyboardExtraction] = Field(description=(
        "Named musical keyboards described by the input. Return an empty list "
        "if none qualify. For unmentioned properties return empty lists. Preserve "
        "multiple or conflicting claims separately; never choose a winner."))


def validate_evidence(extraction: Extraction, source: str) -> None:
    """Check exact quotations while retaining the grouped extraction structure."""
    for entity in extraction.entities:
        for field in PROPERTY_FIELDS:
            for claim in getattr(entity, field):
                if not claim.evidence.strip() or claim.evidence not in source:
                    raise ValueError("Extraction rejected: evidence is not an exact quote from input.")


def to_claims(extraction: Extraction, source: str) -> dict:
    """Legacy flat export helper; not used by the grouped handler/resolver.

    Carry catalog-validated PIDs from PROPERTY_FIELDS, never from the LLM.
    Decimal values become strings only at this compatibility boundary so the
    current resolver and JSON output retain their expected types. Units are not
    converted. Evidence preserves original wording (Decimal normalizes spelling).
    This verifies quote presence, not semantic entailment or numeric agreement.
    """
    validate_evidence(extraction, source)
    claims = []
    for entity in extraction.entities:
        for field, (pid, label) in PROPERTY_FIELDS.items():
            for claim in getattr(entity, field):
                validate_mapped_property(pid, label)
                claims.append({"subject": entity.name, "property": label, "property_id": pid,
                               "value": str(claim.value),
                               "unit": claim.unit if isinstance(claim, QuantityClaim) else None,
                               "evidence": claim.evidence})
    return {"items": claims}

"""
EXAMPLE: filled LLM extraction model BEFORE to_claims()

Synthetic input (20 whitespace-separated words, two keyboard entities):
The Yamaha P-150 has 88 keys and measures 1385 mm wide. The Roland FP-10 has 88 keys and is black.

Illustrative valid output, not a recorded live LLM response. Shown as the JSON
representation of the parsed Extraction object: result.model_dump(mode="json").
Quantity values are Decimal inside the Pydantic object and serialize as strings.
All unmentioned properties remain empty lists. No QIDs or PIDs are present yet;
to_claims() has NOT flattened these grouped properties or attached mapped PIDs.
Here "keys" is preserved as the count unit explicitly present in the input.

{
  "entities": [
    {
      "name": "Yamaha P-150",
      "keys": [
        {
          "evidence": "The Yamaha P-150 has 88 keys and measures 1385 mm wide.",
          "value": "88",
          "unit": "keys"
        }
      ],
      "width": [
        {
          "evidence": "The Yamaha P-150 has 88 keys and measures 1385 mm wide.",
          "value": "1385",
          "unit": "mm"
        }
      ],
      "depth": [],
      "height": [],
      "url": [],
      "manufacturer": [],
      "weight": [],
      "polyphony": [],
      "color": [],
      "loudspeakers": [],
      "instance_of": [],
      "midi_in": [],
      "headphone_outputs": [],
      "midi_out": [],
      "midi_through": [],
      "power_consumption": [],
      "wikidata_item": [],
      "image": [],
      "country": [],
      "audio_outputs": [],
      "microphone_inputs": [],
      "audio_inputs": [],
      "usb_type_b": []
    },
    {
      "name": "Roland FP-10",
      "keys": [
        {
          "evidence": "The Roland FP-10 has 88 keys and is black.",
          "value": "88",
          "unit": "keys"
        }
      ],
      "width": [],
      "depth": [],
      "height": [],
      "url": [],
      "manufacturer": [],
      "weight": [],
      "polyphony": [],
      "color": [
        {
          "evidence": "The Roland FP-10 has 88 keys and is black.",
          "value": "black"
        }
      ],
      "loudspeakers": [],
      "instance_of": [],
      "midi_in": [],
      "headphone_outputs": [],
      "midi_out": [],
      "midi_through": [],
      "power_consumption": [],
      "wikidata_item": [],
      "image": [],
      "country": [],
      "audio_outputs": [],
      "microphone_inputs": [],
      "audio_inputs": [],
      "usb_type_b": []
    }
  ]
}
"""
