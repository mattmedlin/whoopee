import os
from datetime import datetime

import docker
from docker.errors import NotFound

from nucube.backends.base import Launch, WorkerStatus
from nucube.errors import NucubeError
from nucube.models.schema import Config
from nucube.storage.artifacts import manifest_for, tree

PREFIX = "io.nucube."


class DockerBackend:
    def __init__(self, config: Config, owner: str):
        self.config = config
        self.owner = owner
        self.client = docker.from_env(timeout=10)

    def _container(self, handle: str):
        try:
            c = self.client.containers.get(handle)
        except NotFound:
            return None
        labels = c.labels
        if (
            labels.get(PREFIX + "owner") != self.owner
            or labels.get(PREFIX + "managed") != "v1"
            or not all(labels.get(PREFIX + k) for k in ("job", "task", "attempt", "expires"))
        ):
            raise NucubeError("OWNERSHIP_MISMATCH", "Refusing to touch an unowned container")
        return c

    def launch(self, task: Launch) -> str:
        m = task.manifest
        labels = {
            PREFIX + "managed": "v1",
            PREFIX + "owner": self.owner,
            PREFIX + "job": task.job_id,
            PREFIX + "task": task.task_id,
            PREFIX + "attempt": str(task.attempt),
            PREFIX + "expires": str(task.expires),
        }
        c = self.client.containers.create(
            m.runtime.image,
            command=m.runtime.command,
            entrypoint=[],
            name=task.handle,
            labels=labels,
            user=f"{os.getuid() or 65534}:{os.getgid() or 65534}",
            working_dir="/workspace",
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            network_mode=("bridge" if m.network == "enabled" else "none"),
            nano_cpus=int(m.resources.cpu_per_worker * 1e9),
            mem_limit=f"{m.resources.memory_mb_per_worker}m",
            memswap_limit=f"{m.resources.memory_mb_per_worker}m",
            pids_limit=self.config.pids_limit,
            tmpfs={"/tmp": f"rw,noexec,nosuid,size={self.config.tmp_mb}m,mode=1777"},
            volumes={
                str(task.source): {"bind": "/workspace", "mode": "ro"},
                str(task.input): {"bind": "/input/input.json", "mode": "ro"},
                str(task.output): {"bind": "/output", "mode": "rw"},
            },
            environment={
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "NUCUBE_ATTEMPT": str(task.attempt),
            },
            log_config=docker.types.LogConfig(
                type="local",
                config={
                    "max-size": str(self.config.max_log_bytes),
                    "max-file": "1",
                    "compress": "false",
                },
            ),
        )
        c.start()
        return task.handle

    def inspect(self, handle: str) -> WorkerStatus:
        c = self._container(handle)
        if c is None:
            return WorkerStatus("missing")
        s = c.attrs["State"]

        def stamp(value: str) -> float | None:
            if value.startswith("0001"):
                return None
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()

        return WorkerStatus(
            "exited" if s["Status"] in ("exited", "dead") else "running",
            s.get("ExitCode"),
            s.get("OOMKilled", False),
            stamp(s["StartedAt"]),
            stamp(s["FinishedAt"]),
        )

    def stop(self, handle: str) -> None:
        c = self._container(handle)
        if c is not None and c.status not in ("exited", "dead"):
            # Kill also covers paused workers; no unbounded graceful shutdown.
            if c.status == "paused":
                c.unpause()
            if c.status != "created":
                c.kill()
                c.wait(timeout=10)

    def logs(self, handle: str) -> bytes:
        c = self._container(handle)
        if c is None:
            return b""
        output = bytearray()
        for chunk in c.logs(stream=True, follow=False):
            output.extend(chunk[: self.config.max_log_bytes - len(output)])
            if len(output) >= self.config.max_log_bytes:
                break
        return bytes(output)

    def collect_outputs(self, task: Launch) -> list[dict]:
        return manifest_for(tree(task.output, self.config.max_output_bytes, self.config.max_files))

    def cleanup(self, handle: str) -> None:
        c = self._container(handle)
        if c is not None:
            c.remove(force=True)

    def managed(self) -> list[dict]:
        result = []
        for c in self.client.containers.list(
            all=True, filters={"label": [PREFIX + "managed=v1", PREFIX + "owner=" + self.owner]}
        ):
            if c.name is None:
                continue
            checked = self._container(c.name)
            if checked is not None:
                result.append({"handle": checked.name, "labels": checked.labels})
        return result
