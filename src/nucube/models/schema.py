from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Runtime(StrictModel):
    image: str = Field(min_length=1, max_length=256)
    command: list[str] = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=4096)

    @model_validator(mode="after")
    def command_safe(self):
        if any("\0" in x or len(x) > 8192 for x in self.command):
            raise ValueError("invalid command argument")
        return self


class Task(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
    input: str = Field(min_length=1, max_length=4096)


class Resources(StrictModel):
    cpu_per_worker: float = Field(default=1, ge=0.01, le=1024)
    memory_mb_per_worker: int = Field(default=512, ge=32, le=1048576)
    max_workers: int = Field(default=1, ge=1, le=1024)


class Limits(StrictModel):
    task_timeout_seconds: int = Field(default=120, ge=1)
    job_timeout_seconds: int = Field(default=600, ge=1)
    max_retries: int = Field(default=0, ge=0, le=10)


class Manifest(StrictModel):
    api_version: Literal["nucube/v1"]
    name: str = Field(min_length=1, max_length=128)
    runtime: Runtime
    tasks: list[Task] = Field(min_length=1, max_length=1000)
    resources: Resources = Field(default_factory=Resources)
    limits: Limits = Field(default_factory=Limits)
    network: Literal["disabled", "enabled"] = "disabled"

    @model_validator(mode="after")
    def unique_tasks(self):
        if len({t.id for t in self.tasks}) != len(self.tasks):
            raise ValueError("duplicate task IDs")
        return self


class Config(StrictModel):
    storage: Path = Path("~/.local/share/nucube")
    max_workers: int = Field(default=4, ge=1, le=1024)
    total_cpu: float = Field(default=4, ge=0.01, le=1024)
    total_memory_mb: int = Field(default=2048, ge=32)
    allowed_images: list[str] = Field(default_factory=lambda: ["python:3.12-slim"])
    max_job_seconds: int = Field(default=3600, ge=1)
    max_retries: int = Field(default=2, ge=0, le=10)
    allow_network: bool = False
    artifact_retention_days: int = Field(default=7, ge=1)
    log_retention_days: int = Field(default=7, ge=1)
    max_snapshot_bytes: int = Field(default=16 * 1024 * 1024, ge=1, le=64 * 1024 * 1024)
    max_output_bytes: int = Field(default=64 * 1024 * 1024, ge=1)
    max_files: int = Field(default=2000, ge=1, le=10000)
    max_log_bytes: int = Field(default=256 * 1024, ge=1)
    pids_limit: int = Field(default=128, ge=1)
    tmp_mb: int = Field(default=64, ge=1)
    retry_backoff_seconds: float = Field(default=2, ge=0)
    poll_seconds: float = Field(default=0.5, gt=0, le=10)


def load_config(path: Path | None = None) -> Config:
    import os

    if path is None and os.environ.get("NUCUBE_CONFIG"):
        path = Path(os.environ["NUCUBE_CONFIG"])
    data = yaml.safe_load(path.read_text()) if path else {}
    config = Config.model_validate(data or {})
    config.storage = config.storage.expanduser().resolve()
    return config


class Submission(StrictModel):
    manifest: Manifest
    # Base64 file contents, never controller-side arbitrary host paths.
    source_files: dict[str, str] = Field(max_length=10000)
    inputs: dict[str, str] = Field(max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)
