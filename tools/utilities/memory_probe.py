"""簡易メモリ試算ツール。

Config を読み込み、0D ループが何ステップ走るかと主な出力量の行数・概算メモリを
事前に見積もる。run_zero_d と同じ時間グリッド解決ロジックと n_bins を用いるため、
実行前に「この設定では何十 GB になるか」を素早く確認できる。
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Iterable, Tuple

from marsdisk import constants, grid, run

SECONDS_PER_YEAR = 365.25 * 24.0 * 3600.0

DEFAULT_RUN_ROW_BYTES = 2200.0  # run.parquet の 1 行あたり概算（dict/listオーバーヘッド込み）
DEFAULT_PSD_ROW_BYTES = 320.0   # psd_hist.parquet の 1 行あたり概算（dict/listオーバーヘッド込み）


def _human_bytes(value: float) -> str:
    """人間可読のバイト表記に整形する。"""

    units = ("B", "KB", "MB", "GB", "TB", "PB")
    amount = float(value)
    for unit in units:
        if abs(amount) < 1024.0:
            return f"{amount:,.2f} {unit}"
        amount /= 1024.0
    return f"{amount:,.2f} EB"


def _resolve_radius(cfg: object) -> Tuple[float, str]:
    """run_zero_d と同じ優先順位で軌道半径を決定する。"""

    if getattr(cfg, "geometry", None) and cfg.geometry.r is not None:
        return float(cfg.geometry.r), "geometry.r"
    if getattr(cfg, "geometry", None) and getattr(cfg.geometry, "runtime_orbital_radius_rm", None) is not None:
        r = float(cfg.geometry.runtime_orbital_radius_rm) * constants.R_MARS
        return r, "geometry.runtime_orbital_radius_rm"
    if getattr(cfg, "disk", None) is not None:
        geo = cfg.disk.geometry
        r_rm = 0.5 * (geo.r_in_RM + geo.r_out_RM)
        return float(r_rm * constants.R_MARS), "disk.geometry"
    if getattr(cfg, "geometry", None) and getattr(cfg.geometry, "r_in", None) is not None:
        return float(cfg.geometry.r_in), "geometry.r_in"
    raise ValueError("geometry.r も disk.geometry も指定されていません")


def _estimate_memory(rows: int, bytes_per_row: float) -> float:
    return float(rows) * float(bytes_per_row)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="0D シミュレーションのステップ数と概算メモリを事前試算するヘルパー"
    )
    parser.add_argument("--config", type=Path, required=True, help="YAML 設定ファイルへのパス")
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="marsdisk.run と同じ key=value 形式の上書き設定。複数指定可。",
    )
    parser.add_argument(
        "--run-row-bytes",
        type=float,
        default=DEFAULT_RUN_ROW_BYTES,
        help="run.parquet 1 行あたりの概算バイト数（既定: 1400）。",
    )
    parser.add_argument(
        "--psd-row-bytes",
        type=float,
        default=DEFAULT_PSD_ROW_BYTES,
        help="psd_hist.parquet 1 行あたりの概算バイト数（既定: 40）。",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg = run.load_config(args.config, overrides=args.override)

    r, r_source = _resolve_radius(cfg)
    Omega = grid.omega_kepler(r)
    if Omega <= 0.0:
        raise ValueError("Kepler 角周波数が 0 以下です")
    t_orb = 2.0 * math.pi / Omega

    t_end, dt_nominal, dt_step, n_steps_raw, tg_info = run._resolve_time_grid(
        cfg.numerics, Omega, t_orb
    )
    n_steps = n_steps_raw
    dt_effective = dt_step
    if n_steps > run.MAX_STEPS:
        n_steps = run.MAX_STEPS
        dt_effective = t_end / n_steps

    n_bins = int(getattr(cfg.sizes, "n_bins", 0) or 0)
    run_rows = int(n_steps)
    psd_rows = run_rows * n_bins

    run_mem = _estimate_memory(run_rows, args.run_row_bytes)
    psd_mem = _estimate_memory(psd_rows, args.psd_row_bytes)
    smol_mem = 8.0 * (n_bins**2 + n_bins**3)  # C(n^2) + Y(n^3) を float64 前提で計算
    total_mem = run_mem + psd_mem + smol_mem

    print("=== メモリ試算 ===")
    print(f"config: {args.config}")
    print(f"radius: {r:,.3f} m  (source: {r_source})")
    print(f"Omega: {Omega:.6e} s^-1, T_orb: {t_orb:,.3f} s")
    print(f"t_end: {t_end:,.3f} s ({t_end/SECONDS_PER_YEAR:.3f} yr)")
    if n_steps != n_steps_raw:
        print(f"dt: {dt_effective:.6g} s (MAX_STEPS={run.MAX_STEPS:,} で上限適用)")
        print(f"n_steps: {n_steps:,} (元の計算では {n_steps_raw:,})")
    else:
        print(f"dt: {dt_effective:.6g} s (dt_init={dt_nominal:.6g})")
        print(f"n_steps: {n_steps:,}")
    print(f"PSD bins: {n_bins:,}")
    print("--- 行数の見積もり ---")
    print(f"run.parquet rows        : {run_rows:,}")
    print(f"psd_hist.parquet rows   : {psd_rows:,} (= n_steps * n_bins)")
    print("--- メモリ概算（Python オブジェクト + Parquet 生成前のバッファ想定） ---")
    print(f"run.parquet   ~ {_human_bytes(run_mem)} (1 行あたり {args.run_row_bytes:.0f} B 仮定)")
    print(f"psd_hist      ~ {_human_bytes(psd_mem)} (1 行あたり {args.psd_row_bytes:.0f} B 仮定)")
    print(f"Smol tensors  ~ {_human_bytes(smol_mem)} (C + Y を float64 で保持する場合)")
    print(f"合計（run + psd_hist + smol）~ {_human_bytes(total_mem)}")
    print("--- 注意 ---")
    print("ここでのバイト数は DataFrame/辞書のオーバーヘッドを含む概算です。実際のピークはやや大きくなります。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
