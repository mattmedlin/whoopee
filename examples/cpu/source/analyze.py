"""Deterministic CPU work. Only stdlib; output independent of worker count."""

import hashlib
import json
from pathlib import Path

batch = json.loads(Path("/input/input.json").read_text())
results = []
for item in batch["items"]:
    value = hashlib.pbkdf2_hmac(
        "sha256", str(item).encode(), b"nucube-demo-v1", batch["iterations"]
    ).hex()
    results.append({"item": item, "digest": value})
Path("/output/result.json").write_text(json.dumps(results, sort_keys=True) + "\n")
print(f"Processed {len(results)} items")
