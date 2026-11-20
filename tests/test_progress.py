"""Progress must remain separate from JSON and stop on success or failure."""
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from threading import Event
from unittest.mock import patch

import handler
from functions import progress
from functions.resolved_models import ResolvedExtraction


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.handlers = progress.logger.handlers[:]
        self.level = progress.logger.level

    def tearDown(self):
        progress.logger.handlers = self.handlers
        progress.logger.setLevel(self.level)

    def test_json_stdout_is_parseable_with_progress_enabled(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors), \
             patch('sys.argv', ['handler.py', 'source', '--json']), \
             patch.object(handler, 'run_pipeline', return_value=ResolvedExtraction()):
            handler.main()
        self.assertEqual(json.loads(output.getvalue())['entities'], [])
        self.assertIn('Printing JSON results', errors.getvalue())

    def test_quiet_suppresses_progress(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors), \
             patch('sys.argv', ['handler.py', 'source', '--json', '--quiet']), \
             patch.object(handler, 'run_pipeline', return_value=ResolvedExtraction()):
            handler.main()
        self.assertEqual(errors.getvalue(), '')
        self.assertEqual(json.loads(output.getvalue())['entities'], [])

    def test_waiting_report_and_thread_cleanup(self):
        messages = []
        waiting_seen = Event()

        def record(message):
            messages.append(message)
            if 'still waiting' in message:
                waiting_seen.set()

        progress.logger.setLevel(20)
        with patch.object(progress, 'report', side_effect=record):
            with progress.step('Example', interval=0.01):
                self.assertTrue(waiting_seen.wait(1))
            saved_count = len(messages)
            self.assertIn('done', messages[-1])
            # The worker was joined before step returned.
            self.assertEqual(len(messages), saved_count)

    def test_failure_is_reported_and_exception_preserved(self):
        with patch.object(progress, 'report') as report:
            with self.assertRaisesRegex(ValueError, 'invalid evidence'):
                with progress.step('Validation'):
                    raise ValueError('invalid evidence')
        self.assertIn('failed', report.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
