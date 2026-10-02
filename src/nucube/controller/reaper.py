import time

from nucube.backends.base import ExecutionBackend
from nucube.backends.docker import PREFIX


def reap(backend: ExecutionBackend, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    removed = []
    errors = []
    for resource in backend.managed():
        try:
            expires = float(resource["labels"][PREFIX + "expires"])
            if expires <= now:
                backend.cleanup(resource["handle"])
                removed.append(resource["handle"])
        except Exception as exc:
            errors.append({"handle": resource["handle"], "error": type(exc).__name__})
    return {"removed": removed, "errors": errors}
