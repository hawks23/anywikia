"""Bound failed requests and explain truncated structured output clearly."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import APITimeoutError, LengthFinishReasonError
from openai.types.chat import ChatCompletion

from functions import extract_input


class CampusAILimitTests(unittest.TestCase):
    def test_request_has_output_limit_and_no_retry(self):
        result = SimpleNamespace(usage=None, choices=[SimpleNamespace(
            message=SimpleNamespace(refusal=None, parsed='parsed'))])
        with patch.dict('os.environ', {'CAMPUSAI_API_KEY': 'test', 'CAMPUSAI_MODEL': 'chat',
                                      'LLM_TIMEOUT': '12', 'LLM_MAX_TOKENS': '256'}), \
             patch.object(extract_input, 'OpenAI') as factory:
            client = factory.return_value.__enter__.return_value
            client.chat.completions.parse.return_value = result
            self.assertEqual(extract_input.structured_completion([]), 'parsed')
            self.assertEqual(factory.call_args.kwargs['max_retries'], 0)
            self.assertEqual(factory.call_args.kwargs['timeout'].connect, 5)
            self.assertEqual(client.chat.completions.parse.call_args.kwargs['max_tokens'], 256)

    def test_timeout_is_actionable(self):
        with patch.dict('os.environ', {'CAMPUSAI_API_KEY': 'test', 'CAMPUSAI_MODEL': 'chat'}), \
             patch.object(extract_input, 'OpenAI') as factory:
            client = factory.return_value.__enter__.return_value
            client.chat.completions.parse.side_effect = APITimeoutError(
                request=httpx.Request('POST', 'http://localhost'))
            with self.assertRaisesRegex(ValueError, 'No retry was made'):
                extract_input.structured_completion([])

    def test_length_failure_explains_incomplete_json(self):
        completion = ChatCompletion(id='test', created=0, model='chat', object='chat.completion',
                                    choices=[])
        with patch.dict('os.environ', {'CAMPUSAI_API_KEY': 'test', 'CAMPUSAI_MODEL': 'chat'}), \
             patch.object(extract_input, 'OpenAI') as factory:
            client = factory.return_value.__enter__.return_value
            client.chat.completions.parse.side_effect = LengthFinishReasonError(completion=completion)
            with self.assertRaisesRegex(ValueError, 'before completing JSON'):
                extract_input.structured_completion([])


if __name__ == '__main__':
    unittest.main()
