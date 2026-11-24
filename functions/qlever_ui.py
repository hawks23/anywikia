"""Launch the managed query UI with argument arrays, including paths with spaces."""
import time

import httpx
import yaml

from functions.qlever_runtime import atomic_json


def start_query_ui(runtime, port=8178):
    if type(port) is not int or not 1024 <= port <= 65535 or port == 7072:
        raise ValueError("Choose a UI port between 1024 and 65535, other than 7072.")
    print("Starting or resuming the saved QLever graph...", flush=True)
    runtime.initialize()
    directory = runtime.root / "query-ui"
    directory.mkdir(parents=True, exist_ok=True)
    name = runtime.name + ".ui"
    image = "docker.io/adfreiburg/qlever-ui"
    database = directory / "keyboards.ui-db.sqlite3"
    if not database.exists():
        seed = name + ".seed"
        runtime.stop(seed)
        print("Preparing the query UI (first run may download its Docker image)...", flush=True)
        try:
            runtime.docker("create", "--name", seed, "--label", "anywikia.owner=" + runtime.owner, image, timeout=600)
            temporary = directory / "initial-db.sqlite3"
            runtime.docker("cp", seed + ":/app/db/qleverui.sqlite3", temporary)
            temporary.replace(database)
        finally:
            runtime.stop(seed)
    info = runtime.inspect(name)
    if info:
        ports = info.get("HostConfig", {}).get("PortBindings", {}).get("7000/tcp") or []
        mounts = info.get("Mounts", [])
        if not any(p.get("HostPort") == str(port) and p.get("HostIp") == "127.0.0.1" for p in ports) or not any(m.get("Destination") == "/app/db" for m in mounts):
            runtime.stop(name)
            info = None
    if not info:
        print(f"Starting query UI on port {port}...", flush=True)
        runtime.docker("run", "-d", "--name", name, "--label", "anywikia.owner=" + runtime.owner,
                       "--mount", f"type=bind,source={directory.resolve()},target=/app/db",
                       "--env", "QLEVERUI_DATABASE_URL=sqlite:////app/db/keyboards.ui-db.sqlite3",
                       "-p", f"127.0.0.1:{port}:7000", image, timeout=600)
    elif not info["State"]["Running"]:
        runtime.docker("start", name)
    # Reapply the endpoint even when the UI database already exists.
    config = yaml.safe_load(runtime.docker("exec", name, "python", "manage.py", "config", "default"))
    backend = config["config"]["backend"]
    backend.update(baseUrl=runtime.endpoint, isDefault=True, sortKey=1)
    atomic_json(directory / "working-ui.yml", config)  # JSON is valid YAML.
    runtime.docker("exec", name, "python", "manage.py", "config", "default",
                   "/app/db/working-ui.yml", "--hide-all-other-backends")
    url = f"http://127.0.0.1:{port}/default"
    for _ in range(30):
        try:
            response = httpx.get(url, timeout=2, follow_redirects=True)
            response.raise_for_status()
            runtime.query("ASK { ?s ?p ?o }")
            return {"url": url, "endpoint": runtime.endpoint, "container": name}
        except (httpx.HTTPError, ValueError):
            time.sleep(0.5)
    raise RuntimeError(f"UI or graph is not ready yet. Check docker logs {name}, then retry. Saved RDF is retained.")
