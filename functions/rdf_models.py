"""Trusted write schema and RDF value validation, independent of the LLM schema."""

import re
from decimal import Decimal, InvalidOperation
from typing import Literal as Choice
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field
from rdflib import Literal, Namespace, URIRef, XSD

from functions.pydantic_models import PROPERTY_FIELDS, validate_mapped_property
from functions.review_validation import COUNT_PROPERTIES

KB = Namespace("https://keyboards.wikibase.cloud/entity/")
BASE = "https://keyboards.wikibase.cloud/"
WB = Namespace("http://wikiba.se/ontology#")
APP = Namespace("urn:anywikia:")
PROV = Namespace("http://www.w3.org/ns/prov#")
UNIT_BASE = "http://www.wikidata.org/entity/"
UNITS = {
    "mm": "Q174789",
    "cm": "Q174728",
    "m": "Q11573",
    "g": "Q41803",
    "kg": "Q11570",
    "W": "Q25236",
    "DKK": "Q25417",
    "EUR": "Q4916",
    "USD": "Q4917",
    "GBP": "Q25224",
}
UNIT_CHOICES = {
    "P2": ["mm", "cm", "m"],
    "P3": ["mm", "cm", "m"],
    "P4": ["mm", "cm", "m"],
    "P7": ["g", "kg"],
    "P16": ["W"],
    "P25": ["DKK", "EUR", "USD", "GBP"],
}
COUNT_LABELS = {
    "P1": {"key", "keys"},
    "P8": {"voice", "voices", "note", "notes"},
    "P10": {"speaker", "speakers", "loudspeaker", "loudspeakers"},
    "P12": {"input", "inputs", "port", "ports", "connection", "connections"},
    "P13": {"output", "outputs", "port", "ports"},
    "P14": {"output", "outputs", "port", "ports", "connection", "connections"},
    "P15": {"port", "ports", "connection", "connections"},
    "P20": {"output", "outputs", "port", "ports"},
    "P21": {"input", "inputs", "port", "ports"},
    "P22": {"input", "inputs", "port", "ports"},
    "P29": {"port", "ports", "connector", "connectors", "connection", "connections"},
}


class ClaimEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    property_id: str
    value: str = Field(max_length=4000)
    unit: str | None = Field(default=None, max_length=80)
    value_id: str | None = None
    value_confirmed: bool = False
    create_value_entity: bool = False
    action: Choice["add", "replace"] = "add"
    statement: str | None = None
    evidence: str = Field(default="", max_length=20000)
    manual: bool = False


class WriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Choice["existing", "new"]
    confirmed: bool = False
    target_id: str | None = None
    name: str = Field(min_length=1, max_length=250)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    source: str = Field(default="", max_length=20000)
    claims: list[ClaimEdit] = Field(min_length=1, max_length=100)


def entity_uri(qid):
    if not isinstance(qid, str) or not re.fullmatch(r"Q[1-9][0-9]*", qid):
        raise ValueError("Choose a valid local entity ID.")
    return KB[qid]


def property_catalog():
    return [
        dict(
            field=field,
            property_id=pid,
            label=label,
            value_type=validate_mapped_property(pid, label)["wikibase_value_type"],
            units=UNIT_CHOICES.get(pid, []),
            count=pid in COUNT_PROPERTIES,
        )
        for field, (pid, label) in PROPERTY_FIELDS.items()
    ]


def value_terms(claim, graph):
    """Return a safe RDF value and optional quantity unit, or reject the edit."""
    spec = next(
        (p for p in property_catalog() if p["property_id"] == claim.property_id), None
    )
    if spec is None:
        raise ValueError("Unsupported property; choose one from the property dropdown.")
    if set(graph.objects(KB[claim.property_id], WB.propertyType)) != {
        WB[spec["value_type"]]
    } or set(graph.objects(KB[claim.property_id], WB.directClaim)) != {
        URIRef(BASE + "prop/direct/" + claim.property_id)
    }:
        raise ValueError(
            "The working graph property schema differs from the application catalog."
        )
    value = claim.value.strip()
    if not value:
        raise ValueError(f"{spec['label']}: enter a value or omit this claim.")
    if spec["value_type"] == "Quantity":
        if len(value) > 100 or not re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value
        ):
            raise ValueError(
                f"{spec['label']}: enter a finite number without a unit in the value field."
            )
        try:
            amount = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("Invalid numeric value.") from error
        if not amount.is_finite() or amount < 0 or abs(amount.adjusted()) > 100:
            raise ValueError(
                f"{spec['label']}: enter a finite nonnegative number of reasonable size."
            )
        unit = (claim.unit or "").strip()
        if spec["count"]:
            if amount != amount.to_integral_value():
                raise ValueError(f"{spec['label']}: counts must be whole numbers.")
            if unit and unit.lower() not in COUNT_LABELS[claim.property_id]:
                raise ValueError(
                    f"{spec['label']}: use a count label or leave the unit blank."
                )
            unit_uri = URIRef(UNIT_BASE + "Q199")
        else:
            if unit not in spec["units"]:
                raise ValueError(
                    f"{spec['label']}: choose a unit from {', '.join(spec['units'])}."
                )
            if claim.property_id in {"P2", "P3", "P4", "P7"} and amount == 0:
                raise ValueError(f"{spec['label']}: measurement must be positive.")
            unit_uri = URIRef(UNIT_BASE + UNITS[unit])
        return Literal(format(amount, "f"), datatype=XSD.decimal), unit_uri
    if spec["value_type"] == "WikibaseItem":
        if claim.unit and claim.unit.strip():
            raise ValueError(f"{spec['label']}: this property does not take a unit.")
        if not claim.value_confirmed or not claim.value_id:
            raise ValueError(
                f"{spec['label']}: '{value}' needs a confirmed value entity. Search for an existing entity or explicitly choose to create a new one. The keyboard ID is generated automatically."
            )
        target = entity_uri(claim.value_id)
        if not claim.value_confirmed or not any(graph.triples((target, None, None))):
            raise ValueError(
                f"{spec['label']}: search and confirm an existing local value entity."
            )
        return target, None
    if claim.unit and claim.unit.strip():
        raise ValueError(f"{spec['label']}: this property does not take a unit.")
    if spec["value_type"] == "Url":
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or any(c.isspace() for c in value)
            or any(c in value for c in '<>"{}|\\^`')
        ):
            raise ValueError("URL must be a valid http or https address.")
        return URIRef(value), None
    if spec["value_type"] == "ExternalId" and not re.fullmatch(r"Q[1-9][0-9]*", value):
        raise ValueError(
            "Wikidata item must have the form Q123; existence is not verified online."
        )
    if spec["value_type"] == "CommonsMedia" and (
        "/" in value
        or "\\" in value
        or ":" in value
        or not re.search(r"\.[A-Za-z0-9]{2,8}$", value)
    ):
        raise ValueError("Image must be a media filename, not a URL or file path.")
    return Literal(value), None
