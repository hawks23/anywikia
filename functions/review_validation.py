"""Write-boundary validation for reviewed claims; extraction may lack source units.

Future RDF create/update endpoints must call this before any mutation. Review
draft export remains allowed, including incomplete claims. This does not assert
that a supplied unit is compatible or that a claim is factually correct.
"""
from functions.pydantic_models import PROPERTY_FIELDS, validate_mapped_property

COUNT_PROPERTIES = {"P1", "P8", "P10", "P12", "P13", "P14", "P15", "P20", "P21", "P22", "P29"}
PRICE_CURRENCIES = ("DKK", "EUR", "USD", "GBP")


def validate_units_for_rdf(review: dict) -> None:
    """Reject populated measurement claims without units, using trusted catalog types."""
    for entity in review["entities"]:
        for field, prop in entity["properties"].items():
            if field not in PROPERTY_FIELDS:
                raise ValueError(f"Unsupported property: {field}")
            pid, label = PROPERTY_FIELDS[field]
            if prop.get("property_id") != pid:
                raise ValueError(f"Incorrect property ID for {field}")
            definition = validate_mapped_property(pid, label)
            if definition["wikibase_value_type"] != "Quantity" or pid in COUNT_PROPERTIES:
                continue
            for claim in prop["claims"]:
                value = claim.get("value")
                if value is None or not str(value).strip():
                    continue
                unit = claim.get("unit")
                if pid == "P25" and unit not in PRICE_CURRENCIES:
                    raise ValueError("Price requires a selected currency: DKK, EUR, USD or GBP before writing to RDF.")
                if not isinstance(unit, str) or not unit.strip():
                    raise ValueError(f"{entity.get('name', 'Keyboard')}: {label} requires a measurement unit before writing to RDF.")
