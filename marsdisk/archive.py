"""CLI entry point for post-run archiving."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .io import archive as archive_mod


def _env_flag(name: str) -> Optional[bool]:
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if value in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return None


def _load_run_config(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "run_config.json"
    if not path.exists():
        raise FileNotFoundError(f"run_config.json not found in {run_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_archive_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    archive_payload = {}
    io_payload = payload.get("io") or {}
    archive_payload = io_payload.get("archive") or {}
    if archive_payload:
        return archive_payload
    config_payload = payload.get("config") or {}
    archive_payload = (config_payload.get("io") or {}).get("archive") or {}
    return archive_payload


def _build_settings(
    archive_payload: Dict[str, Any],
    *,
    overrides: Dict[str, Any],
) -> archive_mod.ArchiveSettings:
    data = dict(archive_payload)
    data.update(overrides)
    if not data.get("dir") and data.get("dir_resolved"):
        data["dir"] = data.get("dir_resolved")
    return archive_mod.ArchiveSettings(
        enabled=bool(data.get("enabled", False)),
        dir=Path(data["dir"]) if data.get("dir") else None,
        mode=str(data.get("mode", "copy") or "copy").lower(),
        trigger=str(data.get("trigger", "post_finalize") or "post_finalize").lower(),
        merge_target=str(data.get("merge_target", "external") or "external").lower(),
        verify=bool(data.get("verify", True)),
        verify_level=str(data.get("verify_level", "standard_plus") or "standard_plus").lower(),
        keep_local=str(data.get("keep_local", "metadata") or "metadata").lower(),
        record_volume_info=bool(data.get("record_volume_info", True)),
        warn_slow_mb_s=data.get("warn_slow_mb_s", 40.0),
        warn_slow_min_gb=float(data.get("warn_slow_min_gb", 5.0)),
        min_free_gb=data.get("min_free_gb"),
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True, help="Run directory to archive")
    ap.add_argument("--archive-dir", type=Path, default=None, help="Override archive root")
    ap.add_argument(
        "--verify-level",
        choices=["standard", "standard_plus", "strict"],
        default=None,
        help="Override verification level",
    )
    ap.add_argument(
        "--keep-local",
        choices=["none", "metadata", "all"],
        default=None,
        help="Override local retention policy",
    )
    ap.add_argument(
        "--no-verify",
        action="store_true",
        help="Disable archive verification",
    )
    ap.add_argument(
        "--resume",
        "--archive-resume",
        action="store_true",
        help="Resume from a previous incomplete archive attempt",
    )
    args = ap.parse_args(argv)

    io_archive_flag = _env_flag("IO_ARCHIVE")
    if io_archive_flag is False:
        print("[archive] IO_ARCHIVE=off, skipping")
        return 0

    run_dir = args.run_dir.resolve()
    if args.resume:
        incomplete_marker = run_dir / "INCOMPLETE"
        if incomplete_marker.exists():
            try:
                incomplete_marker.unlink()
            except Exception:
                pass
    try:
        payload = _load_run_config(run_dir)
    except Exception as exc:
        print(f"[archive] failed to load run_config.json: {exc}", file=sys.stderr)
        return 2

    archive_payload = _extract_archive_payload(payload)
    if not archive_payload:
        print("[archive] no archive configuration found; skipping")
        return 0

    overrides: Dict[str, Any] = {}
    if args.archive_dir is not None:
        overrides["dir"] = str(args.archive_dir)
    if args.verify_level is not None:
        overrides["verify_level"] = args.verify_level
    if args.keep_local is not None:
        overrides["keep_local"] = args.keep_local
    if args.no_verify:
        overrides["verify"] = False

    settings = _build_settings(archive_payload, overrides=overrides)
    if not settings.enabled:
        print("[archive] disabled in config; skipping")
        return 0
    if settings.dir is None:
        print("[archive] archive dir is not configured", file=sys.stderr)
        return 2

    result = archive_mod.archive_run(
        run_dir,
        archive_root=Path(settings.dir),
        settings=settings,
    )
    if not result.success:
        print(f"[archive] failed: {'; '.join(result.errors)}", file=sys.stderr)
        return 2
    print(f"[archive] done: {result.dest_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
