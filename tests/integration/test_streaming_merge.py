import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from marsdisk import run


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
