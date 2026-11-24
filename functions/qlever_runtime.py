"""Managed, persistent QLever runtime and recoverable RDF export/rebuild.

All Docker commands use argument arrays. Index generations and original RDF
backups are retained; the old 7071 container is never touched. Run setup through
handler.py or tests/start_qlever.py, not by importing this module.
"""

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

import httpx
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.compare import isomorphic

from local_rdf import PROJECT_DIR, RDF_PATH, RUNTIME_DIR, SPARQL_ENDPOINT


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def decode_term(term):
    if term["type"] == "uri":
        return URIRef(term["value"])
    if term["type"] == "bnode":
        return BNode(term["value"])
    return Literal(
        term["value"], lang=term.get("xml:lang"), datatype=term.get("datatype")
    )


class QLeverRuntime:
    """Own this checkout's Docker server, persistent index generations and backups."""

    def __init__(self, root=RUNTIME_DIR, rdf_path=RDF_PATH, endpoint=SPARQL_ENDPOINT):
        self.root, self.rdf_path, self.endpoint = Path(root), Path(rdf_path), endpoint
        self.owner = hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()[:12]
        self.name = "anywikia.working." + self.owner
        self._lock = Lock()

    @contextmanager
    def exclusive(self):
        """Single writer across threads and web/setup processes; fail rather than queue."""
        if not self._lock.acquire(blocking=False):
            raise ValueError(
                "Another save or rebuild is running. Wait for it to finish."
            )
        handle = None
        locked = False
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            handle = (self.root / "writer.lock").open("a+b")
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                if handle.read(1) == b"":
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            yield
        except (BlockingIOError, PermissionError) as error:
            if not locked:
                raise ValueError(
                    "Another process is writing or rebuilding the graph."
                ) from error
            raise
        finally:
            if handle:
                handle.close()
            self._lock.release()

    def config(self):
        """Load private access credentials and the pinned server image ID."""
        path = self.root / "config.json"
        if not path.exists():
            raise ValueError(
                "Working graph is not initialized. Run python tests/start_qlever.py first."
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def active(self):
        """Resolve the published index generation and reject paths outside its root."""
        path = self.root / "active.json"
        if not path.exists():
            raise ValueError(
                "Working index is not initialized. Run python tests/start_qlever.py."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        directory = (self.root / data["generation"]).resolve()
        if directory.parent != (self.root / "generations").resolve():
            raise ValueError("Invalid working index path.")
        return directory

    def docker(self, *args, timeout=60):
        """Execute Docker arguments without a shell and redact access tokens in errors."""
        try:
            result = subprocess.run(
                ["docker", *map(str, args)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(
                "Docker is unavailable or timed out. Check Docker Desktop and the working graph."
            ) from error
        if result.returncode:
            # Never include command arguments (the server launch contains its token).
            detail = result.stderr[-1000:]
            if (self.root / "config.json").exists():
                detail = detail.replace(self.config()["token"], "[redacted]")
            raise RuntimeError("Docker operation failed: " + detail)
        return result.stdout.strip()

    def inspect(self, name):
        # Check structured successful output, not version-dependent stderr wording.
        # Include stopped containers and compare exact names, not substring filters.
        """Return metadata for an owned container, or None if it does not exist."""
        names = self.docker("container", "ls", "--all", "--format", "{{.Names}}")
        if name not in names.splitlines():
            return None
        info = json.loads(self.docker("container", "inspect", name, timeout=20))[0]
        if info.get("Config", {}).get("Labels", {}).get("anywikia.owner") != self.owner:
            raise ValueError(
                "Container ownership mismatch; no existing container was changed."
            )
        return info

    def assert_ready(self):
        """Reject writes when recovery, ownership or persistent-runtime checks fail."""
        if (self.root / "recovery.json").exists():
            raise ValueError(
                "An interrupted rebuild needs recovery. Run python tests/start_qlever.py."
            )
        directory = self.active()
        info = self.inspect(self.name)
        if not info or not info["State"]["Running"]:
            raise ValueError(
                "Working QLever is stopped. Run python tests/start_qlever.py."
            )
        mount = next(
            (m["Source"] for m in info["Mounts"] if m["Destination"] == "/index"), ""
        )
        # Docker Desktop normalizes Windows paths internally. A generation label
        # plus owner and persistent command verifies identity across both hosts.
        labels = info["Config"]["Labels"]
        if (
            not mount
            or labels.get("anywikia.generation") != directory.name
            or "--persist-updates" not in info["Config"]["Cmd"]
        ):
            raise ValueError(
                "Working graph mount/generation or persistence does not match this checkout."
            )
        if os.name != "nt" and Path(mount).resolve() != directory:
            raise ValueError(
                "The working graph mounts another directory; refusing to write."
            )

    def query(self, query, endpoint=None):
        """Execute read-only SPARQL and return its JSON result."""
        response = httpx.post(
            endpoint or self.endpoint,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def snapshot(self, endpoint=None):
        """Read a bounded default-graph snapshot for planning or verification."""
        rows = self.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 100001", endpoint)[
            "results"
        ]["bindings"]
        if len(rows) > 100000:
            raise ValueError(
                "This local review workflow supports snapshots up to 100,000 triples."
            )
        graph = Graph()
        for row in rows:
            graph.add(tuple(decode_term(row[key]) for key in ("s", "p", "o")))
        return graph

    def update(self, sparql):
        """Submit SPARQL Update using the private server-side access token."""
        response = httpx.post(
            self.endpoint,
            content=sparql.encode("utf-8"),
            headers={
                "Content-Type": "application/sparql-update",
                "Authorization": "Bearer " + self.config()["token"],
            },
            timeout=30,
        )
        response.raise_for_status()

    def stop(self, name):
        """Stop and remove only a container owned by this checkout."""
        if self.inspect(name):
            self.docker("stop", name)
            self.docker("rm", name)

    def start(self, directory, name, port):
        """Launch a persistent server for one generation and wait for query readiness."""
        config = self.config()
        args = [
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "anywikia.owner=" + self.owner,
            "--label",
            "anywikia.generation=" + directory.name,
            "--mount",
            f"type=bind,source={directory.resolve()},target=/index",
            "-w",
            "/index",
            "-p",
            f"127.0.0.1:{port}:7072",
            "--entrypoint",
            "qlever-server",
            config["image"],
            "-i",
            "keyboards",
            "-p",
            "7072",
            "-m",
            "1G",
            "-c",
            "256M",
            "-a",
            config["token"],
            "--persist-updates",
        ]
        if os.name != "nt":
            args[2:2] = ["--user", f"{os.getuid()}:{os.getgid()}"]
        self.docker(*args)
        info = self.inspect(name)
        actual_port = info["NetworkSettings"]["Ports"]["7072/tcp"][0]["HostPort"]
        endpoint = "http://127.0.0.1:" + actual_port
        for _ in range(40):
            try:
                if self.query("ASK { ?s ?p ?o }", endpoint).get("boolean"):
                    return endpoint
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(0.5)
        raise RuntimeError(
            "New QLever instance did not become ready; old data has been retained."
        )

    def build(self, graph):
        """Serialize a graph and build a separate index generation without switching."""
        directory = self.root / "generations" / ("g-" + uuid.uuid4().hex)
        directory.mkdir(parents=True)
        graph.serialize(
            destination=directory / "keyboards.nt", format="nt", encoding="utf-8"
        )
        (directory / "keyboards.settings.json").write_text("{}", encoding="utf-8")
        args = [
            "run",
            "--rm",
            "--mount",
            f"type=bind,source={directory.resolve()},target=/index",
            "-w",
            "/index",
            "--entrypoint",
            "qlever-index",
            self.config()["image"],
            "-i",
            "keyboards",
            "-s",
            "keyboards.settings.json",
            "-F",
            "nt",
            "-f",
            "keyboards.nt",
            "--stxxl-memory",
            "1G",
        ]
        if os.name != "nt":
            args[2:2] = ["--user", f"{os.getuid()}:{os.getgid()}"]
        output = self.docker(*args, timeout=600)
        (directory / "build.log").write_text(output, encoding="utf-8")
        return directory

    def publish(self, directory):
        """Atomically record which index generation should be served."""
        atomic_json(
            self.root / "active.json",
            {"generation": str(directory.relative_to(self.root))},
        )

    def initialize(self):
        """Create or resume the graph, recovering an interrupted switch if necessary."""
        with self.exclusive():
            self.docker("info")
            if not (self.root / "config.json").exists():
                image = os.getenv(
                    "ANYWIKIA_QLEVER_IMAGE", "docker.io/adfreiburg/qlever:latest"
                )
                self.docker("pull", image, timeout=600)
                image_id = self.docker("image", "inspect", image, "--format", "{{.Id}}")
                atomic_json(
                    self.root / "config.json",
                    {"token": secrets.token_urlsafe(32), "image": image_id},
                )
                os.chmod(self.root / "config.json", 0o600)
            recovery = self.root / "recovery.json"
            if recovery.exists():
                state = json.loads(recovery.read_text(encoding="utf-8"))
                old = self.root / state["old"]
                if old.resolve().parent != (self.root / "generations").resolve():
                    raise ValueError("Invalid recovery path.")
                self.stop(self.name)
                self.start(old, self.name, 7072)
                self.publish(old)
                shutil.copyfile(self.root / "rebuild-source-backup.nt", self.rdf_path)
                recovery.unlink()
            if not (self.root / "active.json").exists():
                backup = self.root / "original-keyboards.nt"
                if not backup.exists():
                    shutil.copyfile(self.rdf_path, backup)
                directory = self.build(Graph().parse(self.rdf_path, format="nt"))
                self.stop(self.name)
                try:
                    self.start(directory, self.name, 7072)
                    self.publish(directory)
                except Exception:
                    self.stop(self.name)
                    raise
            else:
                info = self.inspect(self.name)
                if not info:
                    self.start(self.active(), self.name, 7072)
                elif not info["State"]["Running"]:
                    self.docker("start", self.name)
            self.assert_ready()
            # Any pending validation container is safe to discard after recovery.
            self.stop(self.name + ".check")
            job = self.root / "rebuild-job.json"
            if (
                job.exists()
                and json.loads(job.read_text(encoding="utf-8")).get("status")
                == "running"
            ):
                atomic_json(
                    job,
                    {
                        "status": "recovered",
                        "message": "Interrupted rebuild recovered; the previous working graph is active.",
                    },
                )
            return {
                "endpoint": self.endpoint,
                "container": self.name,
                "generation": self.active().name,
            }

    def rebuild(self, progress=lambda text: None):
        """Export, build, verify and switch indexes; roll back the old server on failure."""
        with self.exclusive():
            self.assert_ready()
            old = self.active()
            progress("Exporting current RDF; writes are locked")
            graph = self.snapshot()
            progress("Building a fresh index from exported keyboards.nt")
            directory = self.build(graph)
            candidate = self.name + ".check"
            try:
                self.stop(candidate)
                endpoint = self.start(directory, candidate, 0)
                if not isomorphic(graph, self.snapshot(endpoint)):
                    raise RuntimeError(
                        "Fresh index verification failed; old index is still active."
                    )
            finally:
                self.stop(candidate)
            # Preserve old source and full old generation, including its update log.
            shutil.copyfile(self.rdf_path, self.root / "rebuild-source-backup.nt")
            shutil.copyfile(self.rdf_path, directory / "previous-source.nt")
            atomic_json(
                self.root / "recovery.json", {"old": str(old.relative_to(self.root))}
            )
            try:
                progress("Switching indexes; queries may briefly pause")
                self.stop(self.name)
                self.start(directory, self.name, 7072)
                if not isomorphic(graph, self.snapshot()):
                    raise RuntimeError(
                        "Replacement index did not match the exported graph."
                    )
                temporary = self.rdf_path.with_suffix(".nt.tmp")
                shutil.copyfile(directory / "keyboards.nt", temporary)
                temporary.replace(self.rdf_path)
                self.publish(directory)
                (self.root / "recovery.json").unlink()
            except Exception:
                self.stop(self.name)
                self.start(old, self.name, 7072)
                self.publish(old)
                shutil.copyfile(self.root / "rebuild-source-backup.nt", self.rdf_path)
                (self.root / "recovery.json").unlink()
                raise
            progress("Index rebuilt and verified; keyboards.nt is up to date")
            return {
                "triples": len(graph),
                "generation": directory.name,
                "rdf_file": str(self.rdf_path),
            }
