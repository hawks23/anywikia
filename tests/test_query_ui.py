import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from functions.qlever_ui import start_query_ui


class QueryUITests(unittest.TestCase):
    def runtime(self, root):
        runtime = Mock()
        runtime.root = Path(root) / 'folder with spaces'
        runtime.name = 'anywikia.working.test'
        runtime.owner = 'test'
        runtime.endpoint = 'http://127.0.0.1:7072'
        runtime.inspect.return_value = None
        def docker(*args, **kwargs):
            if args[0] == 'cp':
                Path(args[2]).write_bytes(b'test fixture database')
            if args[:5] == ('exec', runtime.name + '.ui', 'python', 'manage.py', 'config') and len(args) == 6:
                return 'config:\n  backend:\n    baseUrl: http://127.0.0.1:7071\n'
            return ''
        runtime.docker.side_effect = docker
        return runtime

    @patch('functions.qlever_ui.httpx.get')
    def test_initial_setup_handles_spaces_and_repoints_ui(self, get):
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root)
            result = start_query_ui(runtime)
            self.assertEqual(result['url'], 'http://127.0.0.1:8178/default')
            config = json.loads((runtime.root / 'query-ui/working-ui.yml').read_text())
            self.assertEqual(config['config']['backend']['baseUrl'], runtime.endpoint)
            run = next(c.args for c in runtime.docker.call_args_list if c.args[0] == 'run')
            self.assertIn(f'type=bind,source={(runtime.root / "query-ui").resolve()},target=/app/db', run)
            self.assertIn('127.0.0.1:8178:7000', run)
            self.assertNotIn('bash', run)
            runtime.initialize.assert_called_once()

    @patch('functions.qlever_ui.httpx.get')
    def test_existing_services_are_reused(self, get):
        with tempfile.TemporaryDirectory() as root:
            runtime = self.runtime(root)
            directory = runtime.root / 'query-ui'; directory.mkdir(parents=True)
            (directory / 'keyboards.ui-db.sqlite3').write_bytes(b'existing data')
            runtime.inspect.return_value = {'State':{'Running':True}, 'Mounts':[{'Destination':'/app/db'}],
                'HostConfig':{'PortBindings':{'7000/tcp':[{'HostPort':'8178','HostIp':'127.0.0.1'}]}}}
            start_query_ui(runtime)
            commands = [c.args[0] for c in runtime.docker.call_args_list]
            self.assertNotIn('run',commands); self.assertNotIn('create',commands)
            self.assertEqual((directory / 'keyboards.ui-db.sqlite3').read_bytes(),b'existing data')

    def test_invalid_port_does_not_start_services(self):
        runtime = Mock()
        for port in (7072, 0, 99999, '8178'):
            with self.assertRaises(ValueError): start_query_ui(runtime,port)
        runtime.initialize.assert_not_called()
