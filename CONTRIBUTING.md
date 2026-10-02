# Contributing

Use Python 3.12+ and uv. Keep execution, machine provisioning, policy, persistence and API layers separate. Describe behavior changes with meaningful operational tests. Do not add infrastructure adapters or imply capacity provisioning when creating containers.

```bash
uv sync --locked
uv run ruff check src tests examples
uv run ruff format --check src tests examples
uv run mypy src
uv run pytest -q
# A running local Docker Engine and pre-pulled image are required:
docker pull python:3.12-slim
NUCUBE_DOCKER_TESTS=1 uv run pytest -q -m docker
```

Update `pyproject.toml` and `uv.lock` together when changing dependencies. CI checks the lockfile on Python 3.12 and 3.13. Docker tests create isolated temporary storage/ownership IDs and remove their own containers. Avoid printing secrets in logs, tests or issues. Apache-2.0 applies to contributions.
