"""Runtime provenance helpers.

This module gathers lightweight metadata needed to reproduce a run from
the on-disk artifacts. All collectors must be exception-safe: failures
should return ``None`` values instead of raising.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable, Sequence

_DEFAULT_PACKAGE_DISTS: tuple[str, ...] = (
    "numpy",
    "pandas",
    "pyarrow",
    "scipy",
    "numba",
    "pydantic",
    "ruamel.yaml",
)


def _utc_timestamp_iso() -> str:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    return stamp.replace("+00:00", "Z")


def _safe_package_version(dist_name: str) -> str | None:
    try:
        return metadata.version(dist_name)
    except metadata.PackageNotFoundError:
        return None
    except Exception:
        return None


def _safe_git_commit(repo_root: Path | None = None) -> str | None:
    root = repo_root
    if root is None:
        root = Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
        ).strip()
    except Exception:
        return None
    return commit or None


def _safe_sha256(
    path: Path,
    *,
    max_bytes: int | None = None,
    chunk_bytes: int = 1024 * 1024,
) -> str | None:
    try:
        size_bytes = path.stat().st_size
    except Exception:
        return None
    if max_bytes is not None and size_bytes > max_bytes:
        return None
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(chunk_bytes), b""):
                hasher.update(chunk)
    except Exception:
        return None
    return hasher.hexdigest()


def gather_runtime_provenance(
    *,
    external_files: Iterable[str | Path | None] = (),
    package_dists: Sequence[str] | None = None,
    max_external_file_bytes: int = 50 * 1024 * 1024,
) -> dict[str, Any]:
    """Return a JSON-serialisable runtime provenance snapshot."""

    cwd = None
    try:
        cwd = str(Path.cwd())
    except Exception:
        cwd = None

    argv = None
    try:
        argv = list(sys.argv)
    except Exception:
        argv = None

    python_version = None
    python_executable = None
    try:
        python_version = platform.python_version()
    except Exception:
        python_version = None
    try:
        python_executable = sys.executable
    except Exception:
        python_executable = None

    platform_payload: dict[str, Any] = {}
    try:
        platform_payload["system"] = platform.system()
    except Exception:
        platform_payload["system"] = None
    try:
        platform_payload["release"] = platform.release()
    except Exception:
        platform_payload["release"] = None
    try:
        platform_payload["version"] = platform.version()
    except Exception:
        platform_payload["version"] = None
    try:
        platform_payload["machine"] = platform.machine()
    except Exception:
        platform_payload["machine"] = None
    try:
        platform_payload["processor"] = platform.processor()
    except Exception:
        platform_payload["processor"] = None

    packages: dict[str, str | None] = {}
    for dist in package_dists or _DEFAULT_PACKAGE_DISTS:
        packages[dist] = _safe_package_version(dist)

    external_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in external_files:
        if not item:
            continue
        try:
            path = item if isinstance(item, Path) else Path(str(item)).expanduser()
        except Exception:
            external_rows.append(
                {
                    "path": str(item),
                    "exists": None,
                    "size_bytes": None,
                    "sha256": None,
                }
            )
            continue
        try:
            path_resolved = path.resolve()
        except Exception:
            path_resolved = path
        key = str(path_resolved)
        if key in seen:
            continue
        seen.add(key)

        exists = None
        size_bytes = None
        sha256 = None
        try:
            exists = path_resolved.exists()
        except Exception:
            exists = None
        if exists:
            try:
                size_bytes = path_resolved.stat().st_size
            except Exception:
                size_bytes = None
            sha256 = _safe_sha256(
                path_resolved,
                max_bytes=max_external_file_bytes,
            )

        external_rows.append(
            {
                "path": str(path_resolved),
                "exists": exists,
                "size_bytes": size_bytes,
                "sha256": sha256,
            }
        )

    return {
        "timestamp_utc": _utc_timestamp_iso(),
        "cwd": cwd,
        "argv": argv,
        "python": {
            "version": python_version,
            "executable": python_executable,
        },
        "platform": platform_payload,
        "packages": packages,
        "git_commit": _safe_git_commit(),
        "external_files": external_rows,
    }


__all__ = ["gather_runtime_provenance"]
