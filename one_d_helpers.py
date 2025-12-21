"""Helpers for 1D integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from marsdisk.run import load_config, run_zero_d
from marsdisk.run_one_d import run_one_d

BASE_CONFIG = Path("configs/base.yml")


def run_one_d_case(tmp_path: Path, overrides: list[str]) -> tuple[dict[str, Any], pd.DataFrame, Path]:
    cfg = load_config(BASE_CONFIG, overrides=overrides)
    cfg.io.outdir = tmp_path
    cfg.io.debug_sinks = False
    run_one_d(cfg)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    run_df = pd.read_parquet(tmp_path / "series" / "run.parquet")
    return summary, run_df, tmp_path


def run_zero_d_case(tmp_path: Path, overrides: list[str]) -> tuple[dict[str, Any], pd.DataFrame, Path]:
    cfg = load_config(BASE_CONFIG, overrides=overrides)
    cfg.io.outdir = tmp_path
    cfg.io.debug_sinks = False
    run_zero_d(cfg)
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    run_df = pd.read_parquet(tmp_path / "series" / "run.parquet")
    return summary, run_df, tmp_path
