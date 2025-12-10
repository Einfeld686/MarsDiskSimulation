import pandas as pd

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
