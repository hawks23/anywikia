"""Extract musical keyboard facts through the CampusAI structured completion API."""
import argparse
import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).with_name('.env'))

from pydantic import BaseModel, Field
from typing import List

class Entity(BaseModel):
    """One candidate fact with a keyboard subject and a source-grounded value."""

    subject: str = Field(
        description="Full name of the musical keyboard instrument or model described in the source, suitable for Wikidata item lookup."
    )
    property: str = Field(
        description="English Wikidata property label for the stated keyboard fact, such as manufacturer, instance of, or mass."
    )
    value: str = Field(
        description="Value stated for this instrument. Preserve entity names, model designations, date precision, and measurement units as text."
    )

class EntityList(BaseModel):
    """Structured completion schema allowing zero or more keyboard facts."""

    items: List[Entity] = Field(
        description="One triple per supported fact about a named musical keyboard. Return an empty list if there are none."
    )


def structured_completion(messages, schema=EntityList):
    """Extract structured information using Chat Completions."""
    key = os.getenv("CAMPUSAI_API_KEY")
    model = os.getenv("CAMPUSAI_MODEL")
    if not key or not model:
        raise ValueError(
            "Set CAMPUSAI_API_KEY and CAMPUSAI_MODEL in .env."
        )

    with OpenAI(
        api_key=key,
        base_url=os.getenv(
            "CAMPUSAI_API_URL",
            "https://api.campusai.compute.dtu.dk/v1"
        ),
        timeout=float(os.getenv("LLM_TIMEOUT", "60")),
        max_retries=1
    ) as client:

        response = client.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=schema
        )
    message = response.choices[0].message
    if message.refusal:
        raise ValueError(f"Model refused: {message.refusal}")
    if message.parsed is None:
        raise ValueError(
            "The model did not return valid structured output."
        )
    return message.parsed



def extract_entities(text: str) -> dict:
    """Extract Wikidata candidate statements about musical keyboard instruments."""
    result = structured_completion([
        {'role': 'system', 'content': """
Extract facts about named musical keyboard instruments or models from English or Danish text.
This includes digital pianos, organs and synthesizers with keyboards. Exclude computer keyboards,
accessories and synthesizer modules without keys. In mixed text, keep only keyboard instrument facts.

Return one subject-property-value triple per explicitly supported statement. Use the instrument's
full name consistently as the subject. A manufacturer or instrument class can be a value.
Keep model variants distinct and resolve pronouns only when their referent is clear.

Use human-readable English Wikidata property labels suitable for lookup, such as "instance of",
"manufacturer", "country of origin", "mass" or "width". Capture keyboard specifications such as
key count when a Wikidata property expresses that precise fact. Skip facts without a matching
property. Avoid guessing properties, QIDs, PIDs or facts from general knowledge.
Preserve values as stated, including names, units and the precision of dates and measurements.

Example input: "Yamaha manufactured the Yamaha DX7. The manual also lists a computer keyboard."
Example output: {"items": [{"subject": "Yamaha DX7", "property": "manufacturer", "value": "Yamaha"}]}

Return only the structured output. If there are no qualifying facts, return {"items": []}.
"""},
        {'role': 'user', 'content': text},
    ], EntityList)
    return result.model_dump()

if __name__ == '__main__':
    out = extract_entities("Yamaha manufactured the Yamaha DX7 synthesizer.")
    print(out)