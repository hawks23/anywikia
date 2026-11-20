"""Application-owned resolution results; these models are never sent to the LLM.

Keep keyboards, properties and source claims grouped. Decimal values remain
Decimal in memory and become strings only when serializing to JSON.
"""
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class Candidate(BaseModel):
    """One distinct local ID returned by exact label/alias matching."""
    model_config = ConfigDict(extra="forbid")
    id: str
    type: str | None = None


class ResolvedClaim(BaseModel):
    """Preserved source content, with optional entity-value matching metadata."""
    model_config = ConfigDict(extra="forbid")
    value: Decimal | str
    unit: str | None = None
    evidence: str
    value_id: str | None = None
    value_candidates: list[Candidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResolvedProperty(BaseModel):
    """Validated local property definition plus all of its extracted claims."""
    model_config = ConfigDict(extra="forbid")
    property_id: str
    label: str
    value_type: str
    claims: list[ResolvedClaim] = Field(default_factory=list)


class ResolvedKeyboard(BaseModel):
    """One source keyboard; aliases are resolved but records are not merged."""
    model_config = ConfigDict(extra="forbid")
    name: str
    subject_id: str | None = None
    subject_candidates: list[Candidate] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    properties: dict[str, ResolvedProperty] = Field(default_factory=dict)


class ResolvedExtraction(BaseModel):
    """Grouped output for display or JSON export; no database values are added."""
    model_config = ConfigDict(extra="forbid")
    knowledge_base: str = "https://keyboards.wikibase.cloud"
    entities: list[ResolvedKeyboard] = Field(default_factory=list)
