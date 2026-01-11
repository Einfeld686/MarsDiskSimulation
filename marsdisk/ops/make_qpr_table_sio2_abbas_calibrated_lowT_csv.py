"""make_qpr_table_sio2_abbas_calibrated_lowT_csv.py

SiO2 を想定した Planck 平均 <Q_pr> テーブル（CSV）を生成する。

狙い
----
- Abbas et al. (2003) の Table 1（λ=0.5320 µm）にある SiO2 粒子の測定 Q_pr を
  単色校正点として使い、Q_pr>1 も許すようにモデルを拡張する。
- 生成するのは、(T_M, s) の 2 次元格子上の Planck 平均 <Q_pr> を「縦持ち CSV」で出力したもの。

モデル
------
単色モデル（経験式）:
    Q_pr(λ, s) = A * x^n / (1 + x^n),   x = 2π s / λ

校正:
    Abbas Table 1 の size parameter x=8.80 に対して Q_pr=1.12 となるように A を決める。
    n は --exponent で変更可能。

温度
----
--grid-csv を指定した場合:
    その CSV に含まれる温度に、--T-extra で与えた温度（既定: 300–1900 K）を追加して計算する。

出力
----
列: T_M,s,Q_pr

使い方（例）
------------
python make_qpr_table_sio2_abbas_calibrated_lowT_csv.py \
    --grid-csv qpr_planck.csv \
    --out qpr_planck_sio2_abbas_calibrated_lowT.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

# Physical constants in SI units
PLANCK = 6.62607015e-34  # J s
LIGHT_SPEED = 2.99792458e8  # m s^-1
BOLTZMANN = 1.380649e-23  # J K^-1
HC_OVER_K = PLANCK * LIGHT_SPEED / BOLTZMANN

DEFAULT_WAVELENGTH_MIN_UM = 0.5
DEFAULT_WAVELENGTH_MAX_UM = 200.0
DEFAULT_WAVELENGTH_SAMPLES = 1024

# Abbas et al. (2003) Table 1 (SiO2, λ=0.5320 µm) calibration
DEFAULT_CAL_X = 8.8         # size parameter x (Table 1)
DEFAULT_CAL_QPR = 1.12     # measured Q_pr (Table 1)
DEFAULT_EXPONENT = 3.0

DEFAULT_T_EXTRA = "300,500,700,900,1000,1300,1600,1900"


def _planck_lambda(wavelength_m: np.ndarray, temperature: float) -> np.ndarray:
    lam = np.asarray(wavelength_m, dtype=float)
    exponent = HC_OVER_K / (lam * temperature)
    return (2.0 * PLANCK * LIGHT_SPEED**2) / (lam**5 * np.expm1(exponent))


def _qpr_model(size_parameter: np.ndarray, amplitude: float, exponent: float) -> np.ndarray:
    x = np.asarray(size_parameter, dtype=float)
    x_pow = x**exponent
    return amplitude * (x_pow / (1.0 + x_pow))


def _calibrate_amplitude(exponent: float, x_cal: float, qpr_cal: float) -> float:
    base = (x_cal**exponent) / (1.0 + x_cal**exponent)
    if base <= 0.0:
        raise ValueError("Calibration base value must be positive")
    return float(qpr_cal / base)


def _read_grid_from_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    table_path = Path(path)
    suffix = table_path.suffix.lower()
    if suffix == ".csv":
        parquet_path = table_path.with_suffix(".parquet")
        if parquet_path.exists():
            if not table_path.exists() or parquet_path.stat().st_mtime >= table_path.stat().st_mtime:
                table_path = parquet_path
    elif suffix in {".parquet", ".pq"} and not table_path.exists():
        csv_path = table_path.with_suffix(".csv")
        if csv_path.exists():
            table_path = csv_path
    if table_path.suffix.lower() in {".parquet", ".pq"}:
        df = pd.read_parquet(table_path, columns=["T_M", "s"])
        if df.empty:
            raise ValueError("Input table is empty")
        T_values = np.unique(df["T_M"].to_numpy(dtype=float))
        s_values = np.unique(df["s"].to_numpy(dtype=float))
    else:
        data = np.genfromtxt(table_path, delimiter=",", names=True, dtype=None, encoding=None)
        if data.size == 0:
            raise ValueError("Input CSV is empty")
        if "T_M" not in data.dtype.names or "s" not in data.dtype.names:
            raise ValueError("Input CSV must have columns: T_M, s")
        T_values = np.unique(data["T_M"].astype(float))
        s_values = np.unique(data["s"].astype(float))
    T_values.sort()
    s_values.sort()
    return T_values, s_values


def _parse_list(raw: str) -> np.ndarray:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    vals = np.array([float(p) for p in parts], dtype=float)
    if np.any(vals <= 0.0):
        raise ValueError("All values must be positive")
    return vals


def compute_planck_mean_qpr(
    s_values: Sequence[float],
    temperatures: Sequence[float],
    amplitude: float,
    exponent: float,
    wavelengths_um: Iterable[float],
) -> np.ndarray:
    s_arr = np.asarray(s_values, dtype=float)
    T_arr = np.asarray(temperatures, dtype=float)
    lam_um = np.asarray(list(wavelengths_um), dtype=float)
    lam_m = lam_um * 1.0e-6

    x = (2.0 * np.pi * s_arr[:, None]) / lam_m[None, :]
    q_lambda = _qpr_model(x, amplitude=amplitude, exponent=exponent)

    out = np.empty((T_arr.size, s_arr.size), dtype=float)
    for i, T in enumerate(T_arr):
        B = _planck_lambda(lam_m, float(T))
        denom = np.trapz(B, lam_m)
        numer = np.trapz(q_lambda * B[None, :], lam_m, axis=1)
        out[i, :] = numer / denom
    return out


def _write_csv(path: Path, T_values: np.ndarray, s_values: np.ndarray, qpr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("T_M,s,Q_pr\n")
        for i, T in enumerate(T_values):
            for j, s in enumerate(s_values):
                f.write(f"{T},{s},{qpr[i, j]}\n")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid-csv", type=str, required=True, help="既存の qpr_planck.csv（格子の読み取りに使用）")
    parser.add_argument("--out", type=str, required=True, help="出力 CSV パス")

    parser.add_argument("--exponent", type=float, default=DEFAULT_EXPONENT, help="モデル指数 n")
    parser.add_argument("--cal-x", type=float, default=DEFAULT_CAL_X, help="Abbas Table 1 の size parameter x（校正点）")
    parser.add_argument("--cal-qpr", type=float, default=DEFAULT_CAL_QPR, help="Abbas Table 1 の measured Q_pr（校正点）")
    parser.add_argument("--T-extra", type=str, default=DEFAULT_T_EXTRA, help="追加する温度（カンマ区切り）")

    parser.add_argument("--wavelength-min-um", type=float, default=DEFAULT_WAVELENGTH_MIN_UM)
    parser.add_argument("--wavelength-max-um", type=float, default=DEFAULT_WAVELENGTH_MAX_UM)
    parser.add_argument("--wavelength-samples", type=int, default=DEFAULT_WAVELENGTH_SAMPLES)

    args = parser.parse_args(argv)

    T_grid, s_grid = _read_grid_from_csv(Path(args.grid_csv))
    T_extra = _parse_list(args.T_extra)
    T_values = np.unique(np.concatenate([T_grid, T_extra]))
    T_values.sort()

    wavelengths_um = np.geomspace(
        float(args.wavelength_min_um),
        float(args.wavelength_max_um),
        int(args.wavelength_samples),
    )

    amplitude = _calibrate_amplitude(
        exponent=float(args.exponent),
        x_cal=float(args.cal_x),
        qpr_cal=float(args.cal_qpr),
    )

    qpr = compute_planck_mean_qpr(
        s_values=s_grid,
        temperatures=T_values,
        amplitude=amplitude,
        exponent=float(args.exponent),
        wavelengths_um=wavelengths_um,
    )

    _write_csv(Path(args.out), T_values, s_grid, qpr)
    print(f"amplitude A = {amplitude}")
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()
