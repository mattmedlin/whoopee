import json
import time
from pathlib import Path
from typing import Annotated

import typer

from nucube.client import Client
from nucube.controller.service import TERMINAL
from nucube.errors import NucubeError

app = typer.Typer(help="nucube — local batch compute for agents.", no_args_is_help=True)


def emit(value: object) -> None:
    typer.echo(json.dumps(value, indent=2, default=str))


def request(method: str, path: str, **kwargs) -> dict:
    try:
        return Client().request(method, path, **kwargs)
    except NucubeError as exc:
        emit(exc.response())
        raise typer.Exit(1) from exc


@app.command()
def serve(config: Annotated[Path | None, typer.Option()] = None, port: int = 8765):
    """Run the single loopback controller; workers survive controller restarts."""
    import uvicorn

    from nucube.api.app import create_app
    from nucube.models.schema import load_config

    uvicorn.run(create_app(load_config(config)), host="127.0.0.1", port=port)


@app.command()
def run(manifest: Path, wait: bool = False, idempotency_key: str | None = None):
    """Snapshot local files and submit; return immediately unless --wait."""
    from pydantic import ValidationError

    try:
        result = Client().submit(str(manifest), idempotency_key)
    except (NucubeError, ValidationError, OSError) as exc:
        emit(
            exc.response()
            if isinstance(exc, NucubeError)
            else {"error": {"code": "INVALID_MANIFEST", "message": str(exc)}}
        )
        raise typer.Exit(1) from exc
    emit(result)
    if wait:
        while True:
            job = request("GET", f"/jobs/{result['id']}")
            if job["status"] in TERMINAL:
                emit(job)
                raise typer.Exit(0 if job["status"] == "succeeded" else 1)
            time.sleep(0.5)


@app.command()
def jobs(limit: int = 50, offset: int = 0):
    emit(request("GET", "/jobs", params={"limit": limit, "offset": offset}))


@app.command()
def inspect(job_id: str, task_limit: int = 100, task_offset: int = 0):
    emit(
        request(
            "GET", f"/jobs/{job_id}", params={"task_limit": task_limit, "task_offset": task_offset}
        )
    )


@app.command()
def logs(job_id: str, task: Annotated[str, typer.Option()], attempt: int | None = None):
    emit(
        request(
            "GET", f"/jobs/{job_id}/logs/{task}", params={"attempt": attempt} if attempt else {}
        )
    )


@app.command()
def artifacts(job_id: str, limit: int = 100, offset: int = 0):
    emit(request("GET", f"/jobs/{job_id}/artifacts", params={"limit": limit, "offset": offset}))


@app.command("read-artifact")
def read_artifact(job_id: str, task: str, attempt: int, path: str, offset: int = 0):
    emit(
        request(
            "GET",
            f"/jobs/{job_id}/artifact",
            params={"task_id": task, "attempt": attempt, "path": path, "offset": offset},
        )
    )


@app.command()
def cancel(job_id: str):
    emit(request("POST", f"/jobs/{job_id}/cancel"))


@app.command()
def doctor(config: Annotated[Path | None, typer.Option()] = None):
    from nucube.backends.docker import DockerBackend
    from nucube.controller.service import owner_id
    from nucube.models.schema import load_config

    c = load_config(config)
    result = {
        "backend": "docker",
        "provisions_machines": False,
        "storage": str(c.storage),
        "configured_cpu": c.total_cpu,
        "configured_memory_mb": c.total_memory_mb,
    }
    try:
        backend = DockerBackend(c, owner_id(c))
        info = backend.client.info()
        result.update(
            docker_version=info["ServerVersion"],
            daemon_cpu=info["NCPU"],
            daemon_memory_mb=info["MemTotal"] // (1024 * 1024),
        )
        result["images"] = {
            image: bool(backend.client.images.list(name=image)) for image in c.allowed_images
        }
        emit(result)
    except Exception as exc:
        result["error"] = {"code": "DOCKER_UNAVAILABLE", "message": str(exc)}
        emit(result)
        raise typer.Exit(1) from exc


@app.command()
def reap(expired: bool = False, config: Annotated[Path | None, typer.Option()] = None):
    """Independently remove expired workers owned by this storage installation."""
    from nucube.backends.docker import DockerBackend
    from nucube.controller.reaper import reap as reap_workers
    from nucube.controller.service import owner_id
    from nucube.models.schema import load_config

    if not expired:
        raise typer.BadParameter("Pass --expired")
    c = load_config(config)
    result = reap_workers(DockerBackend(c, owner_id(c)))
    emit(result)
    if result["errors"]:
        raise typer.Exit(1)


@app.command()
def mcp():
    """Run the official MCP SDK stdio server, backed by the HTTP controller."""
    from nucube.mcp.server import server

    server.run(transport="stdio")
