"""Plot heatmaps and diagnostics from parameter sweep results."""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patches

BLOWOUT_STATUS = "blowout"
DEFAULT_METRIC = "total_mass_lost_Mmars"
BETA_METRIC_LABELS = {
    "beta_at_smin": "β(最小粒径)",
    "beta_at_smin_config": "β(設定最小粒径)",
    "beta_at_smin_effective": "β(有効最小粒径)",
}


def _resolve_table_path(path: Path) -> Path:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        parquet_path = path.with_suffix(".parquet")
        if parquet_path.exists():
            if not path.exists() or parquet_path.stat().st_mtime >= path.stat().st_mtime:
                return parquet_path
    elif suffix in {".parquet", ".pq"} and not path.exists():
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """コマンドライン引数を解釈する。"""

    parser = argparse.ArgumentParser(
        description="results/map*.csv からヒートマップを生成して figures/ に保存します。"
    )
    parser.add_argument(
        "--map",
        type=str,
        required=True,
        help="読み込むマップ番号 (1, 1b, 2, 3)",
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


def _normalise_map_key(map_arg: str) -> Tuple[str, str]:
    key = map_arg.strip().lower()
    if key in {"1", "map1"}:
        return "map1", "Map-1"
    if key in {"1b", "map1b"}:
        return "map1b", "Map-1b"
    if key in {"2", "map2"}:
        return "map2", "Map-2"
    if key in {"3", "map3"}:
        return "map3", "Map-3"
    raise ValueError(f"未知のマップIDです: {map_arg}")


def load_csv(map_stub: str) -> pd.DataFrame:
    """指定マップIDのCSVを読み込む。"""

    csv_path = _resolve_table_path(Path("results") / f"{map_stub}.csv")
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
    if csv_path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(csv_path)
    else:
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
) -> Tuple[pd.DataFrame, pd.DataFrame | None, List[object], List[object], str, str]:
    """ピボットテーブルと軸ラベル情報を組み立てる。"""

    if metric not in df.columns:
        raise ValueError(f"指定されたメトリクス列が存在しません: {metric}")

    working = df.copy()
    working[metric] = pd.to_numeric(working[metric], errors="coerce")
    failure_pivot: pd.DataFrame | None = None
    if "case_status" in working.columns:
        statuses = working["case_status"].astype(str).str.lower()
        working.loc[statuses != BLOWOUT_STATUS, metric] = np.nan
        working["_failed_flag"] = statuses == "failed"
    else:
        working["_failed_flag"] = False

    x_label = (
        working["param_x_name"].dropna().iloc[0]
        if not working["param_x_name"].dropna().empty
        else "param_x"
    )
    y_label = (
        working["param_y_name"].dropna().iloc[0]
        if not working["param_y_name"].dropna().empty
        else "param_y"
    )

    x_order = working["param_x_value"].drop_duplicates().tolist()
    y_order = working["param_y_value"].drop_duplicates().tolist()

    working["param_x_value"] = pd.Categorical(working["param_x_value"], categories=x_order, ordered=True)
    working["param_y_value"] = pd.Categorical(working["param_y_value"], categories=y_order, ordered=True)

    pivot = working.pivot(index="param_y_value", columns="param_x_value", values=metric)
    pivot = pivot.reindex(
        index=pd.Index(y_order, name=pivot.index.name),
        columns=pd.Index(x_order, name=pivot.columns.name),
    )

    if "_failed_flag" in working:
        failure_pivot = working.pivot(
            index="param_y_value",
            columns="param_x_value",
            values="_failed_flag",
        )
        failure_pivot = failure_pivot.reindex(
            index=pd.Index(y_order, name=failure_pivot.index.name),
            columns=pd.Index(x_order, name=failure_pivot.columns.name),
        )
        failure_pivot = failure_pivot.fillna(False).astype(bool)

    return pivot, failure_pivot, x_order, y_order, str(x_label), str(y_label)


def compute_log_values(pivot: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, float, float]:
    """元の値と log10 値 (マスク付き) を計算する。"""

    values = pivot.to_numpy(dtype=float)
    finite = np.isfinite(values) & (values > 0.0)
    if not np.any(finite):
        raise ValueError("指定されたメトリクスに有効な値がありません。")

    log_values = np.full_like(values, np.nan, dtype=float)
    log_values[finite] = np.log10(values[finite])
    masked_log = np.ma.masked_invalid(log_values)
    log_min = float(np.min(log_values[finite]))
    log_max = float(np.max(log_values[finite]))
    return values, masked_log, log_min, log_max


def plot_heatmap(
    map_label: str,
    metric: str,
    pivot: pd.DataFrame,
    failure_pivot: pd.DataFrame | None,
    x_values: List[object],
    y_values: List[object],
    x_label: str,
    y_label: str,
    output_path: Path,
) -> Tuple[float, float]:
    """ヒートマップを描画して保存する。"""

    original_values, masked_log, log_min, log_max = compute_log_values(pivot)

    metric_label = metric_axis_label(metric)

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad(color="lightgray")

    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    im = ax.imshow(
        masked_log,
        origin="lower",
        cmap=cmap,
        aspect="auto",
        vmin=log_min,
        vmax=log_max,
    )

    x_ticks = np.arange(len(x_values))
    y_ticks = np.arange(len(y_values))
    ax.set_xticks(x_ticks)
    ax.set_xticklabels([format_tick_label(v) for v in x_values], rotation=45, ha="right")
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([format_tick_label(v) for v in y_values])
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(f"{map_label}: {metric}")

    ax.set_xticks(np.arange(-0.5, len(x_values), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(y_values), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.5)
    ax.tick_params(which="minor", bottom=False, left=False)

    cbar = fig.colorbar(im, ax=ax)
    cbar_label = f"log10({metric_label})"
    cbar.set_label(cbar_label)

    failure_mask = (
        failure_pivot.to_numpy(dtype=bool)
        if failure_pivot is not None
        else np.zeros_like(original_values, dtype=bool)
    )

    invalid_mask = ~np.isfinite(original_values) | (original_values <= 0.0)
    invalid_mask |= failure_mask
    if np.any(invalid_mask):
        hatch_patch = patches.Patch(
            facecolor="lightgray",
            edgecolor="gray",
            hatch="///",
            label="失敗/未計算",
        )
        legend_handles = [hatch_patch]
        for y_idx, row in enumerate(invalid_mask):
            start_idx: int | None = None
            for x_idx, flagged in enumerate(row):
                if flagged and start_idx is None:
                    start_idx = x_idx
                elif not flagged and start_idx is not None:
                    width = x_idx - start_idx
                    rect = patches.Rectangle(
                        (start_idx - 0.5, y_idx - 0.5),
                        width,
                        1.0,
                        facecolor="none",
                        hatch="///",
                        edgecolor="gray",
                        linewidth=0.8,
                    )
                    ax.add_patch(rect)
                    start_idx = None
            if start_idx is not None:
                width = len(row) - start_idx
                rect = patches.Rectangle(
                    (start_idx - 0.5, y_idx - 0.5),
                    width,
                    1.0,
                    facecolor="none",
                    hatch="///",
                    edgecolor="gray",
                    linewidth=0.8,
                )
                ax.add_patch(rect)
        ax.legend(handles=legend_handles, loc="upper right", frameon=True)

    clim = im.get_clim()
    if not np.allclose(clim, (log_min, log_max), rtol=1e-6, atol=1e-8):
        raise RuntimeError("カラーバー範囲がCSVの最小値/最大値と一致しません。")

    fig.tight_layout()
    ensure_directory(output_path.parent)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    return log_min, log_max


def sanitize_metric_name(metric: str) -> str:
    """ファイル名に使いやすいメトリクス名へ変換する。"""

    return re.sub(r"[^A-Za-z0-9_.-]", "_", metric)


def metric_axis_label(metric: str) -> str:
    """カラー軸などに用いる表示名を返す。"""

    if metric == DEFAULT_METRIC:
        return "M_loss / M_Mars"
    return BETA_METRIC_LABELS.get(metric, metric)


def maybe_plot_mass_per_r2_scatter(df: pd.DataFrame, map_stub: str, map_label: str) -> None:
    """Map-1 系列向けの M/r^2 散布図を保存する。"""

    if "mass_per_r2" not in df.columns:
        return
    working = df.copy()
    run_status = working.get("run_status")
    if run_status is not None:
        working = working[run_status.astype(str).str.lower() == "success"]
    if "case_status" in working.columns:
        working = working[working["case_status"].astype(str).str.lower() == BLOWOUT_STATUS]
    working = working[pd.to_numeric(working["mass_per_r2"], errors="coerce").notna()]
    working = working[working["mass_per_r2"] > 0.0]
    if working.empty:
        return

    x_label = (
        working["param_x_name"].dropna().iloc[0]
        if not working["param_x_name"].dropna().empty
        else "param_x"
    )
    y_label = (
        working["param_y_name"].dropna().iloc[0]
        if not working["param_y_name"].dropna().empty
        else "param_y"
    )

    x = pd.to_numeric(working["param_x_value"], errors="coerce")
    y = pd.to_numeric(working["mass_per_r2"], errors="coerce")
    color = pd.to_numeric(working["param_y_value"], errors="coerce")

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    sc = ax.scatter(x, y, c=color, cmap="viridis", s=24, edgecolor="none")
    ax.set_xlabel(x_label)
    ax.set_ylabel("M_loss / r^2 [M_Mars]")
    ax.set_title(f"{map_label}: M/r^2 分布")

    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label(f"{y_label} (K)")

    mean_val = float(np.mean(y)) if len(y) else math.nan
    if math.isfinite(mean_val):
        ax.axhline(mean_val, color="gray", linestyle="--", linewidth=1.0, label="全体平均")
        rel = float(np.max(np.abs(y - mean_val) / abs(mean_val))) if mean_val != 0.0 else math.nan
        if math.isfinite(rel):
            ax.text(0.02, 0.95, f"max|Δ|/mean = {rel:.3f}", transform=ax.transAxes, ha="left", va="top")

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="lower right")
    fig.tight_layout()
    output_path = Path("figures") / f"{map_stub}_mass_per_r2_scatter.png"
    ensure_directory(output_path.parent)
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"散布図を {output_path} に保存しました。")


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(None if argv is None else list(argv))

    try:
        map_stub, map_label = _normalise_map_key(args.map)
        df = load_csv(map_stub)
        pivot, failure_pivot, x_values, y_values, x_label, y_label = prepare_pivot(df, args.metric)
        metric_name_for_file = sanitize_metric_name(args.metric)
        output_path = Path("figures") / f"{map_stub}_{metric_name_for_file}.png"
        plt.rcParams.update({"font.size": 12})
        log_min, log_max = plot_heatmap(
            map_label,
            args.metric,
            pivot,
            failure_pivot,
            x_values,
            y_values,
            x_label,
            y_label,
            output_path,
        )
        print(
            f"ヒートマップを {output_path} に保存しました (log10範囲: {log_min:.3f} – {log_max:.3f})。"
        )
        if map_stub in {"map1", "map1b"} and args.metric == DEFAULT_METRIC:
            maybe_plot_mass_per_r2_scatter(df, map_stub, map_label)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"エラー: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
