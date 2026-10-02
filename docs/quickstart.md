# Quickstart

Requires Python 3.12+, uv, and a running local Linux Docker Engine (Docker Desktop works on macOS). Linux/macOS controller support only. The controller and Docker daemon must see the same filesystem paths. Remote Docker daemons and Windows controllers are not supported.

From the repository:

```bash
uv sync --locked
# Explicit operator image download; workers do not pull images themselves.
docker pull python:3.12-slim
uv run nucube doctor
uv run nucube serve
```

In another terminal, in the same repository:

```bash
uv run nucube run examples/cpu/job.yaml --wait
uv run python examples/benchmark.py --workers 2 --output /tmp/nucube-benchmark.json
```

Without `--wait`, `run` prints a JSON response containing the stable job `id` and returns immediately after snapshot submission. `--wait` returns a nonzero exit code when the job is unsuccessful. Replace `JOB_ID` below with the returned ID:

```bash
uv run nucube jobs
uv run nucube inspect JOB_ID
uv run nucube logs JOB_ID --task batch-001
uv run nucube artifacts JOB_ID
uv run nucube read-artifact JOB_ID batch-001 1 result.json
uv run nucube cancel JOB_ID
```

Artifact reads return base64, a byte offset, total size and EOF flag; use `--offset` for subsequent chunks. `inspect` defaults to 100 tasks; use `--task-offset` for large jobs. Artifact listings support `--limit` and `--offset`. Logs default to the latest attempt; `--attempt 1` selects an earlier one.

Copy `nucube.example.yaml` to your own configuration and set `NUCUBE_CONFIG` to its absolute path, or pass `serve --config /path/to/config.yaml`. Use the same configuration for doctor and reaper. `NUCUBE_URL` changes the loopback controller URL (default `http://127.0.0.1:8765`); `serve --port` changes the server port. No non-loopback URL is supported.

Allocate CPU and memory conservatively, leaving room for the host and Docker. `doctor` reports daemon capacity alongside configured capacity; these are configuration budgets, not reservations against unrelated Docker workloads.

Repeat a submission safely with `--idempotency-key YOUR_KEY`. The same key and identical snapshotted content return the same job. Changed content with that key returns `IDEMPOTENCY_CONFLICT`. Store your key before submission when handling uncertain HTTP outcomes.

## Independent cleanup

```bash
uv run nucube reap --expired --config /absolute/path/nucube.yaml
```

Run periodically using your operating system scheduler. Example cron entry (replace paths with absolute paths; ensure the scheduler can access Docker):

```cron
* * * * * /path/to/nucube/.venv/bin/nucube reap --expired --config /path/to/nucube.yaml >> /path/to/nucube-reaper.log 2>&1
```

This removes expired containers belonging to that storage installation, even while the controller is stopped. It does not need SQLite or the controller lock. It does not delete records or output directories. The controller reconciles removed containers when it restarts. Rotate the cron log separately. Active controller deadlines are checked on scheduler passes; during controller downtime, reaper frequency determines the extra runtime before termination.

Stopping the controller leaves running workers in place for recovery. Restart with the same storage configuration. Only one controller process may own that storage; a filesystem lock enforces this.
