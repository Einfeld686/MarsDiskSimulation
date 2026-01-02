import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from marsdisk import run


def _write_chunk(path, times):
    table = pa.table({
        "time": [float(value) for value in times],
        "dt": [1.0] * len(times),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def test_streaming_flush_and_merge(tmp_path):
    series_dir = tmp_path / "series"
    streaming = run.StreamingState(
        enabled=True,
        outdir=tmp_path,
        compression="snappy",
        memory_limit_gb=1.0,
        step_flush_interval=0,
        merge_at_end=True,
        step_diag_enabled=False,
        step_diag_path=None,
        step_diag_format="csv",
    )

    history = run.ZeroDHistory()
    history.records.append({"time": 0.0, "dt": 1.0})
    # Flush creates run_chunk_*.parquet
    streaming.flush(history, step_end=0)
    run_chunks = sorted(series_dir.glob("run_chunk_*.parquet"))
    assert run_chunks, "run_chunk parquet should be written"

    # Merge into run.parquet
    streaming.merge_chunks()
    merged = series_dir / "run.parquet"
    assert merged.exists(), "merged run.parquet should be created"

    df = pd.read_parquet(merged)
    assert len(df) == 1
    assert df.iloc[0]["time"] == 0.0
    assert df.iloc[0]["dt"] == 1.0


def test_merge_with_schema_mismatch(tmp_path):
    """Test that merging chunks with different schemas works correctly.

    Simulates the scenario where code changes add new columns between chunks,
    such as when M_sink_cum was added mid-stream.
    """
    series_dir = tmp_path / "series"
    series_dir.mkdir(parents=True, exist_ok=True)

    # Chunk 1: Old schema without M_sink_cum
    table1 = pa.table({
        "time": [0.0, 1.0],
        "dt": [0.5, 0.5],
        "M_loss_cum": [0.0, 0.001],
    })
    chunk1_path = series_dir / "run_chunk_000000000_000000001.parquet"
    pq.write_table(table1, chunk1_path)

    # Chunk 2: New schema with M_sink_cum added
    table2 = pa.table({
        "time": [2.0, 3.0],
        "dt": [0.5, 0.5],
        "M_loss_cum": [0.002, 0.003],
        "M_sink_cum": [0.0001, 0.0002],
    })
    chunk2_path = series_dir / "run_chunk_000000002_000000003.parquet"
    pq.write_table(table2, chunk2_path)

    # Create streaming state and register chunks
    streaming = run.StreamingState(
        enabled=True,
        outdir=tmp_path,
        compression="snappy",
        memory_limit_gb=1.0,
        step_flush_interval=0,
        merge_at_end=True,
        step_diag_enabled=False,
        step_diag_path=None,
        step_diag_format="csv",
    )
    streaming.run_chunks = [chunk1_path, chunk2_path]

    # Merge should succeed despite schema mismatch
    streaming.merge_chunks()
    merged = series_dir / "run.parquet"
    assert merged.exists(), "merged run.parquet should be created"

    df = pd.read_parquet(merged)
    assert len(df) == 4, "All rows from both chunks should be present"
    assert "M_sink_cum" in df.columns, "M_sink_cum column should exist in merged output"
    # Rows from chunk1 should have null for M_sink_cum
    assert pd.isna(df.iloc[0]["M_sink_cum"]), "Missing column should be filled with null"
    assert pd.isna(df.iloc[1]["M_sink_cum"]), "Missing column should be filled with null"
    # Rows from chunk2 should have actual values
    assert df.iloc[2]["M_sink_cum"] == 0.0001
    assert df.iloc[3]["M_sink_cum"] == 0.0002


def test_streaming_offload_move_merge(tmp_path):
    series_dir = tmp_path / "series"
    offload_dir = tmp_path / "offload"
    streaming = run.StreamingState(
        enabled=True,
        outdir=tmp_path,
        compression="snappy",
        memory_limit_gb=1.0,
        step_flush_interval=0,
        merge_at_end=True,
        step_diag_enabled=False,
        step_diag_path=None,
        step_diag_format="csv",
        offload_enabled=True,
        offload_dir=offload_dir,
        offload_keep_last_n=1,
        offload_mode="move",
        offload_verify="size",
        offload_skip_if_same_device=False,
    )

    history = run.ZeroDHistory()
    for step_no in range(3):
        history.records.append({"time": float(step_no), "dt": 1.0})
        streaming.flush(history, step_end=step_no)

    local_chunks = sorted(series_dir.glob("run_chunk_*.parquet"))
    offloaded_chunks = sorted(offload_dir.glob("run_chunk_*.parquet"))
    assert len(local_chunks) == 1, "Only the newest chunk stays local"
    assert len(offloaded_chunks) == 2, "Older chunks should be offloaded"

    streaming.merge_chunks()
    merged = series_dir / "run.parquet"
    assert merged.exists(), "merged run.parquet should be created"
    df = pd.read_parquet(merged)
    assert len(df) == 3


def test_streaming_discover_offload_chunks(tmp_path):
    series_dir = tmp_path / "series"
    offload_dir = tmp_path / "offload"
    _write_chunk(series_dir / "run_chunk_000000000_000000000.parquet", [0.0])
    _write_chunk(offload_dir / "run_chunk_000000001_000000001.parquet", [1.0])

    streaming = run.StreamingState(
        enabled=True,
        outdir=tmp_path,
        compression="snappy",
        memory_limit_gb=1.0,
        step_flush_interval=0,
        merge_at_end=True,
        step_diag_enabled=False,
        step_diag_path=None,
        step_diag_format="csv",
        offload_enabled=True,
        offload_dir=offload_dir,
        offload_keep_last_n=1,
        offload_mode="move",
        offload_verify="size",
        offload_skip_if_same_device=False,
    )

    streaming.discover_existing_chunks(
        offload_dir=offload_dir,
        psd_history_enabled=False,
        diagnostics_enabled=False,
    )
    assert len(streaming.run_chunks) == 2

    streaming.merge_chunks()
    df = pd.read_parquet(series_dir / "run.parquet")
    assert len(df) == 2


def test_streaming_discover_duplicate_prefers_local(tmp_path):
    series_dir = tmp_path / "series"
    offload_dir = tmp_path / "offload"
    chunk_name = "run_chunk_000000000_000000000.parquet"
    local_path = series_dir / chunk_name
    offload_path = offload_dir / chunk_name
    _write_chunk(local_path, [0.0])
    _write_chunk(offload_path, [0.0])
    mtime = local_path.stat().st_mtime
    os.utime(offload_path, (mtime, mtime))

    streaming = run.StreamingState(
        enabled=True,
        outdir=tmp_path,
        compression="snappy",
        memory_limit_gb=1.0,
        step_flush_interval=0,
        merge_at_end=True,
        step_diag_enabled=False,
        step_diag_path=None,
        step_diag_format="csv",
        offload_enabled=True,
        offload_dir=offload_dir,
        offload_keep_last_n=1,
        offload_mode="move",
        offload_verify="size",
        offload_skip_if_same_device=False,
    )

    streaming.discover_existing_chunks(
        offload_dir=offload_dir,
        psd_history_enabled=False,
        diagnostics_enabled=False,
    )
    assert streaming.run_chunks
    assert streaming.run_chunks[0] == local_path
