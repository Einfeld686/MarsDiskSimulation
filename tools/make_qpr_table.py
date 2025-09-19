"""Planck 平均の放射圧効率テーブルを生成するユーティリティ。Planck 平均⟨Q_pr⟩."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

# Physical constants in SI units
PLANCK = 6.62607015e-34  # J s
LIGHT_SPEED = 2.99792458e8  # m s^-1
BOLTZMANN = 1.380649e-23  # J K^-1
HC_OVER_K = PLANCK * LIGHT_SPEED / BOLTZMANN

WAVELENGTH_MIN_UM = 0.5
WAVELENGTH_MAX_UM = 30.0
DEFAULT_WAVELENGTH_SAMPLES = 512


def _rayleigh_geometric_qpr(size_parameter: np.ndarray) -> np.ndarray:
    """Rayleighと幾何光学をつなぐQ_pr曲線を計算する。Rayleigh–幾何 Q_pr."""
    x = np.asarray(size_parameter, dtype=float)
    return x**4 / (1.0 + x**4)


def _planck_lambda(wavelength_m: np.ndarray, temperature: float) -> np.ndarray:
    """黒体放射スペクトルの強度を計算する。Planck 分布B_λ."""
    lam = np.asarray(wavelength_m, dtype=float)
    if np.any(lam <= 0.0):
        raise ValueError("Wavelength values must be positive for Planck spectrum")
    if temperature <= 0.0:
        raise ValueError("Temperature must be positive for Planck spectrum")
    exponent = HC_OVER_K / (lam * temperature)
    intensity = (2.0 * PLANCK * LIGHT_SPEED**2) / (lam**5 * np.expm1(exponent))
    return intensity


def compute_planck_mean_qpr(
    s_values: Sequence[float],
    temperatures: Sequence[float],
    wavelengths_um: Iterable[float] | None = None,
) -> np.ndarray:
    """粒径と温度のグリッドでPlanck平均Q_prを計算する。Planck 平均⟨Q_pr⟩."""
    s_arr = np.asarray(s_values, dtype=float)
    T_arr = np.asarray(temperatures, dtype=float)
    if s_arr.ndim != 1:
        raise ValueError("Input s_values must be one-dimensional")
    if T_arr.ndim != 1:
        raise ValueError("Input temperatures must be one-dimensional")
    if np.any(s_arr <= 0.0):
        raise ValueError("Grain sizes must be positive")
    if np.any(T_arr <= 0.0):
        raise ValueError("Temperatures must be positive")
    if wavelengths_um is None:
        wavelengths_um = np.geomspace(
            WAVELENGTH_MIN_UM, WAVELENGTH_MAX_UM, DEFAULT_WAVELENGTH_SAMPLES
        )
    lam_um = np.asarray(list(wavelengths_um), dtype=float)
    if lam_um.ndim != 1 or lam_um.size == 0:
        raise ValueError("Wavelength grid must be one-dimensional and non-empty")
    if np.any(lam_um <= 0.0):
        raise ValueError("Wavelength grid must have positive values")
    lam_m = lam_um * 1.0e-6

    size_parameter = (2.0 * np.pi * s_arr[:, None]) / lam_m[None, :]
    q_lambda = _rayleigh_geometric_qpr(size_parameter)

    result = np.empty((T_arr.size, s_arr.size), dtype=float)
    for idx, T in enumerate(T_arr):
        spectrum = _planck_lambda(lam_m, float(T))
        denominator = np.trapezoid(spectrum, lam_m)
        if denominator <= 0.0:
            raise ValueError("Planck spectrum integral must be positive")
        numerator = np.trapezoid(q_lambda * spectrum[None, :], lam_m, axis=1)
        result[idx, :] = numerator / denominator
    return result


def _parse_temperatures(raw: str) -> np.ndarray:
    """カンマ区切り文字列から温度配列を作る。Planck 平均⟨Q_pr⟩."""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("At least one temperature must be provided")
    try:
        temps = np.array([float(p) for p in parts], dtype=float)
    except ValueError as exc:
        raise ValueError(f"Temperatures must be numeric: {raw}") from exc
    if np.any(temps <= 0.0):
        raise ValueError("Temperatures must be positive")
    return temps


def _build_size_grid(s_min: float, s_max: float, count: int) -> np.ndarray:
    """粒径の対数グリッドを生成する。Planck 平均⟨Q_pr⟩."""
    if s_min <= 0.0 or s_max <= 0.0:
        raise ValueError("s_min and s_max must be positive")
    if s_max <= s_min:
        raise ValueError("s_max must be larger than s_min")
    if count < 2:
        raise ValueError("Ns must be at least 2 to form a grid")
    return np.geomspace(s_min, s_max, count)


def _write_hdf5(path: Path, qpr: np.ndarray, log10s: np.ndarray, temperatures: np.ndarray) -> None:
    """Planck平均Q_prテーブルをHDF5に保存する。Planck 平均⟨Q_pr⟩."""
    try:
        import h5py
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ValueError("h5py is required to write HDF5 output") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as h5file:
        h5file.create_dataset("qpr", data=qpr)
        h5file.create_dataset("log10s", data=log10s)
        h5file.create_dataset("T", data=temperatures)


def main(argv: Sequence[str] | None = None) -> None:
    """コマンドライン引数でQ_prテーブルを生成する。Planck 平均⟨Q_pr⟩."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s-min", type=float, required=True, help="最小粒径 [m]")
    parser.add_argument("--s-max", type=float, required=True, help="最大粒径 [m]")
    parser.add_argument("--Ns", type=int, required=True, help="粒径分割数")
    parser.add_argument(
        "--T",
        type=str,
        required=True,
        help="カンマ区切りの温度リスト [K]",
    )
    parser.add_argument("--out", type=str, required=True, help="出力HDF5パス")
    args = parser.parse_args(argv)

    temperatures = _parse_temperatures(args.T)
    sizes = _build_size_grid(args.s_min, args.s_max, args.Ns)
    qpr = compute_planck_mean_qpr(sizes, temperatures)
    log10s = np.log10(sizes)

    output_path = Path(args.out)
    _write_hdf5(output_path, qpr, log10s, temperatures)


if __name__ == "__main__":
    main()
