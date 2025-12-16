"""
共通ユーティリティ: run ディレクトリから series/summary/psd を安全に読み込む。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd


def _read_parquet_safe(path: Path, columns: Iterable[str] | None = None) -> pd.DataFrame:
    """
    Parquet を列指定で読み、足りない列は NaN で補う。
    """
    if not path.exists():
        raise FileNotFoundError(path)

    if columns is None:
        return pd.read_parquet(path)

    try:
        return pd.read_parquet(path, columns=list(columns))
    except Exception:
        df = pd.read_parquet(path)
        df = df.copy()
        missing = [c for c in columns if c not in df.columns]
        for col in missing:
            df[col] = np.nan
        return df[columns]


def _downsample(df: pd.DataFrame, max_points: int | None) -> pd.DataFrame:
    if max_points is None or len(df) <= max_points:
        return df
    step = max(len(df) // max_points, 1)
    return df.iloc[::step].copy()


def load_series(run_dir: Path, columns: Iterable[str] | None = None, max_points: int | None = None) -> pd.DataFrame:
    """
    series/run.parquet を読み、必要なら間引く。
    """
    df = _read_parquet_safe(run_dir / "series" / "run.parquet", columns)
    if "time" in df.columns:
        df = df.sort_values("time")
    return _downsample(df, max_points)


def load_summary(run_dir: Path) -> Mapping:
    """
    summary.json を辞書で返す（なければ空 dict）。
    """
    path = run_dir / "summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def load_psd_hist(run_dir: Path, max_points: int | None = None) -> pd.DataFrame:
    """
    series/psd_hist.parquet を読み込む。なければ空 DataFrame。
    """
    path = run_dir / "series" / "psd_hist.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    if "time" in df.columns:
        df = df.sort_values("time")
    return _downsample(df, max_points)


def select_temperature(df: pd.DataFrame) -> np.ndarray:
    """
    温度列の優先順位で配列を返す。全 NaN の場合は None を返す。
    """
    for key in ("T_M_used", "T_M", "T_p_effective"):
        if key in df.columns:
            arr = np.asarray(df[key], dtype=float)
            if np.isfinite(arr).any():
                return arr
    return None


def ensure_plot_path(run_dir: Path, out: Path | None, default_name: str) -> Path:
    """
    保存先パスを確定する。未指定なら run_dir/plots/<default_name>。
    """
    if out is None:
        out_dir = run_dir / "plots"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir / default_name
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def column_or_default(df: pd.DataFrame, name: str, default: float = np.nan) -> np.ndarray:
    """
    列が無ければ default で埋めた配列を返す。
    """
    if name in df.columns:
        return np.asarray(df[name], dtype=float)
    return np.full(len(df), default, dtype=float)
