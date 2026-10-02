from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from nucube.models.schema import Manifest


@dataclass
class Launch:
    handle: str
    job_id: str
    task_id: str
    attempt: int
    source: Path
    input: Path
    output: Path
    expires: float
    manifest: Manifest


@dataclass
class WorkerStatus:
    state: str  # running, exited, missing
    exit_code: int | None = None
    oom: bool = False
    started_at: float | None = None
    finished_at: float | None = None


class ExecutionBackend(Protocol):
    def launch(self, task: Launch) -> str: ...
    def inspect(self, handle: str) -> WorkerStatus: ...
    def stop(self, handle: str) -> None: ...
    def logs(self, handle: str) -> bytes: ...
    def collect_outputs(self, task: Launch) -> list[dict]: ...
    def cleanup(self, handle: str) -> None: ...
    def managed(self) -> list[dict]: ...


class MachineProvisioner(Protocol):
    """Future boundary ONLY: no implementation or cloud support in the local MVP."""

    def acquire(self, cpu: float, memory_mb: int) -> str: ...
    def release(self, machine_id: str) -> None: ...
