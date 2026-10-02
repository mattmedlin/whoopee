"""Run against nucube serve. No paid services or model keys required."""

import argparse
import json
import time
from pathlib import Path

from nucube.client import Client, bundle
from nucube.controller.service import TERMINAL


def run(client: Client, workers: int) -> dict:
    payload = bundle(Path(__file__).parent / "cpu" / "job.yaml")
    payload.manifest.resources.max_workers = workers
    payload.manifest.name = f"benchmark-{workers}-workers"
    start = time.perf_counter()
    submitted = client.request("POST", "/jobs", json=payload.model_dump())
    jid = submitted["id"]
    while True:
        job = client.request("GET", f"/jobs/{jid}")
        if job["status"] in TERMINAL:
            break
        time.sleep(0.1)
    wall = time.perf_counter() - start
    if job["status"] != "succeeded":
        raise RuntimeError(json.dumps(job, indent=2))
    files = client.request("GET", f"/jobs/{jid}/artifacts")["items"]
    hashes = {f"{f['task_id']}/{f['path']}": f["sha256"] for f in files}
    attempts = [a for t in job["tasks"] for a in t["attempts"]]
    return {
        "job_id": jid,
        "worker_count": workers,
        "wall_seconds": round(wall, 3),
        "startup_overhead_seconds_sum": round(sum(a["startup_seconds"] or 0 for a in attempts), 3),
        "allocated_cpu_seconds": round(job["allocated_cpu_seconds"], 3),
        "hashes": hashes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.workers < 2:
        parser.error("parallel worker count must be at least 2")
    client = Client()
    serial = run(client, 1)
    parallel = run(client, args.workers)
    if serial["hashes"] != parallel["hashes"]:
        raise RuntimeError("Serial/parallel output hashes differ")
    result = {
        "serial": serial,
        "parallel": parallel,
        "hashes_match": True,
        "speedup": round(serial["wall_seconds"] / parallel["wall_seconds"], 3),
        "notes": "One local run, pre-pulled image. Startup sum is create-to-start time across "
        "attempts, not additive wall overhead. Allocated CPU-seconds count reserved "
        "CPU from launch intent to exit, not actual CPU usage. Small jobs, startup, "
        "CPU contention and I/O can make parallel execution slower.",
    }
    print(json.dumps(result, indent=2))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
