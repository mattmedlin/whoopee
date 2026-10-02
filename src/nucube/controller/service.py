import base64
import fcntl
import hashlib
import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from nucube.backends.base import ExecutionBackend, Launch
from nucube.errors import NucubeError
from nucube.models.schema import Config, Manifest, Submission
from nucube.storage.artifacts import atomic_json, decode_files, read_safe, safe_parts
from nucube.storage.store import Store

TERMINAL = {"succeeded", "failed", "cancelled", "timed_out"}


def owner_id(config: Config) -> str:
    config.storage.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = config.storage / "owner"
    with path.open("a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        owner = f.read().strip()
        if not owner:
            owner = uuid.uuid4().hex
            f.write(owner)
            f.flush()
            __import__("os").fsync(f.fileno())
        return owner


class Service:
    def __init__(self, config: Config, backend: ExecutionBackend):
        self.config = config
        self.backend = backend
        config.storage.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lease = (config.storage / "controller.lock").open("a")
        try:
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lease.close()
            raise NucubeError(
                "CONTROLLER_RUNNING", "Only one controller may use this storage"
            ) from exc
        self.store = Store(config.storage)
        self.lock = threading.RLock()
        self.last_error: str | None = None

    def close(self) -> None:
        self.store.db.close()
        self._lease.close()

    def root(self, job_id: str) -> Path:
        return self.config.storage / "jobs" / job_id

    def get(self, job_id: str) -> dict:
        with self.lock:
            job = self.store.get(job_id)
            if job is None:
                raise NucubeError("NOT_FOUND", "Job not found", 404)
            now = time.time()
            job["elapsed_seconds"] = (job["finished_at"] or now) - job["created_at"]
            job["allocated_cpu_seconds"] = sum(
                max(0, (a["finished_at"] or now) - a["created_at"])
                * job["manifest"]["resources"]["cpu_per_worker"]
                for t in job["tasks"]
                for a in t["attempts"]
            )
            return job

    def public_job(self, job_id: str, task_limit: int = 100, task_offset: int = 0) -> dict:
        job = self.get(job_id)
        job.pop("key", None)
        job.pop("fingerprint", None)
        all_tasks = job["tasks"]
        job["task_count"] = len(all_tasks)
        job["task_offset"] = task_offset
        job["tasks"] = all_tasks[task_offset : task_offset + task_limit]
        job["manifest"].pop("tasks", None)
        for task in job["tasks"]:
            task.pop("artifacts", None)
            for attempt in task["attempts"]:
                attempt["artifact_count"] = len(attempt.pop("artifacts"))
        return job

    def list_jobs(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self.lock:
            return [
                {k: j[k] for k in ("id", "name", "status", "created_at", "finished_at")}
                for i in self.store.ids()[::-1][offset : offset + min(limit, 100)]
                if (j := self.store.get(i))
            ]

    def validate(self, m: Manifest) -> None:
        c = self.config
        if m.runtime.image not in c.allowed_images:
            raise NucubeError("IMAGE_DENIED", "Runtime image is not allowed by controller policy")
        if m.network == "enabled" and not c.allow_network:
            raise NucubeError("NETWORK_DENIED", "Controller policy disables networking")
        if (
            m.resources.cpu_per_worker > c.total_cpu
            or m.resources.memory_mb_per_worker > c.total_memory_mb
        ):
            raise NucubeError(
                "RESOURCE_LIMIT", "An individual worker cannot fit configured capacity"
            )
        if (
            m.limits.job_timeout_seconds > c.max_job_seconds
            or m.limits.task_timeout_seconds > c.max_job_seconds
            or m.limits.max_retries > c.max_retries
        ):
            raise NucubeError(
                "POLICY_LIMIT", "Requested duration or retries exceed controller policy"
            )

    def submit(self, request: Submission) -> dict:
        with self.lock:
            self.validate(request.manifest)
            payload = request.model_dump(exclude={"idempotency_key"})
            fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            if request.idempotency_key and (old := self.store.by_key(request.idempotency_key)):
                if old["fingerprint"] != fingerprint:
                    raise NucubeError(
                        "IDEMPOTENCY_CONFLICT", "Key was used with different content", 409
                    )
                return {"id": old["id"], "status": old["status"], "duplicate": True}
            source = decode_files(
                request.source_files, self.config.max_snapshot_bytes, self.config.max_files
            )
            inputs = decode_files(
                request.inputs,
                self.config.max_snapshot_bytes - sum(map(len, source.values())),
                self.config.max_files - len(source),
            )
            if set(inputs) != {t.id for t in request.manifest.tasks}:
                raise NucubeError("INVALID_INPUT", "Exactly one input is required per task")
            for content in inputs.values():
                try:
                    json.loads(content)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise NucubeError("INVALID_INPUT", "Inputs must be JSON") from exc
            jid = uuid.uuid4().hex
            root = self.root(jid)
            try:
                for section, files in (("source", source), ("inputs", inputs)):
                    (root / section).mkdir(parents=True)
                    for name, data in files.items():
                        path = root / section / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(data)
                        path.chmod(0o444)
                manifest = request.manifest.model_dump()
                atomic_json(root / "manifest.json", manifest)
                job = {
                    "id": jid,
                    "name": request.manifest.name,
                    "key": request.idempotency_key,
                    "fingerprint": fingerprint,
                    "manifest": manifest,
                    "status": "queued",
                    "created_at": time.time(),
                    "started_at": None,
                    "finished_at": None,
                    "stop_reason": None,
                    "tasks": [
                        {
                            "id": t.id,
                            "status": "queued",
                            "next_run_at": 0.0,
                            "artifacts": [],
                            "attempts": [],
                        }
                        for t in request.manifest.tasks
                    ],
                }
                self.store.save(job)
            except Exception:
                shutil.rmtree(root, ignore_errors=True)
                raise
            return {"id": jid, "status": "queued", "duplicate": False}

    def launch_spec(self, job: dict, task: dict, attempt: dict) -> Launch:
        root = self.root(job["id"])
        m = Manifest.model_validate(job["manifest"])
        return Launch(
            attempt["handle"],
            job["id"],
            task["id"],
            attempt["number"],
            root / "source",
            root / "inputs" / task["id"],
            root / "attempts" / task["id"] / str(attempt["number"]) / "output",
            min(
                job["created_at"] + m.limits.job_timeout_seconds,
                attempt["created_at"] + m.limits.task_timeout_seconds,
            ),
            m,
        )

    def finish(
        self,
        job: dict,
        task: dict,
        status: str,
        code: int | None,
        error: str | None,
        retryable: bool = False,
        finished_at: float | None = None,
    ) -> None:
        a = task["attempts"][-1]
        spec = self.launch_spec(job, task, a)
        # Workers must already be stopped before collecting; failures here remain recoverable.
        log = self.backend.logs(a["handle"])
        (spec.output.parent / "log.txt").write_bytes(log[: self.config.max_log_bytes])
        try:
            artifacts = self.backend.collect_outputs(spec)
        except NucubeError as exc:
            artifacts = []
            if status == "succeeded":
                status, error, retryable = "failed", exc.code, False
        a.update(
            status=status,
            finished_at=finished_at or time.time(),
            exit_code=code,
            error=error,
            retryable=retryable,
            artifacts=artifacts,
        )
        if status == "succeeded":
            atomic_json(
                spec.output.parent.parent / "result.json",
                {"attempt": a["number"], "artifacts": artifacts},
            )
            task["artifacts"] = artifacts
        if retryable and a["number"] <= job["manifest"]["limits"]["max_retries"]:
            task["status"] = "queued"
            task["next_run_at"] = time.time() + self.config.retry_backoff_seconds * 2 ** (
                a["number"] - 1
            )
        else:
            task["status"] = status
        # Commit before removal: replay cleanup without replaying successful work.
        self.store.save(job)
        self.backend.cleanup(a["handle"])

    def cancel(self, jid: str) -> dict:
        with self.lock:
            job = self.get(jid)
            if job["status"] not in TERMINAL:
                job["stop_reason"] = "cancelled"
                self.store.save(job)
                self._stop_job(job, "cancelled")
            return self.get(jid)

    def _stop_job(self, job: dict, reason: str) -> None:
        for task in job["tasks"]:
            if task["status"] == "running":
                self.backend.stop(task["attempts"][-1]["handle"])
                self.finish(job, task, reason, None, reason.upper())
            elif task["status"] == "queued":
                task["status"] = reason
        job.update(status=reason, finished_at=time.time())
        self.store.save(job)

    def tick(self) -> None:
        with self.lock:
            self._tick()
            self.last_error = None

    def _tick(self) -> None:
        now = time.time()
        jobs = [j for i in self.store.ids() if (j := self.store.get(i)) is not None]
        # Cleanup crash leftovers, including create-before-start windows and terminal attempts.
        active = {
            a["handle"]
            for j in jobs
            for t in j["tasks"]
            for a in t["attempts"]
            if a["status"] == "running"
        }
        for resource in self.backend.managed():
            if resource["handle"] not in active:
                self.backend.cleanup(resource["handle"])
        for job in jobs:
            if job["status"] in TERMINAL:
                continue
            deadline = job["created_at"] + job["manifest"]["limits"]["job_timeout_seconds"]
            if job["stop_reason"] or now >= deadline:
                job["stop_reason"] = job["stop_reason"] or "timed_out"
                self.store.save(job)
                self._stop_job(job, job["stop_reason"])
                continue
            for task in job["tasks"]:
                if task["status"] != "running":
                    continue
                a = task["attempts"][-1]
                spec = self.launch_spec(job, task, a)
                state = self.backend.inspect(a["handle"])
                if state.started_at:
                    a["started_at"] = state.started_at
                    a["startup_seconds"] = max(0, state.started_at - a["created_at"])
                if state.state == "exited" and (
                    state.finished_at is None or state.finished_at <= spec.expires
                ):
                    good = state.exit_code == 0
                    # EX_TEMPFAIL (75) is the explicit application retry contract.
                    error = None if good else ("OUT_OF_MEMORY" if state.oom else "WORKER_EXIT")
                    self.finish(
                        job,
                        task,
                        "succeeded" if good else "failed",
                        state.exit_code,
                        error,
                        state.exit_code == 75 and not state.oom,
                        state.finished_at,
                    )
                elif now >= spec.expires:
                    self.backend.stop(a["handle"])
                    self.finish(job, task, "timed_out", None, "TASK_TIMEOUT")
                elif state.state == "missing":
                    self.finish(job, task, "failed", None, "WORKER_LOST", True)
            self._complete(job)
            self.store.save(job)
        running = [(j, t) for j in jobs for t in j["tasks"] if t["status"] == "running"]
        used_cpu = sum(j["manifest"]["resources"]["cpu_per_worker"] for j, _ in running)
        used_mem = sum(j["manifest"]["resources"]["memory_mb_per_worker"] for j, _ in running)
        count = len(running)
        # Round-robin jobs: at most one new worker per job per pass.
        while count < self.config.max_workers:
            launched = False
            for job in jobs:
                if job["status"] in TERMINAL:
                    continue
                if time.time() >= (
                    job["created_at"] + job["manifest"]["limits"]["job_timeout_seconds"]
                ):
                    continue  # next pass terminates active work and persists timeout
                r = job["manifest"]["resources"]
                per_job = sum(t["status"] == "running" for t in job["tasks"])
                if (
                    per_job >= r["max_workers"]
                    or count >= self.config.max_workers
                    or used_cpu + r["cpu_per_worker"] > self.config.total_cpu + 1e-9
                    or used_mem + r["memory_mb_per_worker"] > self.config.total_memory_mb
                ):
                    continue
                task = next(
                    (
                        t
                        for t in job["tasks"]
                        if t["status"] == "queued" and t["next_run_at"] <= time.time()
                    ),
                    None,
                )
                if task is None:
                    continue
                created = time.time()
                number = len(task["attempts"]) + 1
                a = {
                    "number": number,
                    "handle": f"nucube-{job['id']}-{task['id']}-{number}",
                    "status": "running",
                    "created_at": created,
                    "started_at": None,
                    "startup_seconds": None,
                    "finished_at": None,
                    "exit_code": None,
                    "error": None,
                    "retryable": False,
                    "artifacts": [],
                }
                task["attempts"].append(a)
                task["status"] = "running"
                job["status"] = "running"
                job["started_at"] = job["started_at"] or created
                spec = self.launch_spec(job, task, a)
                spec.output.mkdir(parents=True)
                # On root controllers, worker uid 65534 needs output write permission.
                spec.output.chmod(0o777 if __import__("os").getuid() == 0 else 0o755)
                self.store.save(job)
                try:
                    self.backend.launch(spec)
                except Exception as exc:
                    # Unknown launch outcomes reserve resources until reconciliation inspects
                    # the deterministic name. Do not launch a duplicate after an RPC timeout.
                    a["error"] = "LAUNCH_UNCERTAIN"
                    a["launch_error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
                    self.store.save(job)
                    raise
                count += 1
                used_cpu += r["cpu_per_worker"]
                used_mem += r["memory_mb_per_worker"]
                launched = True
            if not launched:
                break

    def _complete(self, job: dict) -> None:
        statuses = {t["status"] for t in job["tasks"]}
        if statuses <= TERMINAL:
            job["status"] = (
                "succeeded"
                if statuses == {"succeeded"}
                else "timed_out"
                if "timed_out" in statuses
                else "failed"
            )
            job["finished_at"] = time.time()

    def logs(self, jid: str, tid: str, attempt: int | None = None) -> dict:
        with self.lock:
            job = self.get(jid)
            task = next((t for t in job["tasks"] if t["id"] == tid), None)
            if not task or not task["attempts"]:
                raise NucubeError("NOT_FOUND", "Task attempt not found", 404)
            a = next(
                (a for a in task["attempts"] if a["number"] == (attempt or len(task["attempts"]))),
                None,
            )
            if a is None:
                raise NucubeError("NOT_FOUND", "Attempt not found", 404)
            if a["status"] == "running":
                data = self.backend.logs(a["handle"])
            else:
                path = self.launch_spec(job, task, a).output.parent / "log.txt"
                data = path.read_bytes() if path.exists() else b""
            return {
                "task_id": tid,
                "attempt": a["number"],
                "untrusted": True,
                "text": data[: self.config.max_log_bytes].decode(errors="replace"),
                "truncated": len(data) >= self.config.max_log_bytes,
            }

    def artifacts(self, jid: str, limit: int = 100, offset: int = 0) -> dict:
        job = self.get(jid)
        items = [
            {"task_id": t["id"], "attempt": a["number"], "status": a["status"], **item}
            for t in job["tasks"]
            for a in t["attempts"]
            for item in a["artifacts"]
        ]
        return {"untrusted": True, "total": len(items), "items": items[offset : offset + limit]}

    def read_artifact(
        self, jid: str, tid: str, attempt: int, path: str, offset: int = 0, limit: int = 65536
    ) -> dict:
        safe_parts(path)
        with self.lock:
            job = self.get(jid)
            task = next((t for t in job["tasks"] if t["id"] == tid), None)
            a = (
                next((a for a in task["attempts"] if a["number"] == attempt), None)
                if task
                else None
            )
            if task is None or not a or path not in {f["path"] for f in a["artifacts"]}:
                raise NucubeError("NOT_FOUND", "Published artifact not found", 404)
            data = read_safe(
                self.launch_spec(job, task, a).output, path, self.config.max_output_bytes
            )
            chunk = data[offset : offset + min(limit, 65536)]
            return {
                "untrusted": True,
                "encoding": "base64",
                "data": base64.b64encode(chunk).decode(),
                "offset": offset,
                "total_bytes": len(data),
                "eof": offset + len(chunk) >= len(data),
            }

    def retention(self) -> None:
        """Expire files, retain durable job/attempt metadata indefinitely."""
        with self.lock:
            now = time.time()
            for jid in self.store.ids():
                job = self.store.get(jid)
                if job is None or job["status"] not in TERMINAL:
                    continue
                age = now - job["finished_at"]
                if age > self.config.log_retention_days * 86400:
                    for path in self.root(jid).glob("attempts/*/*/log.txt"):
                        path.unlink(missing_ok=True)
                if age > self.config.artifact_retention_days * 86400:
                    shutil.rmtree(self.root(jid), ignore_errors=True)
                    for task in job["tasks"]:
                        task["artifacts"] = []
                        for a in task["attempts"]:
                            a["artifacts"] = []
                    job["artifacts_expired"] = True
                    self.store.save(job)
