"""Archive helper utilities for offloading completed runs."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import plistlib
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

import pandas as pd
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

CHUNK_GLOBS = (
    "series/run_chunk_*.parquet",
    "series/psd_hist_chunk_*.parquet",
    "series/diagnostics_chunk_*.parquet",
)

SERIES_MERGED = {
    "run": ("series/run.parquet", "series/run_chunk_*.parquet"),
    "psd_hist": ("series/psd_hist.parquet", "series/psd_hist_chunk_*.parquet"),
    "diagnostics": ("series/diagnostics.parquet", "series/diagnostics_chunk_*.parquet"),
}

METADATA_KEEP = {
    "summary.json",
    "run_config.json",
    "run_card.md",
    "ARCHIVE_DONE",
    "ARCHIVE_SKIPPED",
    "INCOMPLETE",
}


@dataclass(frozen=True)
class ArchiveSettings:
    enabled: bool
    dir: Optional[Path]
    mode: str
    trigger: str
    merge_target: str
    verify: bool
    verify_level: str
    keep_local: str
    record_volume_info: bool
    warn_slow_mb_s: Optional[float]
    warn_slow_min_gb: float
    min_free_gb: Optional[float]


@dataclass(frozen=True)
class ArchiveResult:
    success: bool
    dest_dir: Path
    manifest_path: Optional[Path]
    errors: Sequence[str]


def resolve_archive_dest(archive_root: Path, run_dir: Path) -> Path:
    return archive_root / run_dir.name


def _human_bytes(value: float) -> str:
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for suffix in suffixes:
        if size < 1024.0 or suffix == suffixes[-1]:
            return f"{size:.2f} {suffix}"
        size /= 1024.0
    return f"{size:.2f} TB"


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _hash_dataframe(df: pd.DataFrame) -> str:
    hashed = pd.util.hash_pandas_object(df, index=True).values
    return hashlib.sha256(hashed.tobytes()).hexdigest()


def _parquet_metadata(path: Path) -> Dict[str, int | str]:
    parquet = pq.ParquetFile(path)
    schema_hash = hashlib.sha256(str(parquet.schema_arrow).encode("utf-8")).hexdigest()
    return {
        "row_count": int(parquet.metadata.num_rows),
        "row_group_count": int(parquet.metadata.num_row_groups),
        "schema_hash": schema_hash,
    }


def _parquet_row_group_checksum(path: Path, group_index: int) -> Optional[str]:
    parquet = pq.ParquetFile(path)
    if parquet.metadata.num_row_groups <= 0:
        return None
    group_index = max(0, min(group_index, parquet.metadata.num_row_groups - 1))
    table = parquet.read_row_group(group_index)
    df = table.to_pandas()
    return _hash_dataframe(df)


def _sum_chunk_rows(paths: Sequence[Path]) -> int:
    total = 0
    for path in paths:
        try:
            parquet = pq.ParquetFile(path)
        except Exception as exc:
            logger.warning("Failed to read chunk metadata %s: %s", path, exc)
            continue
        total += int(parquet.metadata.num_rows)
    return total


def _is_chunk(rel_path: Path) -> bool:
    if rel_path.parts and rel_path.parts[0] == "series":
        name = rel_path.name
        return name.startswith(("run_chunk_", "psd_hist_chunk_", "diagnostics_chunk_"))
    return False


def _is_metadata(rel_path: Path) -> bool:
    if rel_path.name in METADATA_KEEP:
        return True
    if rel_path.parts and rel_path.parts[0] == "checks":
        return True
    return False


def _collect_copy_files(run_dir: Path) -> List[Path]:
    files: List[Path] = []
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir)
        if _is_chunk(rel):
            continue
        files.append(path)
    return files


def _collect_hash_targets(run_dir: Path) -> List[Path]:
    targets: List[Path] = []
    for name in ("summary.json", "run_config.json", "run_card.md"):
        path = run_dir / name
        if path.exists():
            targets.append(path)
    checks_dir = run_dir / "checks"
    if checks_dir.exists():
        targets.extend([p for p in checks_dir.glob("*") if p.is_file()])
    for plots_dir in (run_dir / "plots", run_dir / "figures"):
        if plots_dir.exists():
            targets.extend([p for p in plots_dir.rglob("*") if p.is_file()])
    return targets


def _write_marker(path: Path, message: str) -> None:
    try:
        path.write_text(message, encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to write marker %s: %s", path, exc)


def _update_run_card(
    run_card: Path,
    archive_path: Path,
    manifest_path: Optional[Path],
    manifest_hash: Optional[str],
    level: str,
    *,
    volume_info: Optional[Mapping[str, Optional[str]]] = None,
    copy_stats: Optional[Mapping[str, float]] = None,
    slow_warning: Optional[str] = None,
) -> None:
    if not run_card.exists():
        return
    lines = run_card.read_text(encoding="utf-8").splitlines()
    lines.append("")
    lines.append("## Archive")
    lines.append(f"- archive_path: {archive_path}")
    if manifest_path is not None:
        lines.append(f"- archive_manifest: {manifest_path.name}")
    if manifest_hash is not None:
        lines.append(f"- archive_manifest_hash: {manifest_hash}")
    lines.append(f"- archive_verify_level: {level}")
    lines.append(f"- archive_timestamp_unix: {int(time.time())}")
    if copy_stats is not None:
        bytes_total = copy_stats.get("bytes", 0.0)
        seconds = copy_stats.get("seconds", 0.0)
        rate_mb_s = copy_stats.get("rate_mb_s", 0.0)
        lines.append(f"- archive_copy_bytes: {int(bytes_total)}")
        lines.append(f"- archive_copy_seconds: {seconds:.2f}")
        lines.append(f"- archive_copy_rate_mb_s: {rate_mb_s:.2f}")
    if slow_warning:
        lines.append(f"- archive_slow_warning: {slow_warning}")
    if volume_info:
        name = volume_info.get("name")
        uuid = volume_info.get("uuid")
        serial = volume_info.get("serial")
        device = volume_info.get("device")
        mount_point = volume_info.get("mount_point")
        if name:
            lines.append(f"- archive_volume_name: {name}")
        if uuid:
            lines.append(f"- archive_volume_uuid: {uuid}")
        if serial:
            lines.append(f"- archive_volume_serial: {serial}")
        if device:
            lines.append(f"- archive_volume_device: {device}")
        if mount_point:
            lines.append(f"- archive_volume_mount: {mount_point}")
    run_card.write_text("\n".join(lines), encoding="utf-8")


def _check_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        return False
    return os.access(path, os.W_OK)


def _verify_level_settings(level: str) -> str:
    value = str(level or "standard_plus").strip().lower()
    if value not in {"standard", "standard_plus", "strict"}:
        value = "standard_plus"
    return value


def _resolve_mount_point(path: Path) -> Path:
    path = Path(path).resolve()
    if os.name == "nt":
        drive = path.drive
        if drive:
            if drive.endswith("\\"):
                return Path(drive)
            return Path(f"{drive}\\")
        anchor = path.anchor or str(path)
        return Path(anchor)
    current = path
    while True:
        if os.path.ismount(str(current)):
            return current
        if current.parent == current:
            return current
        current = current.parent


def _windows_volume_info(mount_point: Path) -> Dict[str, Optional[str]]:
    info: Dict[str, Optional[str]] = {}
    root = str(mount_point)
    if not root.endswith("\\"):
        root = f"{root}\\"
    try:
        import ctypes
        from ctypes import wintypes

        volume_name_buf = ctypes.create_unicode_buffer(261)
        fs_name_buf = ctypes.create_unicode_buffer(261)
        serial_number = wintypes.DWORD()
        max_component = wintypes.DWORD()
        fs_flags = wintypes.DWORD()
        res = ctypes.windll.kernel32.GetVolumeInformationW(
            wintypes.LPCWSTR(root),
            volume_name_buf,
            len(volume_name_buf),
            ctypes.byref(serial_number),
            ctypes.byref(max_component),
            ctypes.byref(fs_flags),
            fs_name_buf,
            len(fs_name_buf),
        )
        if res:
            info["name"] = volume_name_buf.value or None
            info["serial"] = f"{serial_number.value:08X}"
            info["filesystem"] = fs_name_buf.value or None
        guid_buf = ctypes.create_unicode_buffer(1024)
        res_guid = ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(
            wintypes.LPCWSTR(root),
            guid_buf,
            len(guid_buf),
        )
        if res_guid:
            guid_value = guid_buf.value.rstrip("\\")
            info["uuid"] = guid_value or None
    except Exception as exc:
        logger.debug("windows volume info failed: %s", exc)
    info["device"] = root
    return info


def _mac_volume_info(path: Path) -> Dict[str, Optional[str]]:
    info: Dict[str, Optional[str]] = {}
    try:
        result = subprocess.run(
            ["diskutil", "info", "-plist", str(path)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            return info
        payload = plistlib.loads(result.stdout)
        info["name"] = payload.get("VolumeName")
        info["uuid"] = payload.get("VolumeUUID")
        info["mount_point"] = payload.get("MountPoint")
        device = payload.get("DeviceIdentifier")
        if device:
            if device.startswith("/dev/"):
                info["device"] = device
            else:
                info["device"] = f"/dev/{device}"
        info["filesystem"] = payload.get("FilesystemName") or payload.get("FilesystemType")
    except Exception as exc:
        logger.debug("mac volume info failed: %s", exc)
    return info


def _linux_volume_info(mount_point: Path) -> Dict[str, Optional[str]]:
    info: Dict[str, Optional[str]] = {}
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,MOUNTPOINT,UUID,LABEL"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return info
        payload = json.loads(result.stdout)

        def _find(node: Mapping[str, object]) -> Optional[Mapping[str, object]]:
            if node.get("mountpoint") == str(mount_point):
                return node
            for child in node.get("children", []) or []:
                found = _find(child)
                if found:
                    return found
            return None

        for node in payload.get("blockdevices", []) or []:
            found = _find(node)
            if found:
                info["uuid"] = found.get("uuid")
                info["name"] = found.get("label")
                name = found.get("name")
                if name:
                    if str(name).startswith("/dev/"):
                        info["device"] = str(name)
                    else:
                        info["device"] = f"/dev/{name}"
                break
    except Exception as exc:
        logger.debug("linux volume info failed: %s", exc)
    return info


def _resolve_volume_info(path: Path) -> Dict[str, Optional[str]]:
    mount_point = _resolve_mount_point(path)
    info: Dict[str, Optional[str]] = {"mount_point": str(mount_point)}
    if sys.platform.startswith("win"):
        info.update(_windows_volume_info(mount_point))
    elif sys.platform == "darwin":
        info.update(_mac_volume_info(path))
    else:
        info.update(_linux_volume_info(mount_point))
    return info


def archive_run(
    run_dir: Path,
    *,
    archive_root: Path,
    settings: ArchiveSettings,
) -> ArchiveResult:
    run_dir = Path(run_dir).resolve()
    archive_root = Path(archive_root).resolve()
    dest_dir = resolve_archive_dest(archive_root, run_dir)
    errors: List[str] = []

    if not run_dir.exists():
        errors.append(f"run_dir not found: {run_dir}")
        return ArchiveResult(False, dest_dir, None, errors)

    if os.name == "nt" and not archive_root.is_absolute():
        errors.append("archive_root must be an absolute path on Windows")
        _write_marker(run_dir / "ARCHIVE_SKIPPED", "; ".join(errors))
        return ArchiveResult(False, dest_dir, None, errors)

    if not archive_root.exists() or not archive_root.is_dir():
        errors.append(f"archive_root missing: {archive_root}")
        _write_marker(run_dir / "ARCHIVE_SKIPPED", "; ".join(errors))
        return ArchiveResult(False, dest_dir, None, errors)

    if not _check_writable(dest_dir):
        errors.append(f"archive_root not writable: {archive_root}")
        _write_marker(run_dir / "ARCHIVE_SKIPPED", "; ".join(errors))
        return ArchiveResult(False, dest_dir, None, errors)

    logger.info("archive destination resolved: %s", dest_dir)
    volume_info: Optional[Dict[str, Optional[str]]] = None
    if settings.record_volume_info:
        volume_info = _resolve_volume_info(archive_root)

    copy_files = _collect_copy_files(run_dir)
    copy_bytes = sum(path.stat().st_size for path in copy_files)
    logger.info(
        "archive: %s files, %s to copy", len(copy_files), _human_bytes(copy_bytes)
    )

    if settings.min_free_gb is not None:
        free_bytes = shutil.disk_usage(dest_dir).free
        min_free_bytes = settings.min_free_gb * (1024.0 ** 3)
        if free_bytes < min_free_bytes:
            errors.append(
                f"archive_root free space below min_free_gb ({settings.min_free_gb})"
            )
            _write_marker(run_dir / "ARCHIVE_SKIPPED", "; ".join(errors))
            return ArchiveResult(False, dest_dir, None, errors)

    start_time = time.time()
    for src in copy_files:
        rel = src.relative_to(run_dir)
        dest = dest_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest)
        except Exception as exc:
            errors.append(f"copy failed for {src}: {exc}")
            _write_marker(run_dir / "INCOMPLETE", "; ".join(errors))
            return ArchiveResult(False, dest_dir, None, errors)

    elapsed = time.time() - start_time
    rate_mb_s = 0.0
    if elapsed > 0.0:
        rate_mb_s = copy_bytes / elapsed / (1024.0**2)
    if elapsed > 0.0:
        rate = copy_bytes / elapsed
        logger.info("archive copy finished: %s/s", _human_bytes(rate))
    slow_warning = None
    warn_slow_mb_s = settings.warn_slow_mb_s or 0.0
    warn_slow_min_gb = settings.warn_slow_min_gb
    if warn_slow_mb_s > 0.0 and copy_bytes >= warn_slow_min_gb * (1024.0**3):
        if rate_mb_s > 0.0 and rate_mb_s < warn_slow_mb_s:
            slow_warning = (
                f"throughput {rate_mb_s:.1f} MB/s below threshold {warn_slow_mb_s:.1f} MB/s"
            )
            logger.warning("archive slow device warning: %s", slow_warning)

    manifest_path = dest_dir / "archive_manifest.json"
    verify_level = _verify_level_settings(settings.verify_level)
    manifest = _build_manifest(dest_dir, exclude={"run_card.md", "archive_manifest.json"})
    manifest_hash = _hash_manifest(manifest)
    copy_stats = {
        "bytes": float(copy_bytes),
        "seconds": float(elapsed),
        "rate_mb_s": float(rate_mb_s),
    }
    _update_run_card(
        run_dir / "run_card.md",
        dest_dir,
        manifest_path,
        manifest_hash,
        verify_level,
        volume_info=volume_info,
        copy_stats=copy_stats,
        slow_warning=slow_warning,
    )
    _update_run_card(
        dest_dir / "run_card.md",
        dest_dir,
        manifest_path,
        manifest_hash,
        verify_level,
        volume_info=volume_info,
        copy_stats=copy_stats,
        slow_warning=slow_warning,
    )
    if settings.verify:
        verify_errors = _verify_archive(
            run_dir=run_dir,
            dest_dir=dest_dir,
            verify_level=verify_level,
        )
        errors.extend(verify_errors)
        if errors:
            _write_marker(run_dir / "INCOMPLETE", "; ".join(errors))
            return ArchiveResult(False, dest_dir, None, errors)

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_marker(dest_dir / "ARCHIVE_DONE", "ok")

    if settings.keep_local != "all":
        _cleanup_local(run_dir, settings.keep_local)

    return ArchiveResult(True, dest_dir, manifest_path, [])


def _build_manifest(root: Path, *, exclude: Optional[set[str]] = None) -> Dict[str, object]:
    exclude = exclude or set()
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in exclude:
            continue
        stat = path.stat()
        files.append(
            {
                "path": rel,
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            }
        )
    return {
        "root": str(root),
        "file_count": len(files),
        "files": files,
    }


def _hash_manifest(manifest: Mapping[str, object]) -> str:
    payload = json.dumps(manifest, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _verify_archive(
    *,
    run_dir: Path,
    dest_dir: Path,
    verify_level: str,
) -> List[str]:
    errors: List[str] = []
    level = _verify_level_settings(verify_level)

    if not (dest_dir / "summary.json").exists():
        errors.append("summary.json missing in archive")
    if not (dest_dir / "run_config.json").exists():
        errors.append("run_config.json missing in archive")

    if level in {"standard_plus", "strict"}:
        hash_targets = _collect_hash_targets(run_dir)
        for src in hash_targets:
            rel = src.relative_to(run_dir)
            dest = dest_dir / rel
            if not dest.exists():
                errors.append(f"missing copy for {rel}")
                continue
            try:
                src_hash = _hash_file(src)
                dest_hash = _hash_file(dest)
            except Exception as exc:
                errors.append(f"hash failed for {rel}: {exc}")
                continue
            if src_hash != dest_hash:
                errors.append(f"hash mismatch for {rel}")

        _verify_parquet_sets(run_dir, dest_dir, errors, level)

    if level == "strict":
        for dest in dest_dir.rglob("*"):
            if not dest.is_file():
                continue
            rel = dest.relative_to(dest_dir)
            src = run_dir / rel
            if not src.exists():
                continue
            try:
                if _hash_file(src) != _hash_file(dest):
                    errors.append(f"hash mismatch for {rel}")
            except Exception as exc:
                errors.append(f"hash failed for {rel}: {exc}")

    return errors


def _verify_parquet_sets(
    run_dir: Path,
    dest_dir: Path,
    errors: List[str],
    level: str,
) -> None:
    for name, (merged_rel, chunk_glob) in SERIES_MERGED.items():
        merged_path = dest_dir / merged_rel
        if not merged_path.exists():
            continue
        try:
            meta = _parquet_metadata(merged_path)
        except Exception as exc:
            errors.append(f"parquet metadata failed for {merged_rel}: {exc}")
            continue

        chunk_paths = sorted((run_dir / "series").glob(Path(chunk_glob).name))
        if chunk_paths:
            total_rows = _sum_chunk_rows(chunk_paths)
            if total_rows != meta["row_count"]:
                errors.append(
                    f"{name} row_count mismatch: chunks={total_rows} merged={meta['row_count']}"
                )
            try:
                chunk_parquet = pq.ParquetFile(chunk_paths[0])
                chunk_hash = hashlib.sha256(
                    str(chunk_parquet.schema_arrow).encode("utf-8")
                ).hexdigest()
                if chunk_hash != meta["schema_hash"]:
                    errors.append(f"{name} schema_hash mismatch")
            except Exception as exc:
                errors.append(f"{name} chunk schema read failed: {exc}")

        if meta["row_group_count"] <= 0 and meta["row_count"] > 0:
            errors.append(f"{name} row_group_count is zero")

        if level in {"standard_plus", "strict"}:
            try:
                first_hash = _parquet_row_group_checksum(merged_path, 0)
                last_hash = _parquet_row_group_checksum(
                    merged_path, meta["row_group_count"] - 1
                )
            except Exception as exc:
                errors.append(f"row group checksum failed for {merged_rel}: {exc}")
                continue
            if first_hash is None or last_hash is None:
                errors.append(f"row group checksum missing for {merged_rel}")
        if level == "strict":
            try:
                parquet = pq.ParquetFile(merged_path)
                for idx in range(parquet.metadata.num_row_groups):
                    parquet.read_row_group(idx)
            except Exception as exc:
                errors.append(f"{name} full row group read failed: {exc}")


def _cleanup_local(run_dir: Path, keep_local: str) -> None:
    keep_local = str(keep_local or "metadata").strip().lower()
    for path in sorted(run_dir.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                continue
            continue
        rel = path.relative_to(run_dir)
        if keep_local == "metadata" and _is_metadata(rel):
            continue
        if keep_local == "none" or (keep_local == "metadata" and not _is_metadata(rel)):
            try:
                path.unlink()
            except Exception as exc:
                logger.warning("Failed to remove %s: %s", path, exc)
