# Dependency verification

The implementation checked these primary sources before selecting APIs:

- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/): controller scheduler startup/shutdown through the application lifespan.
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/): validation with forbidden extra fields and constrained values.
- [Typer tutorial](https://typer.tiangolo.com/tutorial/): typed commands and options.
- [Docker SDK containers](https://docker-py.readthedocs.io/en/stable/containers.html): create, inspect, logs, resource controls, mounts and removal.
- [Docker container run reference](https://docs.docker.com/reference/cli/docker/container/run/): isolation and resource-control semantics.
- [Official Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk): FastMCP, stdio, tools and structured output.
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/): universal lockfile and locked installs.

`uv.lock` records exact resolved versions and hashes for transitive dependencies. Initial resolution selected FastAPI 0.142.2, Pydantic 2.13.5, Typer 0.27.2, Docker SDK 7.2.0, MCP 1.30.0, Uvicorn 0.54.0 and httpx 0.28.1. The MCP dependency is constrained to major version 1 to avoid silently adopting a new SDK API. Verification uses Python 3.13.1 locally; CI covers Python 3.12 and 3.13.

Do not hand-edit the lockfile. Run `uv lock` after changing dependency constraints and verify with `uv sync --locked`, lint, type checking and tests. Nothing is automatically installed inside workers; the controller dependency lock does not lock worker runtime images. Pin approved image digests for reproducible execution.
