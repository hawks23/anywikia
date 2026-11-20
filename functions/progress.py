"""Small CLI progress messages, always on stderr so stdout can contain JSON.

Library imports stay quiet unless the caller enables progress. Long operations
emit a waiting message every ten seconds; no source text or credentials are logged.
"""
from contextlib import contextmanager
import logging
import sys
from threading import Event, Thread
from time import monotonic

logger = logging.getLogger("anywikia.progress")
logger.addHandler(logging.NullHandler())
logger.propagate = False


def configure_progress(quiet: bool = False) -> None:
    """Enable concise progress for CLI runs without enabling HTTP/SDK debug logs."""
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[anywikia] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING if quiet else logging.INFO)


def report(message: str) -> None:
    """Report a short stage summary without printing extracted source content."""
    logger.info(message)


@contextmanager
def step(label: str, interval: float = 10):
    """Report start, elapsed completion/failure, and waits during a blocking call.

    Exceptions are re-raised unchanged. A background reporter stops on every exit.
    """
    started = monotonic()
    stopped = Event()

    def waiting():
        while not stopped.wait(interval):
            report(f"{label}: still waiting ({monotonic() - started:.0f}s)")

    report(f"{label}...")
    worker = None
    if logger.isEnabledFor(logging.INFO):
        worker = Thread(target=waiting, daemon=True)
        worker.start()
    try:
        yield
    except BaseException:
        report(f"{label}: failed after {monotonic() - started:.1f}s")
        raise
    else:
        report(f"{label}: done ({monotonic() - started:.1f}s)")
    finally:
        stopped.set()
        if worker is not None:
            worker.join()
