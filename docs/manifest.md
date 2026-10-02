# Job manifest reference

See the runnable [`examples/cpu/job.yaml`](../examples/cpu/job.yaml).

| Field | Contract |
| --- | --- |
| `api_version` | Required, exactly `nucube/v1` |
| `name` | Required, 1–128 characters |
| `runtime.image` | Required; exact entry in controller `allowed_images`; pre-pulled |
| `runtime.command` | Required nonempty argument array; no implicit shell; overrides image entrypoint |
| `runtime.source` | Required source directory; relative to manifest or absolute |
| `tasks` | 1–1000 independent tasks; unique IDs |
| `tasks[].id` | ASCII letters/digits followed by letters/digits/underscore/hyphen; max 64 characters |
| `tasks[].input` | JSON file relative to manifest or absolute |
| `resources.cpu_per_worker` | CPU allocation at least 0.01, default 1 |
| `resources.memory_mb_per_worker` | Integer, at least 32 MiB, default 512 |
| `resources.max_workers` | Integer 1–1024, default 1 |
| `limits.task_timeout_seconds` | Positive integer, default 120; includes startup |
| `limits.job_timeout_seconds` | Positive integer, default 600; includes queuing |
| `limits.max_retries` | Integer 0–10, default 0; additional attempts after initial execution |
| `network` | `disabled` (default) or `enabled` (requires controller permission) |

Unknown fields, duplicate IDs, non-finite numeric values, invalid inputs and policy violations are rejected. Commands execute from `/workspace`. The worker gets source at `/workspace`, a single JSON input at `/input/input.json` (both read-only), a writable `/output`, and bounded `/tmp`. `NUCUBE_ATTEMPT` is the one-based attempt number. Source code should write all retained results into `/output`. Worker environments do not inherit controller credentials or shell variables.

Inputs and source are snapshotted at submission. Symlinks, hardlinks and special files are rejected. Hidden files under the supplied source directory are included: supply a small dedicated source directory, not your home or entire repository. No ignore-file interpretation or dependency installation is performed. Package dependencies into an operator-approved image ahead of time.

## Controller policy

[`nucube.example.yaml`](../nucube.example.yaml) lists all configuration defaults. Configuration is YAML, validated independently of the manifest. A request cannot enable disallowed networking, select another image, increase retry/duration ceilings, or exceed individual worker capacity. Source + inputs share the snapshot byte/file budget. Output limits apply per attempt at collection; log limits apply per container. See security limitations for raw disk consumption.

For reproducible runtimes, set an image digest in both `allowed_images` and the manifest, and explicitly pull it. Mutable tags are convenient for the demo but do not freeze runtime image contents. Snapshot hashes and input bytes cannot protect against a mutable image tag changing before launch.

## API

Interactive schema at `http://127.0.0.1:8765/docs`; calls from browser origins are disabled. HTTP paths: `POST /jobs`, `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `GET /jobs/{id}/logs/{task}`, `GET /jobs/{id}/artifacts`, `GET /jobs/{id}/artifact`.

Submission uses `{manifest, source_files, inputs, idempotency_key}`. `source_files` maps relative names to base64 bytes; `inputs` maps task IDs to base64 JSON bytes. The local client builds this from YAML. Stable errors use `{error: {code, message}}`; examples include `RESOURCE_LIMIT`, `POLICY_LIMIT`, `IMAGE_DENIED`, `NETWORK_DENIED`, `IDEMPOTENCY_CONFLICT`, `UNSAFE_PATH`, `ARTIFACT_LIMIT`, `NOT_FOUND` and `VALIDATION_ERROR`.

Lists are paginated. Job inspection includes up to 100 tasks, each with bounded attempt metadata, and omits artifact lists; use the artifact endpoint for those. `task_offset`/`task_limit` page tasks. Artifact reads return up to 64 KiB base64 bytes with `offset`, `total_bytes`, `eof` and `untrusted`. Logs are bounded by controller policy and may be truncated/rotated; they are not a complete audit stream.
