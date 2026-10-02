import base64
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from nucube.errors import NucubeError
from nucube.models.schema import Manifest, Submission
from nucube.storage.artifacts import read_safe, tree


def bundle(path: Path, key: str | None = None) -> Submission:
    path = path.expanduser().absolute()
    try:
        manifest_bytes = read_safe(path.parent, path.name, 1024 * 1024)
        m = Manifest.model_validate(yaml.safe_load(manifest_bytes))
    except yaml.YAMLError as exc:
        raise NucubeError("INVALID_MANIFEST", "Malformed YAML manifest") from exc
    source = path.parent / m.runtime.source
    if source.is_symlink() or not source.is_dir():
        raise NucubeError("UNSAFE_PATH", "Source must be a regular directory")
    files = tree(source, 64 * 1024 * 1024, 10000)
    inputs = {}
    remaining = 64 * 1024 * 1024 - sum(map(len, files.values()))
    for task in m.tasks:
        p = (path.parent / task.input).absolute()
        if p.is_symlink():
            raise NucubeError("UNSAFE_PATH", "Input symlinks are forbidden")
        data = read_safe(p.parent, p.name, remaining)
        remaining -= len(data)
        inputs[task.id] = base64.b64encode(data).decode()
    return Submission(
        manifest=m,
        source_files={k: base64.b64encode(v).decode() for k, v in files.items()},
        inputs=inputs,
        idempotency_key=key,
    )


class Client:
    def __init__(self, url: str | None = None):
        self.url = (url or os.environ.get("NUCUBE_URL", "http://127.0.0.1:8765")).rstrip("/")
        parsed = urlparse(self.url)
        if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise NucubeError("LOCAL_ONLY", "MVP controller URL must be loopback HTTP")

    def request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = httpx.request(method, self.url + path, timeout=60, trust_env=False, **kwargs)
        except httpx.HTTPError as exc:
            raise NucubeError("CONTROLLER_UNAVAILABLE", "Cannot reach nucube serve", 503) from exc
        if response.is_error:
            try:
                err = response.json()["error"]
            except (ValueError, KeyError, TypeError):
                err = {"code": "CONTROLLER_ERROR", "message": f"HTTP {response.status_code}"}
            raise NucubeError(err["code"], err["message"], response.status_code)
        return response.json()

    def submit(self, manifest_path: str, idempotency_key: str | None = None) -> dict:
        return self.request(
            "POST", "/jobs", json=bundle(Path(manifest_path), idempotency_key).model_dump()
        )
