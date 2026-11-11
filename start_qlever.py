"""Start QLever using keyboards-index, independently of the working directory."""
import json
from pathlib import Path
import subprocess
import sys
import time

import httpx

from local_rdf import INDEX_DIR, SPARQL_ENDPOINT


def main():
    container = "qlever.server.anywikia"
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("Docker is unavailable. Start Docker Desktop and enable "
                         "Ubuntu WSL integration, then retry.")
    result = subprocess.run(
        ["docker", "inspect", container], capture_output=True, text=True
    )
    if result.returncode == 0:
        info = json.loads(result.stdout)[0]
        mount = next((m["Source"] for m in info["Mounts"]
                      if m["Destination"] == "/index"), None)
        if mount != str(INDEX_DIR):
            raise SystemExit(f"Existing container mounts {mount}, expected {INDEX_DIR}")
        if not info["State"]["Running"]:
            subprocess.run(["docker", "start", container], check=True)
    else:
        qlever = Path(sys.executable).parent / "qlever"
        if not (INDEX_DIR / "keyboards.index.spo").exists():
            raise SystemExit("Index missing. From keyboards-index run: "
                             "../.venv/bin/qlever index")
        subprocess.run([str(qlever), "start"], cwd=INDEX_DIR, check=True)
    for _ in range(30):
        try:
            response = httpx.post(SPARQL_ENDPOINT,
                                  data={"query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"},
                                  headers={"Accept": "application/sparql-results+json"},
                                  timeout=2)
            response.raise_for_status()
            if "results" in response.json():
                break
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(0.5)
    else:
        raise SystemExit(f"QLever is not ready. Check {INDEX_DIR / 'keyboards.server-log.txt'}")
    print(f"QLever endpoint: {SPARQL_ENDPOINT}")


if __name__ == "__main__":
    main()
