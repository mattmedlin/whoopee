# nucube

**Give it a task. It builds the cluster.**

An open-source agentic compute orchestrator: an existing agent submits executable batch work; ordinary CPU workers execute it without additional AI models.

Status: local MVP. Docker containers share your existing machine's capacity; nucube does **not** provision machines, add capacity, or support cloud or Kubernetes backends. Single controller, trusted local users, independent tasks only.

## Try it locally

Install Python 3.12+, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Docker Engine/Docker Desktop, then:

```bash
uv sync --locked
docker pull python:3.12-slim
uv run nucube doctor
uv run nucube serve
```

In another terminal:

```bash
uv run nucube run examples/cpu/job.yaml --wait
uv run python examples/benchmark.py --workers 2
```

`run` returns a job ID immediately without `--wait`. Source and JSON inputs are snapshotted at submission; each attempt gets its own output directory. The controller enforces image/network policy, CPU/memory/worker budgets, deadlines and bounded retries. Jobs, tasks and attempts persist in SQLite. Containers are removed after completion; outputs remain until configured retention expires.

The official Python MCP SDK exposes `submit_job`, `get_job`, `list_jobs`, `get_task_logs`, `list_artifacts`, `read_artifact` and `cancel_job` through `nucube mcp`. CLI and MCP use the same controller. No model API keys or paid services are needed.

## Read more

- [Quickstart, commands and independent reaper](docs/quickstart.md)
- [Architecture, recovery and orchestration context](docs/architecture.md)
- [Manifest and policy reference](docs/manifest.md)
- [Agent/MCP setup](docs/mcp.md)
- [Security model and limitations](docs/security.md)
- [Local verification and benchmark](docs/verification.md)
- [Dependency documentation and lockfile](docs/dependencies.md)
- [Contributing](CONTRIBUTING.md) and [security reporting](SECURITY.md)

Execution can be **at least once** after failures: retryable work must tolerate repetition. This is user-authorized local execution, not a hostile multi-tenant sandbox. Writable output directories have no live disk quota. Worker wall-clock deadlines require the controller or periodically scheduled reaper. Loopback-only operation has no multi-user authentication. No cloud capacity or dollar-budget enforcement is implemented.

Licensed under [Apache-2.0](LICENSE).
