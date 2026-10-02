# Architecture and execution semantics

```text
Agent (MCP stdio) / CLI
          | shared HTTP client and immutable snapshot upload
          v
FastAPI loopback API
          |
Controller service — policy, transitions, cancellations
    |              |                |
SQLite WAL     local artifacts   scheduler thread
                                    |
                         ExecutionBackend protocol
                                    |
                               Docker Engine
```

The API layer validates request shape and bounds request bytes; the controller independently enforces policy. Both CLI and MCP call the same HTTP controller. Files are resolved beside the manifest by the submitting client and uploaded as bounded base64 data; the API never interprets manifest paths as arbitrary controller host paths. Source and task JSON inputs are copied at submission. Later edits do not alter queued work. Snapshots preserve bytes and relative names, not executable modes; invoke scripts through their interpreter.

SQLite stores separate job, task and attempt records. Each state transition commits atomically with WAL and FULL synchronous writes. Files are written before insertion; a crash during submission may leave an unreferenced snapshot directory. Records remain indefinitely. The controller expires artifact/snapshot and log files for terminal jobs according to policy, at startup and every 120 scheduling passes.

One controller process owns storage via a POSIX advisory lock. API operations and the synchronous scheduler serialize state transitions using an RLock. Docker calls have a 10-second request timeout. This intentionally simple design limits API responsiveness during Engine stalls; it is not a high-throughput controller.

## Scheduling

Jobs transition `queued → running → succeeded | failed | cancelled | timed_out`. Tasks transition similarly, but classified failures can return to `queued` after backoff. Queued cancellation and queue-expired jobs can transition directly to a terminal state. Each attempt has its own terminal status, timestamps, exit code, error, output directory and retry classification.

The scheduler accounts for active workers across all jobs before launching. It enforces global worker count, per-job worker count, configured CPU and memory capacity. Per-job max_workers may exceed global capacity; scheduling still respects the smaller available budget. Impossible individual worker requests are rejected. One worker is started per eligible job per pass; this is basic admission fairness, not priority scheduling or guaranteed starvation prevention.

Job timeout starts at accepted submission, including queue time and backoff. Task timeout starts at persisted launch intent, including container startup. Timeouts do not retry. Application exit 75 (`EX_TEMPFAIL`) and missing workers retry within the bounded retry count; nonzero ordinary exits, OOM and unsafe/oversized output fail permanently. Backoff is `retry_backoff_seconds * 2^(attempt-1)`. No jitter or DAGs in this MVP.

Cancellation first persists an intent, then terminates running workers and cancels queued tasks. Completed task outputs remain accessible. A cleanup error leaves a durable recovery path; capacity is not silently released after uncertain launch outcomes.

## Crash recovery

Before creating a container, persist its deterministic name and attempt. Containers carry installation ownership, job, task, attempt and expiration labels. Each pass inspects those names, resumes live workers, collects exited workers and retries lost workers only when allowed. Created-but-never-started containers stay reserved until their deadline. Unknown launch RPC outcomes also remain reserved for inspection. Successful outputs are published via fsync + atomic rename before the successful transition commits. Commit terminal attempt state before removing its container. Reconciliation removes managed containers not referenced by running attempts; unrelated installations/containers are excluded.

Execution is **at least once**, not exactly once. A vanished worker may have performed external effects before being retried. Retryable programs must tolerate repeated execution, especially when network access is enabled. Idempotency keys deduplicate submission, not external side effects of tasks.

Each attempt gets a separate output directory. Collected regular-file metadata includes size and SHA-256; successful tasks also get an atomically replaced `result.json` manifest. Failed attempt outputs are retained when safely collectible. An unsafe/oversized output tree is not published but remains on disk until retention; it must be treated as untrusted.

## Metrics and future provisioning

Elapsed time is acceptance to completion (or now). Allocated CPU-seconds are configured CPU multiplied by the interval from launch intent to recorded exit/termination for every attempt, including failed attempts. They measure allocation accounting, **not actual utilization**. Startup overhead is launch-intent to Docker StartedAt, summed across attempts; overlapping startup time is not additive wall time.

`ExecutionBackend` launches/inspects/stops/collects/cleans workers. `MachineProvisioner` is a separate, unimplemented interface for future acquisition/release of machines. Container creation uses existing capacity. Next milestone: one opt-in machine provisioner, bootstrapping and readiness, machine leases, heartbeat loss handling, remote artifact transport, reliable teardown, provider accounting and price-aware budgets. Dollar-budget enforcement requires pricing plus billing-delay treatment and is not implemented.

## Relationship to existing orchestrators

nucube offers a small agent-facing submission contract and local temporary batch workers. Agents retain planning and judgment. It complements larger orchestration systems by exposing a focused compute workflow; it does not replace their fleet management, queueing ecosystems, autoscaling, or operational guarantees. No Kubernetes integration or compatibility is claimed. A future execution adapter could target an existing scheduler independently of the machine provisioning layer.
