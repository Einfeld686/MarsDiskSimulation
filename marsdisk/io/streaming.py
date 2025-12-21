"""Streaming writer helpers for large zero-D runs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from marsdisk.runtime.history import ZeroDHistory
from . import writer

logger = logging.getLogger(__name__)

# Approximate byte footprints used for memory guardrails.
MEMORY_RUN_ROW_BYTES = 2200.0
MEMORY_PSD_ROW_BYTES = 320.0
MEMORY_DIAG_ROW_BYTES = 1400.0


class StreamingState:
    """Manage streaming flush of large histories to Parquet/CSV chunks."""

    def __init__(
        self,
        *,
        enabled: bool,
        outdir: Path,
        compression: str = "snappy",
        memory_limit_gb: float = 10.0,
        step_flush_interval: int = 10000,
        merge_at_end: bool = True,
        step_diag_enabled: bool = False,
        step_diag_path: Optional[Path] = None,
        step_diag_format: str = "csv",
    ) -> None:
        self.enabled = bool(enabled)
        self.outdir = Path(outdir)
        self.compression = compression
        self.memory_limit_bytes = float(memory_limit_gb) * (1024.0**3)
        self.step_flush_interval = int(step_flush_interval) if step_flush_interval > 0 else 0
        self.merge_at_end = bool(merge_at_end)
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

    def _chunk_label(self, step_end: int) -> str:
        step_end = max(step_end, self.chunk_start_step)
        return f"{self.chunk_start_step:09d}_{step_end:09d}"

    def flush(self, history: ZeroDHistory, step_end: int) -> None:
        if not self.enabled:
            return
        label = self._chunk_label(step_end)
        series_dir = self.outdir / "series"
        wrote_any = False
        if history.records:
            path = series_dir / f"run_chunk_{label}.parquet"
            writer.write_parquet(pd.DataFrame(history.records), path, compression=self.compression)
            self.run_chunks.append(path)
            history.records.clear()
            wrote_any = True
        if history.psd_hist_records:
            path = series_dir / f"psd_hist_chunk_{label}.parquet"
            writer.write_parquet(
                pd.DataFrame(history.psd_hist_records), path, compression=self.compression
            )
            self.psd_chunks.append(path)
            history.psd_hist_records.clear()
            wrote_any = True
        if history.diagnostics:
            path = series_dir / f"diagnostics_chunk_{label}.parquet"
            writer.write_parquet(
                pd.DataFrame(history.diagnostics), path, compression=self.compression
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

    def merge_chunks(self) -> None:
        if not self.enabled or not self.merge_at_end:
            return
        if self.run_chunks:
            self._merge_parquet_chunks(self.run_chunks, self.outdir / "series" / "run.parquet")
        if self.psd_chunks:
            self._merge_parquet_chunks(
                self.psd_chunks, self.outdir / "series" / "psd_hist.parquet"
            )
        if self.diag_chunks:
            self._merge_parquet_chunks(
                self.diag_chunks, self.outdir / "series" / "diagnostics.parquet"
            )

    def _merge_parquet_chunks(self, chunks: List[Path], destination: Path) -> None:
        """Merge multiple Parquet chunk files into a single destination file.

        This method handles schema mismatches between chunks by unifying schemas
        and filling missing columns with nulls. This allows merging chunks written
        by different code versions or across checkpoint restarts.
        """
        if not chunks:
            return
        writer._ensure_parent(destination)
        sorted_chunks = sorted(chunks)

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
            return

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


__all__ = [
    "StreamingState",
    "MEMORY_RUN_ROW_BYTES",
    "MEMORY_PSD_ROW_BYTES",
    "MEMORY_DIAG_ROW_BYTES",
]
