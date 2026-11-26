"""Application entry points for graph review, writes and background rebuild jobs."""

import json
from threading import Lock, Thread

from functions.qlever_runtime import QLeverRuntime, atomic_json
from functions.rdf_models import property_catalog
from functions.rdf_store import RDFStore
from functions.similar_names import invalidate_name_cache

runtime = QLeverRuntime()
store = RDFStore(runtime)
_job_lock = Lock()
_job = None


def initialize_graph():
    """Start or recover the managed graph without discarding saved updates."""
    result = runtime.initialize()
    return result


def initialize_query_ui(port=8178):
    """Start the query editor against this checkout's managed graph."""
    from functions.qlever_ui import start_query_ui

    result = start_query_ui(runtime, port)
    return result


def status():
    """Report graph readiness and the latest rebuild job for the browser."""
    ready, message = False, ""
    try:
        runtime.assert_ready()
        ready = True
    except Exception as error:
        message = str(error)
    job = _job
    if job is None and (runtime.root / "rebuild-job.json").exists():
        job = json.loads(
            (runtime.root / "rebuild-job.json").read_text(encoding="utf-8")
        )
        if job["status"] == "running":
            job = {
                "status": "interrupted",
                "message": "Rebuild was interrupted. Run python tests/start_qlever.py to recover before editing.",
            }
    return {
        "ready": ready,
        "message": message,
        "endpoint": runtime.endpoint,
        "properties": property_catalog(),
        "rebuild": job,
    }


def preview_change(payload):
    """Validate and persist a proposed change; leave the graph untouched."""
    return store.preview(payload)


def confirm_change(payload):
    """Apply a confirmed preview idempotently and invalidate name suggestions."""
    result = store.commit(payload.get("preview_id"), payload.get("confirmed"))
    invalidate_name_cache()
    return result


def inspect_graph_entity(qid):
    """Read statement identities needed to choose a safe replacement."""
    return store.inspect(qid)


def search_graph_entities(text):
    """Find local entity-valued property candidates for human confirmation."""
    return {"matches": store.search(text)}


def verify_graph(payload):
    """Execute a generated read-only query for the requested entity/property."""
    return store.verify_query(
        payload.get("entity_id"), payload.get("property_id") or None
    )


def rebuild_graph(payload):
    """Start one background export/rebuild job after explicit confirmation."""
    global _job
    if payload.get("confirmed") is not True:
        raise ValueError("Confirm the RDF export and index rebuild first.")
    runtime.assert_ready()
    if not _job_lock.acquire(blocking=False):
        raise ValueError("An index rebuild is already running.")

    def progress(message):
        global _job
        _job = {"status": "running", "message": message}
        atomic_json(runtime.root / "rebuild-job.json", _job)

    def run():
        global _job
        try:
            result = runtime.rebuild(progress)
            invalidate_name_cache()
            _job = {
                "status": "complete",
                "message": "RDF exported and keyboards index rebuilt and verified.",
                **result,
            }
        except Exception as error:
            _job = {"status": "failed", "message": str(error)}
        finally:
            try:
                atomic_json(runtime.root / "rebuild-job.json", _job)
            finally:
                _job_lock.release()

    try:
        progress("Preparing rebuild")
        Thread(target=run, daemon=True, name="anywikia-rebuild").start()
    except Exception:
        _job = {"status": "failed", "message": "Could not start rebuild."}
        _job_lock.release()
        raise
    return dict(_job)
