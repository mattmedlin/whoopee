import base64
import time

import pytest
from fastapi.testclient import TestClient

from nucube.api.app import create_app
from nucube.controller.reaper import reap
from nucube.controller.service import Service
from nucube.errors import NucubeError

from .conftest import submission


def test_vertical_slice_and_retrieval(service):
    with TestClient(create_app(service.config, service, False)) as client:
        response = client.post("/jobs", json=submission().model_dump())
        assert response.status_code == 202
        jid = response.json()["id"]
        service.tick()
        service.backend.complete()
        service.tick()
        job = client.get(f"/jobs/{jid}").json()
        assert job["status"] == "succeeded"
        assert job["allocated_cpu_seconds"] > 0
        assert not service.backend.workers
        files = client.get(f"/jobs/{jid}/artifacts").json()
        assert files["items"][0]["path"] == "result.txt"
        artifact = client.get(
            f"/jobs/{jid}/artifact",
            params={"task_id": "task-0", "attempt": 1, "path": "result.txt"},
        ).json()
        assert base64.b64decode(artifact["data"]) == b"answer"
        assert client.get(f"/jobs/{jid}/logs/task-0").json()["untrusted"]


@pytest.mark.parametrize(
    "code,oom,retried", [(75, False, True), (1, False, False), (137, True, False)]
)
def test_retry_classification_and_bound(service, code, oom, retried):
    req = submission(limits={"max_retries": 1})
    jid = service.submit(req)["id"]
    service.tick()
    service.backend.complete(code, oom)
    service.tick()
    job = service.get(jid)
    assert len(job["tasks"][0]["attempts"]) == (2 if retried else 1)
    if retried:
        service.backend.complete(code)
        service.tick()
    assert service.get(jid)["status"] == "failed"
    assert len(service.get(jid)["tasks"][0]["attempts"]) <= 2


def test_backoff(service):
    service.config.retry_backoff_seconds = 100
    jid = service.submit(submission(limits={"max_retries": 1}))["id"]
    service.tick()
    service.backend.complete(75)
    service.tick()
    assert service.get(jid)["tasks"][0]["status"] == "queued"
    assert not service.backend.workers


@pytest.mark.parametrize("job_deadline", [True, False])
def test_deadlines(service, job_deadline):
    jid = service.submit(submission(2))["id"]
    service.tick()
    job = service.get(jid)
    if job_deadline:
        job["created_at"] -= 1000
    else:
        job["tasks"][0]["attempts"][0]["created_at"] -= 1000
    service.store.save(job)
    service.tick()
    if not job_deadline:
        service.backend.complete()
        service.tick()
    assert service.get(jid)["status"] == "timed_out"
    assert not service.backend.workers


def test_cancel_preserves_completed(service):
    jid = service.submit(submission(3))["id"]
    service.tick()
    service.backend.complete()
    service.tick()
    service.cancel(jid)
    job = service.get(jid)
    assert job["status"] == "cancelled"
    assert [t["status"] for t in job["tasks"]] == ["succeeded", "cancelled", "cancelled"]
    assert service.artifacts(jid)["items"]
    assert not service.backend.workers


def test_capacity_and_global_concurrency(service):
    service.config.total_cpu = 2
    service.config.total_memory_mb = 768
    for _ in range(3):
        service.submit(submission(4, resources={"max_workers": 4, "memory_mb_per_worker": 512}))
    service.tick()
    assert len(service.backend.workers) == 1  # memory is tighter than CPU
    service.config.total_memory_mb = 4096
    service.tick()
    assert len(service.backend.workers) == 2
    service.config.max_workers = 1
    service.backend.complete()
    service.tick()
    assert len(service.backend.workers) == 1


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"resources": {"cpu_per_worker": 5}}, "RESOURCE_LIMIT"),
        ({"network": "enabled"}, "NETWORK_DENIED"),
        ({"limits": {"max_retries": 3}}, "POLICY_LIMIT"),
        ({"runtime": {"image": "bad", "command": ["hi"], "source": "."}}, "IMAGE_DENIED"),
    ],
)
def test_policy(service, overrides, code):
    with pytest.raises(NucubeError) as e:
        service.submit(submission(**overrides))
    assert e.value.code == code


def test_idempotency(service):
    req = submission()
    req.idempotency_key = "key"
    first = service.submit(req)
    assert service.submit(req)["id"] == first["id"]
    req.manifest.name = "changed"
    with pytest.raises(NucubeError, match="different content"):
        service.submit(req)


def test_restart_reconciles_running_and_missing(service):
    jid = service.submit(submission(limits={"max_retries": 1}))["id"]
    service.tick()
    service.store.db.close()
    service._lease.close()
    restarted = Service(service.config, service.backend)
    try:
        restarted.tick()
        assert len(restarted.backend.workers) == 1
        assert len(restarted.get(jid)["tasks"][0]["attempts"]) == 1
        restarted.backend.workers.clear()
        restarted.tick()
        assert len(restarted.get(jid)["tasks"][0]["attempts"]) == 2
        restarted.backend.complete()
        restarted.tick()
        assert restarted.get(jid)["status"] == "succeeded"
    finally:
        restarted.close()


def test_reaper(service):
    service.submit(submission())
    service.tick()
    assert not reap(service.backend)["removed"]
    assert len(reap(service.backend, time.time() + 1000)["removed"]) == 1


def test_single_controller(service):
    with pytest.raises(NucubeError, match="one controller"):
        Service(service.config, service.backend)


def test_api_rejects_browser_and_bad_fields(service):
    with TestClient(create_app(service.config, service, False)) as client:
        assert client.post("/jobs", headers={"Origin": "https://evil.example"}).status_code == 403
        r = client.post("/jobs", json={"bad": True})
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
        assert client.get("/jobs/nope").status_code == 404


def test_retention_keeps_records(service):
    jid = service.submit(submission())["id"]
    service.tick()
    service.backend.complete()
    service.tick()
    job = service.get(jid)
    job["finished_at"] -= 8 * 86400
    service.store.save(job)
    service.retention()
    assert not service.root(jid).exists()
    assert service.get(jid)["artifacts_expired"]


def test_snapshot_is_immutable_after_submission(service):
    req = submission()
    jid = service.submit(req)["id"]
    req.source_files["main.py"] = base64.b64encode(b"changed").decode()
    req.inputs["task-0"] = base64.b64encode(b'{"changed":true}').decode()
    service.tick()
    spec = next(iter(service.backend.specs.values()))
    assert spec.source.joinpath("main.py").read_bytes() == b"print('hello')"
    assert spec.input.read_bytes() == b"{}"
    assert service.get(jid)["status"] == "running"


def test_cleanup_crash_does_not_repeat_completed_work(service, monkeypatch):
    jid = service.submit(submission())["id"]
    service.tick()
    service.backend.complete()
    original = service.backend.cleanup

    def failed_cleanup(handle):
        raise RuntimeError("Engine temporarily unavailable")

    monkeypatch.setattr(service.backend, "cleanup", failed_cleanup)
    with pytest.raises(RuntimeError):
        service.tick()
    assert service.get(jid)["tasks"][0]["status"] == "succeeded"
    monkeypatch.setattr(service.backend, "cleanup", original)
    service.tick()
    assert service.get(jid)["status"] == "succeeded"
    assert len(service.get(jid)["tasks"][0]["attempts"]) == 1
    assert not service.backend.workers


def test_uncertain_launch_reserves_capacity(service, monkeypatch):
    original = service.backend.launch

    def launch_then_connection_loss(spec):
        original(spec)
        raise TimeoutError("Response lost after creation")

    monkeypatch.setattr(service.backend, "launch", launch_then_connection_loss)
    jid = service.submit(submission())["id"]
    with pytest.raises(TimeoutError):
        service.tick()
    service.tick()  # adopts existing worker, does not call launch again
    assert len(service.backend.workers) == 1
    assert len(service.get(jid)["tasks"][0]["attempts"]) == 1
    service.backend.complete()
    service.tick()
    assert service.get(jid)["status"] == "succeeded"


def test_cancel_intent_survives_stop_failure(service, monkeypatch):
    jid = service.submit(submission(2))["id"]
    service.tick()
    stop = service.backend.stop

    def unavailable(handle):
        raise RuntimeError("Engine temporarily unavailable")

    monkeypatch.setattr(service.backend, "stop", unavailable)
    with pytest.raises(RuntimeError):
        service.cancel(jid)
    assert service.get(jid)["stop_reason"] == "cancelled"
    monkeypatch.setattr(service.backend, "stop", stop)
    service.tick()
    assert service.get(jid)["status"] == "cancelled"
    assert not service.backend.workers


def test_queued_cancel_never_launches(service):
    jid = service.submit(submission())["id"]
    service.cancel(jid)
    service.tick()
    assert not service.backend.specs
    assert service.get(jid)["status"] == "cancelled"


def test_job_inspection_pages_tasks_and_omits_large_artifact_lists(service):
    jid = service.submit(submission(3))["id"]
    result = service.public_job(jid, 1, 1)
    assert result["task_count"] == 3
    assert [t["id"] for t in result["tasks"]] == ["task-1"]
    assert "tasks" not in result["manifest"]
    assert "artifacts" not in result["tasks"][0]


@pytest.mark.parametrize("cpu", [1e-20, 0, float("nan"), float("inf")])
def test_invalid_cpu_cannot_become_an_unlimited_container(cpu):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        submission(resources={"cpu_per_worker": cpu})
