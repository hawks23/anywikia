"""Supporting context is retained without exact-quote validation or repair."""
import unittest
from unittest.mock import patch
from functions.pydantic_models import Extraction, KeyboardExtraction, QuantityClaim, to_claims
from functions.extract_input import extract_entities

class SupportingContextTests(unittest.TestCase):
    def test_multiple_sentences_and_different_whitespace_survive(self):
        context = "The Yamaha DX7 is on the shelf. It weighs 14.2 kg."
        model = Extraction(entities=[KeyboardExtraction(name="Yamaha DX7", weight=[
            QuantityClaim(value="14.2", unit="kg", evidence=context)
        ])])
        source = "The Yamaha DX7 is on the shelf.\nIt weighs\n14.2 kg."
        with patch("functions.extract_input.structured_completion", return_value=model):
            result = extract_entities(source)
        self.assertEqual(result["entities"][0]["weight"][0]["evidence"], context)
        self.assertEqual(to_claims(model, source)["items"][0]["evidence"], context)

if __name__ == "__main__":
    unittest.main()
