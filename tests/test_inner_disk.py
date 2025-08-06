"""内側円盤の質量指定オプションを検証するテスト."""

from importlib import util
from pathlib import Path
import hashlib
import numpy as np
import sys
import pytest

# モジュールの読み込み
step1_path = Path(__file__).resolve().parents[1] / "Step1"
sys.path.append(str(step1_path))
spec_map = util.spec_from_file_location(
    "ext_map", step1_path / "extended_static_map.py"
)
mod_map = util.module_from_spec(spec_map)
spec_map.loader.exec_module(mod_map)

R_MARS = mod_map.R_MARS
M_MARS = mod_map.M_MARS


def test_sigma_inner_from_mass(monkeypatch):
    """M_inner から Σ_inner を逆算できるか."""
    area = np.pi * ((2.7 * R_MARS) ** 2 - (2.6 * R_MARS) ** 2)
    mass = 5e3 * area / M_MARS
    monkeypatch.setattr(sys, "argv", ["prog", "--M_inner", str(mass), "--testmode"])
    args = mod_map.parse_args()
    sigma = mod_map.sigma_piecewise(args.r_min, args)
    assert np.isclose(sigma, 5e3), "Σ_inner の逆算に失敗"


def test_inner_exclusive(monkeypatch):
    """Σ_inner と M_inner の同時指定はエラー"""
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--Sigma_inner", "5e3", "--M_inner", "1e-7"],
    )
    with pytest.raises(SystemExit):
        mod_map.parse_args()


def test_default_output_hash(monkeypatch, tmp_path):
    """デフォルト設定の出力 SHA256 が変わらない"""
    monkeypatch.setattr(sys, "argv", ["prog", "--testmode"])
    args = mod_map.parse_args()
    monkeypatch.chdir(tmp_path)
    mod_map.run_batch(args)
    csv_path = Path("output/extended_disk_map_r2.6R.csv")
    h = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert (
        h == "50edd50a0fe4c4bb207069184fd8d5b6fbc1ce8c08bc205c442a0747ae17f922"
    ), "既定出力のハッシュが変化"
