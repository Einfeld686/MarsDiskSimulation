"""Streaming writer helpers for large zero-D runs."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

from marsdisk.runtime.history import ColumnarBuffer, ZeroDHistory
from . import writer

logger = logging.getLogger(__name__)

# Approximate byte footprints used for memory guardrails.
MEMORY_RUN_ROW_BYTES = 2200.0
MEMORY_PSD_ROW_BYTES = 320.0
MEMORY_DIAG_ROW_BYTES = 1400.0

CHUNK_PATTERN = re.compile(r".*_chunk_(\d+)_(\d+)\.parquet$")


class StreamingState:
    """Manage streaming flush of large histories to Parquet/CSV chunks."""

    def __init__(
        self,
        *,
        enabled: bool,
        outdir: Path,
        merge_outdir: Optional[Path] = None,
        compression: str = "snappy",
        memory_limit_gb: float = 10.0,
        step_flush_interval: int = 10000,
        merge_at_end: bool = True,
        cleanup_chunks: bool = True,
        step_diag_enabled: bool = False,
        step_diag_path: Optional[Path] = None,
        step_diag_format: str = "csv",
        series_columns: Optional[List[str]] = None,
        diagnostic_columns: Optional[List[str]] = None,
        offload_enabled: bool = False,
        offload_dir: Optional[Path] = None,
        offload_keep_last_n: int = 2,
        offload_mode: str = "move",
        offload_verify: str = "size",
        offload_skip_if_same_device: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.outdir = Path(outdir)
        self.merge_outdir = Path(merge_outdir) if merge_outdir is not None else self.outdir
        self.compression = compression
        self.memory_limit_bytes = float(memory_limit_gb) * (1024.0**3)
        self.step_flush_interval = int(step_flush_interval) if step_flush_interval > 0 else 0
        self.merge_at_end = bool(merge_at_end)
        self.cleanup_chunks = bool(cleanup_chunks)
        self.step_diag_enabled = bool(step_diag_enabled)
        self.step_diag_path = step_diag_path if step_diag_enabled else None
        self.step_diag_format = step_diag_format
        self.chunk_index = 0
        self.chunk_start_step = 0
        self.run_chunks: List[Path] = []
        self.psd_chunks: List[Path] = []
        self.diag_chunks: List[Path] = []
        self.mass_budget_path: Path = self.outdir / "checks" / "mass_budget.csv"
        self.mass_budget_header_written = False
        self.mass_budget_cells_path: Path = self.outdir / "checks" / "mass_budget_cells.csv"
        self.mass_budget_cells_header_written = False
        self.step_diag_header_written = False
        self.series_columns = series_columns
        self.diagnostic_columns = diagnostic_columns
        self.offload_enabled = bool(offload_enabled) and self.enabled
        self.offload_dir = Path(offload_dir) if offload_dir is not None else None
        self.offload_keep_last_n = max(int(offload_keep_last_n), 0)
        self.offload_mode = str(offload_mode).lower()
        self.offload_verify = str(offload_verify).lower()
        self.offload_skip_if_same_device = bool(offload_skip_if_same_device)
        self._offload_skip_reason: Optional[str] = None
        try:
            self._outdir_device: Optional[int] = self.outdir.stat().st_dev
        except OSError:
            self._outdir_device = None

    def _estimate_bytes(self, history: ZeroDHistory) -> float:
        run_bytes = len(history.records) * MEMORY_RUN_ROW_BYTES
        psd_bytes = len(history.psd_hist_records) * MEMORY_PSD_ROW_BYTES
        diag_bytes = len(history.diagnostics) * MEMORY_DIAG_ROW_BYTES
        budget_bytes = len(history.mass_budget) * MEMORY_RUN_ROW_BYTES
        budget_cells_bytes = len(history.mass_budget_cells) * MEMORY_RUN_ROW_BYTES
        step_diag_bytes = len(history.step_diag_records) * MEMORY_DIAG_ROW_BYTES
        return run_bytes + psd_bytes + diag_bytes + budget_bytes + budget_cells_bytes + step_diag_bytes

    def should_flush(self, history: ZeroDHistory, steps_since_flush: int) -> bool:
        if not self.enabled:
            return False
        if self.memory_limit_bytes > 0 and self._estimate_bytes(history) >= self.memory_limit_bytes:
            return True
        if self.step_flush_interval > 0 and steps_since_flush >= self.step_flush_interval:
            return True
        return False

    def _chunk_sort_key(self, path: Path) -> Tuple[int, int, str]:
        match = CHUNK_PATTERN.match(path.name)
        if match:
            return (int(match.group(1)), int(match.group(2)), path.name)
        return (1_000_000_000, 1_000_000_000, path.name)

    def _sort_chunks(self, chunks: List[Path]) -> List[Path]:
        return sorted(chunks, key=self._chunk_sort_key)

    def _chunk_label(self, step_end: int) -> str:
        step_end = max(step_end, self.chunk_start_step)
        return f"{self.chunk_start_step:09d}_{step_end:09d}"

    def _find_existing_ancestor(self, path: Path) -> Optional[Path]:
        candidate = path
        while True:
            if candidate.exists():
                return candidate
            parent = candidate.parent
            if parent == candidate:
                return None
            candidate = parent

    def _log_offload_skip(self, reason: str) -> None:
        if self._offload_skip_reason != reason:
            logger.warning("Streaming offload skipped: %s", reason)
            self._offload_skip_reason = reason

    def _ensure_offload_dir(self) -> Optional[Path]:
        if not self.offload_enabled:
            return None
        if self.offload_dir is None:
            self._log_offload_skip("offload enabled but offload dir is not set")
            return None
        existing = self._find_existing_ancestor(self.offload_dir)
        if existing is None:
            self._log_offload_skip(f"offload dir not available: {self.offload_dir}")
            return None
        if self.offload_skip_if_same_device and self._outdir_device is not None:
            try:
                if existing.stat().st_dev == self._outdir_device:
                    self._log_offload_skip("target is on the same device as outdir")
                    return None
            except OSError:
                self._log_offload_skip("failed to resolve offload device")
                return None
        if not self.offload_dir.exists():
            try:
                self.offload_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self._log_offload_skip(f"failed to create offload dir: {exc}")
                return None
        if self._offload_skip_reason is not None:
            logger.info("Streaming offload resumed at %s", self.offload_dir)
            self._offload_skip_reason = None
        return self.offload_dir

    def _hash_file(self, path: Path) -> Optional[str]:
        try:
            hasher = hashlib.sha256()
            with path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError as exc:
            logger.warning("Failed to hash %s: %s", path, exc)
            return None

    def _verify_match(self, source: Path, dest: Path) -> bool:
        if self.offload_verify == "hash":
            src_hash = self._hash_file(source)
            dest_hash = self._hash_file(dest)
            if src_hash is None or dest_hash is None:
                return False
            return src_hash == dest_hash
        try:
            return source.stat().st_size == dest.stat().st_size
        except OSError as exc:
            logger.warning("Failed to compare chunk sizes for %s: %s", source, exc)
            return False

    def _transfer_chunk(self, source: Path, dest: Path) -> Path:
        if dest.exists():
            if self._verify_match(source, dest):
                if self.offload_mode == "move":
                    try:
                        source.unlink()
                        return dest
                    except OSError as exc:
                        logger.warning("Failed to remove local chunk %s: %s", source, exc)
                        return source
                return source
            logger.warning("Offload target exists but verification failed for %s", source)
            return source
        try:
            shutil.copy2(source, dest)
        except OSError as exc:
            logger.warning("Failed to offload chunk %s: %s", source, exc)
            return source
        if not self._verify_match(source, dest):
            logger.warning("Offloaded chunk verification failed for %s", source)
            try:
                dest.unlink()
            except OSError:
                pass
            return source
        if self.offload_mode == "move":
            try:
                source.unlink()
                return dest
            except OSError as exc:
                logger.warning("Failed to remove local chunk %s: %s", source, exc)
                return source
        return source

    def _offload_chunk(self, path: Path, offload_dir: Path) -> Path:
        if not path.exists():
            return path
        if path.parent == offload_dir:
            return path
        dest = offload_dir / path.name
        return self._transfer_chunk(path, dest)

    def _offload_old_chunks(self) -> None:
        if not self.offload_enabled:
            return
        offload_dir = self._ensure_offload_dir()
        if offload_dir is None:
            return
        keep_last_n = self.offload_keep_last_n
        for chunk_list in (self.run_chunks, self.diag_chunks, self.psd_chunks):
            if not chunk_list:
                continue
            cutoff = len(chunk_list) - keep_last_n if keep_last_n > 0 else len(chunk_list)
            updated: List[Path] = []
            for idx, path in enumerate(chunk_list):
                if idx < cutoff:
                    updated.append(self._offload_chunk(path, offload_dir))
                else:
                    updated.append(path)
            chunk_list[:] = self._sort_chunks(updated)

    def discover_existing_chunks(
        self,
        *,
        offload_dir: Optional[Path] = None,
        psd_history_enabled: bool = True,
        diagnostics_enabled: bool = True,
    ) -> None:
        if not self.enabled:
            return
        local_series = self.outdir / "series"
        local_run = self._scan_chunks(local_series, "run_chunk_*.parquet")
        local_diag = (
            self._scan_chunks(local_series, "diagnostics_chunk_*.parquet")
            if diagnostics_enabled
            else []
        )
        local_psd = (
            self._scan_chunks(local_series, "psd_hist_chunk_*.parquet")
            if psd_history_enabled
            else []
        )
        offload_root = Path(offload_dir) if offload_dir is not None else self.offload_dir
        offload_run: List[Path] = []
        offload_diag: List[Path] = []
        offload_psd: List[Path] = []
        if offload_root is not None:
            if offload_root.exists():
                offload_run = self._scan_chunks(offload_root, "run_chunk_*.parquet")
                if diagnostics_enabled:
                    offload_diag = self._scan_chunks(offload_root, "diagnostics_chunk_*.parquet")
                if psd_history_enabled:
                    offload_psd = self._scan_chunks(offload_root, "psd_hist_chunk_*.parquet")
            else:
                logger.warning("Offload dir not available for rediscovery: %s", offload_root)
        self.run_chunks = self._merge_discovered_chunks(local_run, offload_run)
        self.diag_chunks = self._merge_discovered_chunks(local_diag, offload_diag)
        self.psd_chunks = self._merge_discovered_chunks(local_psd, offload_psd)

    def _scan_chunks(self, root: Path, pattern: str) -> List[Path]:
        if not root.exists():
            return []
        return self._sort_chunks(list(root.glob(pattern)))

    def _safe_stat(self, path: Path) -> Optional[os.stat_result]:
        try:
            return path.stat()
        except OSError as exc:
            logger.warning("Failed to stat %s: %s", path, exc)
            return None

    def _resolve_duplicate(self, local_path: Path, other_path: Path) -> Path:
        if self.offload_verify == "hash":
            local_hash = self._hash_file(local_path)
            other_hash = self._hash_file(other_path)
            if local_hash is not None and other_hash is not None and local_hash == other_hash:
                return local_path
            local_stat = self._safe_stat(local_path)
            other_stat = self._safe_stat(other_path)
            if local_stat is None or other_stat is None:
                return local_path
            chosen = local_path if local_stat.st_mtime >= other_stat.st_mtime else other_path
            logger.warning(
                "Duplicate chunk %s hash mismatch; using %s",
                local_path.name,
                chosen,
            )
            return chosen
        local_stat = self._safe_stat(local_path)
        other_stat = self._safe_stat(other_path)
        if local_stat is None or other_stat is None:
            return local_path
        if local_stat.st_size != other_stat.st_size:
            chosen = local_path if local_stat.st_size > other_stat.st_size else other_path
            logger.warning(
                "Duplicate chunk %s size mismatch; using %s",
                local_path.name,
                chosen,
            )
            return chosen
        if local_stat.st_mtime != other_stat.st_mtime:
            chosen = local_path if local_stat.st_mtime >= other_stat.st_mtime else other_path
            logger.warning(
                "Duplicate chunk %s mtime mismatch; using %s",
                local_path.name,
                chosen,
            )
            return chosen
        return local_path

    def _merge_discovered_chunks(self, local_chunks: List[Path], offload_chunks: List[Path]) -> List[Path]:
        if not local_chunks and not offload_chunks:
            return []
        by_name: Dict[str, Path] = {chunk.name: chunk for chunk in local_chunks}
        for chunk in offload_chunks:
            existing = by_name.get(chunk.name)
            if existing is None:
                by_name[chunk.name] = chunk
                continue
            chosen = self._resolve_duplicate(existing, chunk)
            by_name[chunk.name] = chosen
        return self._sort_chunks(list(by_name.values()))

    def flush(self, history: ZeroDHistory, step_end: int) -> None:
        if not self.enabled:
            return
        label = self._chunk_label(step_end)
        series_dir = self.outdir / "series"
        wrote_any = False
        if history.records:
            path = series_dir / f"run_chunk_{label}.parquet"
            if isinstance(history.records, ColumnarBuffer):
                try:
                    table = history.records.to_table(ensure_columns=self.series_columns)
                    writer.write_parquet_table(
                        table,
                        path,
                        compression=self.compression,
                    )
                except Exception as exc:
                    logger.warning("Columnar flush failed for %s: %s; falling back to row write", path, exc)
                    writer.write_parquet(
                        history.records.to_records(),
                        path,
                        compression=self.compression,
                        ensure_columns=self.series_columns,
                    )
            else:
                writer.write_parquet(
                    history.records,
                    path,
                    compression=self.compression,
                    ensure_columns=self.series_columns,
                )
            self.run_chunks.append(path)
            history.records.clear()
            wrote_any = True
        if history.psd_hist_records:
            path = series_dir / f"psd_hist_chunk_{label}.parquet"
            writer.write_parquet(history.psd_hist_records, path, compression=self.compression)
            self.psd_chunks.append(path)
            history.psd_hist_records.clear()
            wrote_any = True
        if history.diagnostics:
            path = series_dir / f"diagnostics_chunk_{label}.parquet"
            if isinstance(history.diagnostics, ColumnarBuffer):
                try:
                    table = history.diagnostics.to_table(ensure_columns=self.diagnostic_columns)
                    writer.write_parquet_table(
                        table,
                        path,
                        compression=self.compression,
                    )
                except Exception as exc:
                    logger.warning(
                        "Columnar diagnostics flush failed for %s: %s; falling back to row write",
                        path,
                        exc,
                    )
                    writer.write_parquet(
                        history.diagnostics.to_records(),
                        path,
                        compression=self.compression,
                        ensure_columns=self.diagnostic_columns,
                    )
            else:
                writer.write_parquet(
                    history.diagnostics,
                    path,
                    compression=self.compression,
                    ensure_columns=self.diagnostic_columns,
                )
            self.diag_chunks.append(path)
            history.diagnostics.clear()
            wrote_any = True
        if history.mass_budget:
            header = not self.mass_budget_header_written
            wrote = writer.append_csv(history.mass_budget, self.mass_budget_path, header=header)
            self.mass_budget_header_written = self.mass_budget_header_written or wrote
            history.mass_budget.clear()
        if history.mass_budget_cells:
            header = not self.mass_budget_cells_header_written
            wrote = writer.append_csv(
                history.mass_budget_cells,
                self.mass_budget_cells_path,
                header=header,
            )
            self.mass_budget_cells_header_written = self.mass_budget_cells_header_written or wrote
            history.mass_budget_cells.clear()
        if self.step_diag_enabled and history.step_diag_records and self.step_diag_path is not None:
            header = not self.step_diag_header_written
            wrote = writer.append_step_diagnostics(
                history.step_diag_records,
                self.step_diag_path,
                fmt=self.step_diag_format,
                header=header,
            )
            self.step_diag_header_written = self.step_diag_header_written or wrote
            history.step_diag_records.clear()
        if wrote_any:
            self.chunk_index += 1
            self.chunk_start_step = step_end + 1
            self._offload_old_chunks()

    def merge_chunks(self) -> None:
        if not self.enabled or not self.merge_at_end:
            return
        merge_root = self.merge_outdir if self.merge_outdir is not None else self.outdir
        run_chunks = self._existing_chunks(self.run_chunks, "run")
        if run_chunks:
            merged = self._merge_parquet_chunks(run_chunks, merge_root / "series" / "run.parquet")
            if merged and self.cleanup_chunks:
                removed = self._cleanup_chunk_files(run_chunks)
                if removed:
                    removed_set = set(removed)
                    self.run_chunks = [p for p in self.run_chunks if p not in removed_set]
        psd_chunks = self._existing_chunks(self.psd_chunks, "psd_hist")
        if psd_chunks:
            merged = self._merge_parquet_chunks(
                psd_chunks, merge_root / "series" / "psd_hist.parquet"
            )
            if merged and self.cleanup_chunks:
                removed = self._cleanup_chunk_files(psd_chunks)
                if removed:
                    removed_set = set(removed)
                    self.psd_chunks = [p for p in self.psd_chunks if p not in removed_set]
        diag_chunks = self._existing_chunks(self.diag_chunks, "diagnostics")
        if diag_chunks:
            merged = self._merge_parquet_chunks(
                diag_chunks, merge_root / "series" / "diagnostics.parquet"
            )
            if merged and self.cleanup_chunks:
                removed = self._cleanup_chunk_files(diag_chunks)
                if removed:
                    removed_set = set(removed)
                    self.diag_chunks = [p for p in self.diag_chunks if p not in removed_set]

    def _existing_chunks(self, chunks: List[Path], label: str) -> List[Path]:
        existing = [path for path in chunks if path.exists()]
        if len(existing) != len(chunks):
            missing = len(chunks) - len(existing)
            logger.warning("Missing %s chunk files: %d", label, missing)
        return existing

    def _cleanup_chunk_files(self, chunks: List[Path]) -> List[Path]:
        removed: List[Path] = []
        for path in chunks:
            try:
                path.unlink()
                removed.append(path)
            except FileNotFoundError:
                continue
            except OSError as exc:
                logger.warning("Failed to remove chunk %s: %s", path, exc)
        return removed

    def _merge_parquet_chunks(self, chunks: List[Path], destination: Path) -> bool:
        """Merge multiple Parquet chunk files into a single destination file.

        This method handles schema mismatches between chunks by unifying schemas
        and filling missing columns with nulls. This allows merging chunks written
        by different code versions or across checkpoint restarts.
        """
        if not chunks:
            return False
        writer._ensure_parent(destination)
        sorted_chunks = self._sort_chunks(chunks)

        # Phase 1: Collect schemas from all chunks
        schemas: List[pa.Schema] = []
        valid_chunks: List[Path] = []
        for path in sorted_chunks:
            try:
                schema = pq.read_schema(path)
                schemas.append(schema)
                valid_chunks.append(path)
            except Exception as exc:
                logger.warning("Failed to read schema from %s: %s", path, exc)

        if not schemas:
            logger.warning("No valid chunk schemas found, skipping merge for %s", destination)
            return False

        # Phase 2: Unify schemas to create a superset of all columns
        try:
            unified_schema = pa.unify_schemas(schemas, promote_options="permissive")
        except pa.ArrowInvalid as exc:
            logger.warning(
                "Schema unification failed for %s, falling back to first chunk schema: %s",
                destination,
                exc,
            )
            unified_schema = schemas[0]

        # Phase 3: Write tables with unified schema, filling missing columns
        parquet_writer: Optional[pq.ParquetWriter] = None
        try:
            for path in valid_chunks:
                table = pq.read_table(path)
                # Add missing columns as null arrays
                for field in unified_schema:
                    if field.name not in table.column_names:
                        null_array = pa.nulls(len(table), type=field.type)
                        table = table.append_column(field.name, null_array)
                # Reorder columns to match unified schema and cast types if needed
                try:
                    table = table.select([f.name for f in unified_schema])
                    table = table.cast(unified_schema)
                except Exception as exc:
                    logger.warning(
                        "Column reordering/casting failed for %s: %s; writing with original order",
                        path,
                        exc,
                    )
                if parquet_writer is None:
                    parquet_writer = pq.ParquetWriter(
                        destination, unified_schema, compression=self.compression
                    )
                parquet_writer.write_table(table)
        finally:
            if parquet_writer is not None:
                parquet_writer.close()
        return parquet_writer is not None and destination.exists()


__all__ = [
    "StreamingState",
    "MEMORY_RUN_ROW_BYTES",
    "MEMORY_PSD_ROW_BYTES",
    "MEMORY_DIAG_ROW_BYTES",
]
