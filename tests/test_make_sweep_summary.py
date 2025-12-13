"""Tests for tools.plotting.make_sweep_summary module."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def mock_batch_dir(tmp_path: Path) -> Path:
    """Create a mock batch directory with minimal sweep structure."""
    cases = [
        ("T6000_mu1p0_phi20", {"M_loss": 1.5e-10, "supply_clip_time_fraction": 0.05}),
        ("T6000_mu0p5_phi20", {"M_loss": 0.8e-10, "supply_clip_time_fraction": 0.10}),
        ("T4000_mu1p0_phi20", {"M_loss": 0.5e-10, "supply_clip_time_fraction": 0.02}),
    ]
    for name, summary_data in cases:
        case_dir = tmp_path / name
        case_dir.mkdir()
        summary_path = case_dir / "summary.json"
        summary_path.write_text(json.dumps(summary_data))
    return tmp_path


def test_parse_dir_name():
    """Test directory name parsing for T, mu, phi extraction."""
    from tools.plotting.make_sweep_summary import parse_dir_name

    # Standard format
    result = parse_dir_name("T6000_mu1p0_phi20")
    assert result is not None
    T, mu, phi = result
    assert T == 6000.0
    assert mu == 1.0
    assert phi == 0.20

    # Decimal format
    result = parse_dir_name("T4000_mu0p5_phi37")
    assert result is not None
    T, mu, phi = result
    assert T == 4000.0
    assert mu == 0.5
    assert phi == 0.37

    # Invalid format
    result = parse_dir_name("invalid_dir_name")
    assert result is None


def test_discover_cases(mock_batch_dir: Path):
    """Test case discovery from batch directory."""
    from tools.plotting.make_sweep_summary import discover_cases

    cases = discover_cases(mock_batch_dir)
    assert len(cases) == 3

    # Check that M_loss was loaded
    mloss_values = [c.M_loss for c in cases]
    assert 1.5e-10 in mloss_values


def test_cases_to_dataframe(mock_batch_dir: Path):
    """Test conversion of cases to DataFrame."""
    from tools.plotting.make_sweep_summary import cases_to_dataframe, discover_cases

    cases = discover_cases(mock_batch_dir)
    df = cases_to_dataframe(cases)

    assert "T_M" in df.columns
    assert "epsilon_mix" in df.columns
    assert "phi" in df.columns
    assert "M_loss" in df.columns
    assert "supply_clip_time_fraction" in df.columns
    assert len(df) == 3


def test_main_csv_output(mock_batch_dir: Path):
    """Test main function produces CSV output."""
    from tools.plotting.make_sweep_summary import main

    result = main(["--batch-dir", str(mock_batch_dir), "--no-plots"])
    assert result == 0

    csv_path = mock_batch_dir / "sweep_summary.csv"
    assert csv_path.exists()

    import pandas as pd
    df = pd.read_csv(csv_path)
    assert len(df) == 3


def test_empty_batch_dir(tmp_path: Path):
    """Test handling of empty batch directory."""
    from tools.plotting.make_sweep_summary import main

    result = main(["--batch-dir", str(tmp_path), "--no-plots"])
    # Should return 0 (warning, not error) for empty directory
    assert result == 0


def test_missing_summary_json(tmp_path: Path):
    """Test handling of case directory without summary.json."""
    from tools.plotting.make_sweep_summary import discover_cases

    # Create directory with valid name but no summary.json
    case_dir = tmp_path / "T6000_mu1p0_phi20"
    case_dir.mkdir()

    cases = discover_cases(tmp_path)
    assert len(cases) == 1
    # M_loss should be NaN since no summary.json
    assert cases[0].M_loss != cases[0].M_loss  # NaN check
