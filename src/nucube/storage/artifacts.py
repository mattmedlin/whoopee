import base64
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath

from nucube.errors import NucubeError


def safe_parts(name: str) -> tuple[str, ...]:
    p = PurePosixPath(name)
    if (
        not name
        or p.is_absolute()
        or "\\" in name
        or "\0" in name
        or any(x in ("", ".", "..") for x in name.split("/"))
    ):
        raise NucubeError("UNSAFE_PATH", "Paths must be relative, without traversal")
    return p.parts


def read_safe(root: Path, name: str, limit: int) -> bytes:
    """Walk with dir fds and O_NOFOLLOW; do not follow even intermediate symlinks."""
    parts = safe_parts(name)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        target = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(target, "rb") as f:
            s = os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
                raise NucubeError("UNSAFE_PATH", "Only regular, non-hardlinked files are allowed")
            data = f.read(limit + 1)
            if len(data) > limit:
                raise NucubeError("ARTIFACT_LIMIT", "File exceeds configured byte limit")
            return data
    except OSError as exc:
        raise NucubeError("UNSAFE_PATH", "File missing or unsafe") from exc
    finally:
        os.close(fd)


def tree(root: Path, byte_limit: int, file_limit: int) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    remaining = byte_limit
    entries = 0

    def walk_error(exc: OSError) -> None:
        raise NucubeError("UNSAFE_PATH", "Cannot traverse artifact directory") from exc

    for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        for name in dirs + names:
            entries += 1
            if entries > file_limit:
                raise NucubeError("ARTIFACT_LIMIT", "Too many filesystem entries")
            if (Path(directory) / name).is_symlink():
                raise NucubeError("UNSAFE_PATH", "Symlinks are not allowed")
        for name in sorted(names):
            rel = (Path(directory) / name).relative_to(root).as_posix()
            data = read_safe(root, rel, remaining)
            remaining -= len(data)
            files[rel] = data
    return files


def atomic_json(path: Path, value: object) -> None:
    temp = path.with_suffix(".tmp")
    with temp.open("w") as f:
        json.dump(value, f, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def decode_files(files: dict[str, str], byte_limit: int, file_limit: int) -> dict[str, bytes]:
    if len(files) > file_limit:
        raise NucubeError("ARTIFACT_LIMIT", "Too many snapshot files")
    result = {}
    remaining = byte_limit
    for name, encoded in files.items():
        safe_parts(name)
        if len(encoded) > (remaining + 2) // 3 * 4:
            raise NucubeError("ARTIFACT_LIMIT", "Snapshot exceeds configured limit")
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise NucubeError("INVALID_INPUT", "Invalid base64 file") from exc
        remaining -= len(data)
        if remaining < 0:
            raise NucubeError("ARTIFACT_LIMIT", "Snapshot exceeds configured limit")
        result[name] = data
    # Reject file/directory collisions before writing anything.
    for name in result:
        if any(str(p) in result for p in PurePosixPath(name).parents if str(p) != "."):
            raise NucubeError("UNSAFE_PATH", "Conflicting snapshot paths")
    return result


def manifest_for(files: dict[str, bytes]) -> list[dict]:
    return [
        {"path": k, "size": len(v), "sha256": hashlib.sha256(v).hexdigest()}
        for k, v in sorted(files.items())
    ]
