"""Utility to merge streaming Parquet chunks left by marsdisk zero-D runs.

Streaming出力（`io.streaming.enable=true`）で途中終了した場合、`series/run_chunk_*`
などの一時ファイルだけが残り、`run.parquet` 等が生成されないことがある。
このツールは残存チャンクを検出して結合し、標準の最終ファイル名で保存する。
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


def _detect_series_dirs(paths: Sequence[Path]) -> List[Path]:
    """Return series directories to process."""
    series_dirs: List[Path] = []
    for raw in paths:
        p = raw.resolve()
        if not p.exists():
            logger.warning("Path does not exist, skipping: %s", p)
            continue
        if p.name == "series" and p.is_dir():
            series_dirs.append(p)
            continue
        candidate = p / "series"
        if candidate.is_dir():
            series_dirs.append(candidate.resolve())
            continue
        for sub in p.rglob("series"):
            if sub.is_dir():
                series_dirs.append(sub.resolve())
    # Remove duplicates while preserving order
    seen = set()
    unique_dirs: List[Path] = []
    for d in series_dirs:
        if d not in seen:
            unique_dirs.append(d)
            seen.add(d)
    return unique_dirs


def _probe_compression(path: Path) -> str:
    """Infer compression codec from a Parquet file."""
    try:
        meta = pq.ParquetFile(path).metadata
        if meta is None or meta.num_row_groups == 0 or meta.row_group(0).num_columns == 0:
            return "snappy"
        codec = meta.row_group(0).column(0).compression
        return str(codec).lower()
    except Exception:
        return "snappy"


def _merge_chunks(chunks: List[Path], destination: Path, *, force: bool) -> Tuple[bool, str]:
    """Merge Parquet chunks into destination. Returns (changed, message)."""
    if not chunks:
        return False, "no chunks found"
    if destination.exists() and not force:
        return False, f"exists: {destination}"

    compression = _probe_compression(chunks[0])
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    try:
        for idx, path in enumerate(sorted(chunks)):
            table = pq.read_table(path)
            if writer is None:
                writer = pq.ParquetWriter(destination, table.schema, compression=compression)
            else:
                if table.schema != writer.schema:
                    return False, f"schema mismatch at {path.name}"
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    return True, f"merged {len(chunks)} chunks -> {destination.name}"


def merge_series_dir(series_dir: Path, *, force: bool = False) -> List[str]:
    """Merge all known chunk types in a series directory."""
    messages: List[str] = []
    mappings = {
        "run": ("run_chunk_*.parquet", series_dir / "run.parquet"),
        "psd_hist": ("psd_hist_chunk_*.parquet", series_dir / "psd_hist.parquet"),
        "diagnostics": ("diagnostics_chunk_*.parquet", series_dir / "diagnostics.parquet"),
    }
    for name, (pattern, dest) in mappings.items():
        chunks = sorted(series_dir.glob(pattern))
        changed, msg = _merge_chunks(chunks, dest, force=force)
        prefix = f"[{name}]"
        messages.append(f"{prefix} {msg}")
    return messages


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge streaming Parquet chunks (run_chunk_*) into final outputs."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("out")],
        help="Run directoryまたはその親ディレクトリ。未指定なら out を再帰探索。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存の run.parquet 等を上書きして再生成する。",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    series_dirs = _detect_series_dirs(args.paths)
    if not series_dirs:
        logger.info("series ディレクトリが見つかりませんでした。終了します。")
        return 1

    exit_code = 0
    for series_dir in series_dirs:
        logger.info("processing: %s", series_dir)
        for msg in merge_series_dir(series_dir, force=args.force):
            logger.info("  %s", msg)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
