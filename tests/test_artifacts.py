import os

import pytest

from nucube.client import bundle
from nucube.errors import NucubeError
from nucube.storage.artifacts import read_safe, safe_parts, tree


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "a/../b", "a//b", "a/./b", "a\\b", ""])
def test_traversal(path):
    with pytest.raises(NucubeError):
        safe_parts(path)


def test_symlinks_and_hardlinks(tmp_path):
    (tmp_path / "good").write_text("safe")
    (tmp_path / "link").symlink_to(tmp_path / "good")
    with pytest.raises(NucubeError):
        read_safe(tmp_path, "link", 100)
    with pytest.raises(NucubeError):
        tree(tmp_path, 100, 100)
    (tmp_path / "link").unlink()
    os.link(tmp_path / "good", tmp_path / "hard")
    with pytest.raises(NucubeError):
        read_safe(tmp_path, "hard", 100)


def test_directory_link_and_fifo(tmp_path):
    (tmp_path / "link").symlink_to("/tmp", target_is_directory=True)
    with pytest.raises(NucubeError):
        read_safe(tmp_path, "link/x", 100)
    os.mkfifo(tmp_path / "fifo")
    with pytest.raises(NucubeError):
        read_safe(tmp_path, "fifo", 100)


def test_limits(tmp_path):
    (tmp_path / "large").write_bytes(b"x" * 101)
    with pytest.raises(NucubeError):
        tree(tmp_path, 100, 100)
    with pytest.raises(NucubeError):
        tree(tmp_path, 1000, 0)


def test_example_snapshot():
    from pathlib import Path

    req = bundle(Path("examples/cpu/job.yaml"))
    assert set(req.inputs) == {f"batch-{n:03}" for n in range(1, 5)}
    assert "analyze.py" in req.source_files
