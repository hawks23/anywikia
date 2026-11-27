"""HTTP request shapes. RDF rules remain in functions/rdf_models.py.

Strict booleans prevent strings such as "true" from acting as approval.
These models describe requests in /docs and reject malformed inputs early.
"""

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from functions.rdf_models import WriteRequest


class APIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    """Expected HTTP failures share the browser's readable error field."""

    error: str


class ExtractionRequest(APIRequest):
    text: str = Field(min_length=1, max_length=20000)

    @field_validator("text")
    @classmethod
    def require_source_text(cls, value):
        if not value.strip():
            raise ValueError("Enter some source text first.")
        return value


class EntityRequest(APIRequest):
    entity_id: str = Field(pattern=r"^Q[1-9][0-9]*$")


class SearchRequest(APIRequest):
    text: str = Field(min_length=1, max_length=250)


class PreviewRequest(WriteRequest):
    """Reuse the domain schema; identity approval must be a JSON boolean."""

    confirmed: StrictBool = False


class ConfirmRequest(APIRequest):
    preview_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    confirmed: StrictBool = False


class VerifyRequest(EntityRequest):
    # The existing browser sends an empty string for "all properties".
    property_id: str | None = Field(default=None, pattern=r"^(P[1-9][0-9]*)?$")


class RebuildRequest(APIRequest):
    confirmed: StrictBool = False
