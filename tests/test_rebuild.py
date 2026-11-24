"""Exercise generation promotion and rollback without requiring Docker."""
import tempfile
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from rdflib import Graph, Literal, RDFS
from rdflib.compare import isomorphic

from functions.qlever_runtime import QLeverRuntime, atomic_json
from functions.rdf_models import KB
from tests.test_rdf_writes import fixture


def clone(graph):
    copied = Graph()
    for triple in graph: copied.add(triple)
    return copied


class LifecycleRuntime(QLeverRuntime):
    def __init__(self, root):
        root = Path(root)
        super().__init__(root / "runtime", root / "keyboards.nt")
        self.root.mkdir()
        self.old = self.root / "generations" / "old"
        self.old.mkdir(parents=True)
        initial = fixture()
        initial.serialize(self.rdf_path, format="nt")
        initial.serialize(self.old / "keyboards.nt", format="nt")
        self.graphs = {"old": clone(initial)}
        self.graphs["old"].add((KB.Q9, RDFS.label, Literal("Live addition")))
        self.running = {self.name: self.old}
        self.publish(self.old)
        atomic_json(self.root / "config.json", {"token": "test", "image": "pinned-test-image"})
        self.fail_build = self.fail_candidate = self.fail_switch = False
        self.stops = []

    def assert_ready(self):
        if self.name not in self.running: raise ValueError("not running")
    def snapshot(self, endpoint=None):
        directory = self.running[self.name + ".check" if endpoint == "candidate" else self.name]
        graph = clone(self.graphs[directory.name])
        if self.fail_candidate and endpoint == "candidate": graph.add((KB.Q999, RDFS.label, Literal("unexpected")))
        return graph
    def build(self, graph):
        if self.fail_build: raise RuntimeError("build failed")
        directory = self.root / "generations" / "fresh"; directory.mkdir()
        graph.serialize(directory / "keyboards.nt", format="nt")
        self.graphs["fresh"] = clone(graph)
        return directory
    def start(self, directory, name, port):
        if self.fail_switch and name == self.name and directory.name == "fresh":
            self.fail_switch = False
            raise RuntimeError("switch failed")
        self.running[name] = directory
        return "candidate" if port == 0 else self.endpoint
    def stop(self, name):
        self.stops.append(name); self.running.pop(name, None)
    def docker(self, *args, **kwargs): return "linux"
    def inspect(self, name):
        return {"State": {"Running": True}} if name in self.running else None


class RebuildTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.runtime = LifecycleRuntime(temp.name)

    def test_rebuild_exports_live_updates_and_keeps_old_generation(self):
        expected = self.runtime.snapshot()
        result = self.runtime.rebuild()
        self.assertEqual(result["generation"], "fresh")
        self.assertEqual(self.runtime.active().name, "fresh")
        self.assertTrue(isomorphic(expected, Graph().parse(self.runtime.rdf_path, format="nt")))
        self.assertTrue((self.runtime.old / "keyboards.nt").exists())
        self.assertTrue((self.runtime.root / "generations/fresh/previous-source.nt").exists())
        self.assertFalse((self.runtime.root / "recovery.json").exists())

    def test_build_failure_keeps_source_and_live_server(self):
        before = self.runtime.rdf_path.read_bytes(); self.runtime.fail_build = True
        with self.assertRaisesRegex(RuntimeError, "build failed"): self.runtime.rebuild()
        self.assertEqual(before, self.runtime.rdf_path.read_bytes())
        self.assertNotIn(self.runtime.name, self.runtime.stops)

    def test_candidate_mismatch_never_stops_old_server(self):
        self.runtime.fail_candidate = True
        with self.assertRaisesRegex(RuntimeError, "verification failed"): self.runtime.rebuild()
        self.assertNotIn(self.runtime.name, self.runtime.stops)
        self.assertEqual(self.runtime.active().name, "old")

    def test_switch_failure_rolls_back_source_and_index(self):
        before = self.runtime.rdf_path.read_bytes(); self.runtime.fail_switch = True
        with self.assertRaisesRegex(RuntimeError, "switch failed"): self.runtime.rebuild()
        self.assertEqual(self.runtime.active().name, "old")
        self.assertEqual(self.runtime.running[self.runtime.name], self.runtime.old)
        self.assertEqual(before, self.runtime.rdf_path.read_bytes())

    def test_crash_recovery_restores_previous_source(self):
        before = self.runtime.rdf_path.read_bytes()
        (self.runtime.root / "rebuild-source-backup.nt").write_bytes(before)
        atomic_json(self.runtime.root / "recovery.json", {"old":"generations/old"})
        self.runtime.rdf_path.write_text("incomplete file")
        self.runtime.initialize()
        self.assertEqual(before, self.runtime.rdf_path.read_bytes())
        self.assertFalse((self.runtime.root / "recovery.json").exists())

    def test_writes_cannot_enter_during_rebuild_lock(self):
        with self.runtime.exclusive():
            with self.assertRaisesRegex(ValueError, "running"):
                with self.runtime.exclusive(): pass

    def test_second_process_lock_is_exclusive(self):
        other = QLeverRuntime(self.runtime.root, self.runtime.rdf_path)
        with self.runtime.exclusive():
            with self.assertRaises((ValueError, OSError)):
                with other.exclusive(): pass

    def test_real_start_uses_argument_arrays_persistence_and_loopback(self):
        runtime = QLeverRuntime(self.runtime.root, self.runtime.rdf_path)
        info = {"NetworkSettings":{"Ports":{"7072/tcp":[{"HostPort":"7072"}]}}}
        with patch.object(runtime,"docker") as docker, patch.object(runtime,"inspect",return_value=info), patch.object(runtime,"query",return_value={"boolean":True}):
            runtime.start(self.runtime.old,runtime.name,7072)
            args = docker.call_args.args
            self.assertIn("--persist-updates",args)
            self.assertIn("127.0.0.1:7072:7072",args)
            self.assertIn("pinned-test-image",args)
            self.assertIn(f"type=bind,source={self.runtime.old.resolve()},target=/index",args)
            self.assertNotIn("bash",args)

    def test_missing_container_is_normal_without_parsing_error_text(self):
        runtime = QLeverRuntime(self.runtime.root, self.runtime.rdf_path)
        with patch.object(runtime, 'docker', return_value=runtime.name + '.check') as docker:
            self.assertIsNone(runtime.inspect(runtime.name))
            docker.assert_called_once_with('container', 'ls', '--all', '--format', '{{.Names}}')

    def test_existing_stopped_owned_container_is_inspected(self):
        runtime = QLeverRuntime(self.runtime.root, self.runtime.rdf_path)
        info = {'State': {'Running': False}, 'Config': {'Labels': {'anywikia.owner': runtime.owner}}}
        with patch.object(runtime, 'docker', side_effect=[runtime.name, json.dumps([info])]):
            self.assertEqual(runtime.inspect(runtime.name), info)

    def test_container_list_failure_is_not_mistaken_for_absence(self):
        runtime = QLeverRuntime(self.runtime.root, self.runtime.rdf_path)
        with patch.object(runtime, 'docker', side_effect=RuntimeError('Docker operation failed: permission denied')):
            with self.assertRaisesRegex(RuntimeError, 'permission denied'):
                runtime.inspect(runtime.name)

    def test_container_inspect_failure_keeps_diagnostic(self):
        runtime = QLeverRuntime(self.runtime.root, self.runtime.rdf_path)
        with patch.object(runtime, 'docker', side_effect=[runtime.name, RuntimeError('Docker operation failed: daemon unavailable')]):
            with self.assertRaisesRegex(RuntimeError, 'daemon unavailable'):
                runtime.inspect(runtime.name)

    def test_container_owner_mismatch_still_rejected(self):
        runtime = QLeverRuntime(self.runtime.root, self.runtime.rdf_path)
        info = {'Config': {'Labels': {'anywikia.owner': 'other'}}}
        with patch.object(runtime, 'docker', side_effect=[runtime.name, json.dumps([info])]):
            with self.assertRaisesRegex(ValueError, 'ownership mismatch'):
                runtime.inspect(runtime.name)


if __name__ == "__main__": unittest.main()
