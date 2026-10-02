# Local verification

Verified on October 1–2, 2026: macOS ARM64, Python 3.13.1, Docker Desktop Engine 24.0.6. The Docker VM reported 10 CPUs and 8,225,546,240 bytes memory. Controller allocation policy was 4 workers, 4 CPU and 2048 MiB memory, with a 0.1-second scheduler interval. Runtime: `python:3.12-slim`, pre-pulled at digest `sha256:eeb8088e67610b37583880c7627e3931f087cba55a35810819e34a398f624a47`.

## Checks

- Ruff lint and formatting: passed.
- mypy: passed on 21 source files.
- `uv lock --check --offline`: passed; 58 packages resolved.
- Full pytest suite with `NUCUBE_DOCKER_TESTS=1`: **51 passed**, including 8 Docker/transport cases.
- One upstream Starlette TestClient deprecation warning about httpx remains; it did not affect test results.
- CI is configured for Python 3.12 and 3.13 on Linux; remote CI has not been run or published.

Operational coverage includes artifact retrieval, non-root/read-only/resource/network settings, bounded classified retries and backoff, task/job deadlines, active/queued cancellation, CPU/memory/concurrency admission, policy rejection, idempotency conflicts, restart reconciliation, missing workers, uncertain launches, failed cleanup, durable cancellation intent, independent expiry cleanup, preservation of an unrelated container, traversal/symlink/hardlink/FIFO rejection, immutable snapshots and retention. The final transport test invokes the Typer CLI, HTTP controller, Docker worker, and official MCP stdio client, including structured artifact reads and cross-interface idempotency.

## Benchmark

Four independent batches, eight PBKDF2-HMAC-SHA256 inputs per batch, 500,000 iterations per input. Each task requests 1 CPU and 128 MiB. Serial and parallel use identical snapshotted source/input bytes. The final recorded run occurred after acceptance tests finished; the machine was not otherwise controlled for background load.

| Maximum concurrent workers | Wall seconds | Sum of startup seconds | Allocated CPU-seconds |
| --- | ---: | ---: | ---: |
| 1 | 11.289 | 8.131 | 10.814 |
| 2 | 7.616 | 6.431 | 9.063 |

**All four output hashes matched.** Observed wall-time ratio: 1.482× for this single local run. This is not a general performance guarantee or a controlled performance study. [Raw results, IDs and hashes](benchmark-results.json) are retained.

Wall time includes submission, queueing, startup, execution, collection and polling. Startup is launch-intent to Docker StartedAt, summed across attempts, not an additive portion of wall time when attempts overlap. Allocated CPU-seconds include reserved CPU during startup and execution; they do not measure actual CPU usage.

Container startup dominates this small demonstration. Parallel execution can be slower for tiny tasks, contended CPU/memory, I/O-heavy jobs, or expensive container startup. nucube adds no physical compute capacity locally. Use longer batches to amortize startup and repeat measurements on your workload before choosing concurrency.

To reproduce, start `uv run nucube serve`, then:

```bash
uv run python examples/benchmark.py --workers 2 --output /tmp/nucube-benchmark.json
```

The script fails if any job fails or serial/parallel output hashes differ. Default polling configuration is 0.5 seconds, so timings with the shipped defaults may differ from the recorded 0.1-second validation configuration.
