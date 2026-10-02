import base64
import time

import pytest

from nucube.backends.base import WorkerStatus
from nucube.backends.docker import PREFIX
from nucube.controller.service import Service
from nucube.models.schema import Config, Submission
from nucube.storage.artifacts import manifest_for, tree


class FakeBackend:
    def __init__(self):
        self.workers = {}
        self.specs = {}
        self.cleaned = []

    def launch(self, task):
        self.workers[task.handle] = WorkerStatus("running", started_at=time.time())
        self.specs[task.handle] = task
        return task.handle

    def inspect(self, handle):
        return self.workers.get(handle, WorkerStatus("missing"))

    def stop(self, handle):
        if handle in self.workers:
            self.workers[handle] = WorkerStatus("exited", 137)

    def logs(self, handle):
        return b"untrusted log\n"

    def collect_outputs(self, task):
        return manifest_for(tree(task.output, 1024, 10))

    def cleanup(self, handle):
        self.cleaned.append(handle)
        self.workers.pop(handle, None)

    def managed(self):
        return [
            {"handle": h, "labels": {PREFIX + "expires": str(self.specs[h].expires)}}
            for h in self.workers
        ]

    def complete(self, code=0, oom=False):
        for handle in list(self.workers):
            self.specs[handle].output.joinpath("result.txt").write_text("answer")
            self.workers[handle] = WorkerStatus("exited", code, oom, time.time() - 0.1, time.time())


def submission(tasks=1, **overrides):
    m = {
        "api_version": "nucube/v1",
        "name": "test",
        "runtime": {
            "image": "python:3.12-slim",
            "command": ["python", "/workspace/main.py"],
            "source": ".",
        },
        "tasks": [{"id": f"task-{n}", "input": "in.json"} for n in range(tasks)],
    }
    m.update(overrides)
    return Submission(
        manifest=m,
        source_files={"main.py": base64.b64encode(b"print('hello')").decode()},
        inputs={f"task-{n}": base64.b64encode(b"{}").decode() for n in range(tasks)},
    )


@pytest.fixture
def service(tmp_path):
    s = Service(Config(storage=tmp_path, retry_backoff_seconds=0), FakeBackend())
    yield s
    s.close()
