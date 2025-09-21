#!/usr/bin/env python3
"""結果CSVからメトリクスのカラーマップを生成するユーティリティ。"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patches

DEFAULT_METRIC = "total_mass_lost_Mmars"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解釈する。"""

    parser = argparse.ArgumentParser(
        description="results/map{ID}.csv からヒートマップを生成して figures/ に保存します。"
    )
    parser.add_argument(
        "--map",
        type=int,
        choices=(1, 2, 3),
        required=True,
        help="読み込むマップ番号 (1, 2, 3)",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default=DEFAULT_METRIC,
        help=f"ヒートマップに用いる列名 (デフォルト: {DEFAULT_METRIC})",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def ensure_directory(path: Path) -> None:
    """ディレクトリが存在しなければ作成する。"""

    path.mkdir(parents=True, exist_ok=True)


def load_csv(map_id: int) -> pd.DataFrame:
    """指定マップIDのCSVを読み込む。"""

    csv_path = Path("results") / f"map{map_id}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
    df = pd.read_csv(csv_path)
    required_columns = {
        "map_id",
        "case_id",
        "param_x_name",
        "param_x_value",
        "param_y_name",
        "param_y_value",
    }
    missing = sorted(required_columns.difference(df.columns))
    if missing:
        raise ValueError(f"必要な列が不足しています: {', '.join(missing)}")
    return df


def format_tick_label(value: object) -> str:
    """軸目盛のラベル文字列を生成する。"""

    if isinstance(value, float):
        if math.isfinite(value):
            return f"{value:g}"
        return str(value)
    return str(value)


def prepare_pivot(
    df: pd.DataFrame, metric: str
) -> tuple[pd.DataFrame, List[object], List[object], str, str]:
    """ピボットテーブルと軸ラベル情報を組み立てる。"""

    if metric not in df.columns:
        raise ValueError(f"指定されたメトリクス列が存在しません: {metric}")

    x_label = df["param_x_name"].dropna().iloc[0] if not df["param_x_name"].dropna().empty else "param_x"
    y_label = df["param_y_name"].dropna().iloc[0] if not df["param_y_name"].dropna().empty else "param_y"

    x_order = df["param_x_value"].drop_duplicates().tolist()
    y_order = df["param_y_value"].drop_duplicates().tolist()

    working = df.copy()
    working[metric] = pd.to_numeric(working[metric], errors="coerce")
    if "case_status" in working.columns:
        working.loc[working["case_status"].astype(str) != "success", metric] = np.nan

    working["param_x_value"] = pd.Categorical(working["param_x_value"], categories=x_order, ordered=True)
    working["param_y_value"] = pd.Categorical(working["param_y_value"], categories=y_order, ordered=True)

    pivot = working.pivot(index="param_y_value", columns="param_x_value", values=metric)
    pivot = pivot.reindex(index=pd.Index(y_order, name=pivot.index.name), columns=pd.Index(x_order, name=pivot.columns.name))

    return pivot, x_order, y_order, str(x_label), str(y_label)


def compute_log_values(pivot: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """元の値と log10 値 (マスク付き) を計算する。"""

    values = pivot.to_numpy(dtype=float)
    valid = np.isfinite(values) & (values > 0.0)
    if not np.any(valid):
        raise ValueError("指定されたメトリクスに有効な値がありません。")

    log_values = np.full_like(values, np.nan, dtype=float)
    log_values[valid] = np.log10(values[valid])
    masked_log = np.ma.masked_invalid(log_values)
    return values, masked_log


def plot_heatmap(
    map_id: int,
    metric: str,
    pivot: pd.DataFrame,
    x_values: List[object],
    y_values: List[object],
    x_label: str,
    y_label: str,
    output_path: Path,
) -> None:
    """ヒートマップを描画して保存する。"""

    original_values, masked_log = compute_log_values(pivot)

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad(color="lightgray")

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(masked_log, origin="lower", cmap=cmap, aspect="auto")

    x_ticks = np.arange(len(x_values))
    y_ticks = np.arange(len(y_values))
    ax.set_xticks(x_ticks)
    ax.set_xticklabels([format_tick_label(v) for v in x_values], rotation=45, ha="right")
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([format_tick_label(v) for v in y_values])
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(f"Map {map_id}: {metric}")

    # 罫線を薄く描画してセルを見やすくする。
    ax.set_xticks(np.arange(-0.5, len(x_values), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(y_values), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.5)
    ax.tick_params(which="minor", bottom=False, left=False)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label(f"log10({metric})")

    # 無効セルにハッチングを重ねる。
    invalid_mask = ~np.isfinite(original_values) | (original_values <= 0.0)
    if np.any(invalid_mask):
        for (y_idx, x_idx) in zip(*np.where(invalid_mask)):
            rect = patches.Rectangle(
                (x_idx - 0.5, y_idx - 0.5),
                1.0,
                1.0,
                facecolor="none",
                hatch="///",
                edgecolor="gray",
                linewidth=0.8,
            )
            ax.add_patch(rect)

    fig.tight_layout()
    ensure_directory(output_path.parent)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def sanitize_metric_name(metric: str) -> str:
    """ファイル名に使いやすいメトリクス名へ変換する。"""

    return re.sub(r"[^A-Za-z0-9_.-]", "_", metric)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(None if argv is None else list(argv))

    try:
        df = load_csv(args.map)
        pivot, x_values, y_values, x_label, y_label = prepare_pivot(df, args.metric)
        metric_name_for_file = sanitize_metric_name(args.metric)
        output_path = Path("figures") / f"map{args.map}_{metric_name_for_file}.png"
        plt.rcParams.update({"font.size": 12})
        plot_heatmap(
            args.map,
            args.metric,
            pivot,
            x_values,
            y_values,
            x_label,
            y_label,
            output_path,
        )
        print(f"ヒートマップを {output_path} に保存しました。")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"エラー: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
