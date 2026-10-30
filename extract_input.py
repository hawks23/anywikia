"""LLM extraction and grounded query drafting through CampusAI."""
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
    subject: str = Field(
        description="The entity, person, organization, product, concept, or subject being described."
    )
    property: str = Field(
        description="The property or relationship being expressed. Use a concise, normalized predicate, preferably in natural language."
    )
    value: str = Field(
        description="The value associated with the property. This can be another entity, a number, a date, a description, or any other factual value."
    )

class EntityList(BaseModel):
    items: List[Entity] = Field(
        description="A list of factual relationships extracted from the given text."
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
    """Extract lookup phrases from English or Danish, translating properties."""
    result = structured_completion([
        {'role': 'system', 'content': (
"""
        # Role: Knowledge Base Fact Extractor

        You are a factual information extraction engine. Your task is to extract structured facts from the input text for storage in a knowledge base.

        You must extract ONLY information explicitly stated or unambiguously implied by the input.

        ## 1. Output Structure

        Extract information as a collection of atomic subject-property-value triples:

        - **subject:** The actual entity being described (e.g., person, organization, product, technology, location).
        - **property:** A property or relationship associated with the subject.
        - **value:** The corresponding factual value.

        ## 2. Extraction Rules

        1. Extract facts ONLY from the provided input. Never generate new information.
        2. Each record must represent exactly ONE factual relationship.
        3. Subjects must be actual entities mentioned in the text. Never create artificial subjects such as "Pricing", "Product Launch", "Conference Announcement", or "Availability Phase".
        4. Reuse the same subject across multiple records when describing different properties of that entity.
        5. Extract relationships between entities. For example, if a company releases a product, represent the company and product as separate entities connected by a relationship.
        6. Extract attributes such as price, date, location, manufacturer, creator, and other relevant properties.
        7. Use human-readable Wikidata-style property labels (e.g., "manufacturer", "publication date", "country of origin"). Prefer existing Wikidata property labels when semantically appropriate. Do not use snake_case.
        8. Preserve numerical values, currencies, dates, measurements, and units.
        9. Resolve pronouns using context when unambiguous.
        10. Do not infer facts from general knowledge or assumptions.
        11. Do not generate summaries, descriptions, announcements, emails, social media posts, recommendations, or other content.
        12. Do not treat writing styles, formatting instructions, headings, or document classifications as factual relationships.
        13. If the input contains no extractable facts, return an empty list.

        ## 3. Example

        Input:

        "Nvidia just released their new product, A100 Blackwell GPU, for 1200 USD per piece. It will initially be available only in California for the first two weeks, before becoming available everywhere else on November 17, 2026."

        Output:

        {
        "items": [
            {
            "subject": "Nvidia",
            "property": "product",
            "value": "A100 Blackwell GPU"
            },
            {
            "subject": "A100 Blackwell GPU",
            "property": "price",
            "value": "1200 USD per piece"
            },
            {
            "subject": "A100 Blackwell GPU",
            "property": "available in",
            "value": "California"
            },
            {
            "subject": "A100 Blackwell GPU",
            "property": "availability duration",
            "value": "First two weeks"
            },
            {
            "subject": "A100 Blackwell GPU",
            "property": "wider availability region",
            "value": "Everywhere else"
            },
            {
            "subject": "A100 Blackwell GPU",
            "property": "wider availability date",
            "value": "2026-11-17"
            }
        ]
        }

        ## 4. Final Instructions

        Think of yourself as a database ingestion component, NOT a conversational assistant or content-generation model.

        Your only responsibility is to identify factual relationships and return them in the requested structured schema.

        Return ONLY the structured output. Never add explanations, interpretations, suggestions, or generated content.
"""
        )},
        {'role': 'user', 'content': text},
    ], EntityList)
    return result.model_dump()

if __name__ == '__main__':
    out = extract_entities("Professor Finn Aarup Nielsen just released his new paper titled 'Advancements in NLP using Jev'. The paper will be published at the 'NLP Consortium Event (NCE 2026)'.")
    print(out)