import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def tools_available():
    params = StdioServerParameters(
        command=str(Path(sys.executable).with_name("nucube")), args=["mcp"]
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        return {t.name for t in tools.tools}


def test_official_mcp_stdio_discovery():
    assert asyncio.run(tools_available()) == {
        "submit_job",
        "get_job",
        "list_jobs",
        "get_task_logs",
        "list_artifacts",
        "read_artifact",
        "cancel_job",
    }


@pytest.mark.docker
def test_cli_http_mcp_end_to_end(tmp_path):
    if os.environ.get("NUCUBE_DOCKER_TESTS") != "1":
        pytest.skip("set NUCUBE_DOCKER_TESTS=1")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = tmp_path / "config.yaml"
    config.write_text(f"storage: {tmp_path / 'state'}\npoll_seconds: 0.1\n")
    source = tmp_path / "source"
    source.mkdir()
    source.joinpath("work.py").write_text(
        "from pathlib import Path\nPath('/output/answer.txt').write_text('42')\nprint('done')\n"
    )
    tmp_path.joinpath("input.json").write_text("{}")
    manifest = tmp_path / "job.yaml"
    manifest.write_text("""api_version: nucube/v1
name: transport-test
runtime:
  image: python:3.12-slim
  command: [python, /workspace/work.py]
  source: ./source
tasks:
  - id: one
    input: ./input.json
""")
    env = {**os.environ, "NUCUBE_URL": f"http://127.0.0.1:{port}"}
    binary = str(Path(sys.executable).with_name("nucube"))
    with (tmp_path / "server.log").open("w") as log:
        server = subprocess.Popen(
            [binary, "serve", "--config", str(config), "--port", str(port)],
            stdout=log,
            stderr=log,
            env=env,
        )
        try:
            with httpx.Client(base_url=env["NUCUBE_URL"], trust_env=False) as client:
                for _ in range(100):
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    pytest.fail((tmp_path / "server.log").read_text())
                result = subprocess.run(
                    [binary, "run", str(manifest), "--idempotency-key", "cli"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30,
                    check=True,
                )
                jid = json.loads(result.stdout)["id"]
                for _ in range(100):
                    job = client.get(f"/jobs/{jid}").json()
                    if job["status"] == "succeeded":
                        break
                    time.sleep(0.1)
                assert job["status"] == "succeeded", job

            async def inspect_through_mcp():
                params = StdioServerParameters(command=binary, args=["mcp"], env=env)
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool("get_job", {"job_id": jid})
                        assert not result.isError
                        assert result.structuredContent["status"] == "succeeded"
                        result = await session.call_tool(
                            "read_artifact",
                            {"job_id": jid, "task_id": "one", "attempt": 1, "path": "answer.txt"},
                        )
                        assert result.structuredContent["data"] == "NDI="
                        assert result.structuredContent["untrusted"]
                        duplicate = await session.call_tool(
                            "submit_job", {"manifest_path": str(manifest), "idempotency_key": "cli"}
                        )
                        assert duplicate.structuredContent["id"] == jid
                        assert duplicate.structuredContent["duplicate"]

            asyncio.run(inspect_through_mcp())
        finally:
            server.terminate()
            server.wait(timeout=30)
            from nucube.backends.docker import DockerBackend
            from nucube.controller.service import owner_id
            from nucube.models.schema import load_config

            c = load_config(config)
            backend = DockerBackend(c, owner_id(c))
            for resource in backend.managed():
                backend.cleanup(resource["handle"])
