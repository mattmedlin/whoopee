"""Opt-in real Engine acceptance tests: NUCUBE_DOCKER_TESTS=1 pytest -m docker."""

import base64
import os
import time
from unittest.mock import Mock

import pytest

from nucube.backends.base import Launch
from nucube.backends.docker import PREFIX, DockerBackend
from nucube.controller.reaper import reap
from nucube.controller.service import TERMINAL, Service, owner_id
from nucube.errors import NucubeError
from nucube.models.schema import Config

from .conftest import submission


@pytest.fixture
def real(tmp_path):
    if os.environ.get("NUCUBE_DOCKER_TESTS") != "1":
        pytest.skip("set NUCUBE_DOCKER_TESTS=1 to enable real Docker tests")
    config = Config(storage=tmp_path, retry_backoff_seconds=0, poll_seconds=0.1)
    backend = DockerBackend(config, owner_id(config))
    service = Service(config, backend)
    yield service
    for resource in backend.managed():
        backend.cleanup(resource["handle"])
    service.close()


def code_request(code, tasks=1, **kwargs):
    req = submission(tasks, **kwargs)
    req.source_files = {"main.py": base64.b64encode(code.encode()).decode()}
    return req


def wait(service, jid, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        service.tick()
        job = service.get(jid)
        if job["status"] in TERMINAL:
            return job
        time.sleep(0.1)
    pytest.fail(f"Job did not complete: {service.get(jid)}")


@pytest.mark.docker
def test_real_success_isolation_cleanup(real):
    code = """import os, json, socket
from pathlib import Path
assert os.getuid() != 0
assert not Path('/var/run/docker.sock').exists()
assert not Path('/sys/class/net/eth0').exists()
for path in ['/workspace/forbidden', '/input/forbidden', '/forbidden']:
    try:
        Path(path).write_text('bad')
    except OSError:
        pass
    else:
        raise AssertionError(path)
Path('/output/result.json').write_text(json.dumps({'answer': 42}))
print('worker succeeded')
"""
    jid = real.submit(code_request(code))["id"]
    real.tick()
    resources = real.backend.managed()
    c = real.backend.client.containers.get(resources[0]["handle"])
    host = c.attrs["HostConfig"]
    assert host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"]
    assert host["NetworkMode"] == "none"
    assert host["NanoCpus"] == 1000000000
    assert host["Memory"] == 512 * 1024 * 1024
    assert host["PidsLimit"] == 128
    job = wait(real, jid)
    assert job["status"] == "succeeded", (job, real.logs(jid, "task-0"))
    data = real.read_artifact(jid, "task-0", 1, "result.json")
    assert b"42" in base64.b64decode(data["data"])
    assert real.logs(jid, "task-0")["text"] == "worker succeeded\n"
    assert not real.backend.managed()


@pytest.mark.docker
def test_real_retry_and_restart(real):
    req = code_request(
        "import os,sys\nfrom pathlib import Path\n"
        "Path('/output/attempt.txt').write_text(os.environ['NUCUBE_ATTEMPT'])\n"
        "sys.exit(75 if os.environ['NUCUBE_ATTEMPT'] == '1' else 0)\n",
        limits={"max_retries": 1},
    )
    jid = real.submit(req)["id"]
    real.tick()
    real.close()
    resumed = Service(real.config, real.backend)
    try:
        job = wait(resumed, jid)
        assert job["status"] == "succeeded", job
        assert [a["exit_code"] for a in job["tasks"][0]["attempts"]] == [75, 0]
        assert len(resumed.artifacts(jid)["items"]) == 2
    finally:
        resumed.close()


@pytest.mark.docker
@pytest.mark.parametrize("operation", ["task_timeout", "job_timeout", "cancel"])
def test_real_termination(real, operation):
    limits = {
        "task_timeout_seconds": 1 if operation == "task_timeout" else 30,
        "job_timeout_seconds": 1 if operation == "job_timeout" else 60,
    }
    jid = real.submit(code_request("import time\ntime.sleep(60)", 2, limits=limits))["id"]
    real.tick()
    if operation == "cancel":
        real.cancel(jid)
    job = wait(real, jid, 10)
    assert job["status"] == ("cancelled" if operation == "cancel" else "timed_out")
    assert not real.backend.managed()


@pytest.mark.docker
def test_real_artifact_escape(real):
    jid = real.submit(
        code_request("from pathlib import Path\nPath('/output/escape').symlink_to('/etc/passwd')")
    )["id"]
    job = wait(real, jid)
    assert job["status"] == "failed"
    assert job["tasks"][0]["attempts"][0]["error"] == "UNSAFE_PATH"


@pytest.mark.docker
def test_real_reaper_preserves_unrelated(real):
    unrelated = real.backend.client.containers.create("python:3.12-slim", ["true"])
    try:
        jid = real.submit(code_request("import time\ntime.sleep(60)"))["id"]
        real.tick()
        assert reap(real.backend, time.time() + 1000)["removed"]
        unrelated.reload()
        assert unrelated.status == "created"
        job = wait(real, jid)
        assert job["status"] == "failed"
    finally:
        unrelated.remove(force=True)


def test_ownership_checks_before_deletion(tmp_path):
    backend = DockerBackend.__new__(DockerBackend)
    backend.config = Config(storage=tmp_path)
    backend.owner = "our-owner"
    backend.client = Mock()
    c = backend.client.containers.get.return_value
    c.labels = {PREFIX + "managed": "v1", PREFIX + "owner": "someone-else"}
    with pytest.raises(NucubeError):
        backend.cleanup("unrelated")
    c.remove.assert_not_called()


def test_docker_launch_flags(tmp_path):
    backend = DockerBackend.__new__(DockerBackend)
    backend.config = Config(storage=tmp_path)
    backend.owner = "test-owner"
    backend.client = Mock()
    spec = Launch(
        "handle",
        "job",
        "task",
        1,
        tmp_path / "source",
        tmp_path / "input",
        tmp_path / "output",
        time.time() + 60,
        submission().manifest,
    )
    backend.launch(spec)
    kwargs = backend.client.containers.create.call_args.kwargs
    assert kwargs["network_mode"] == "none"
    assert kwargs["security_opt"] == ["no-new-privileges:true"]
    assert kwargs["memswap_limit"] == kwargs["mem_limit"]
    assert kwargs["entrypoint"] == []
    assert len(kwargs["volumes"]) == 3
    assert "noexec" in kwargs["tmpfs"]["/tmp"]
