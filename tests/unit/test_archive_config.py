from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from marsdisk.run_zero_d import load_config


def _base_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "base.yml"


def test_archive_requires_dir_when_enabled() -> None:
    config_path = _base_config_path()
    with pytest.raises(ValidationError):
        load_config(config_path, overrides=["io.archive.enabled=true"])


def test_archive_accepts_dir_when_enabled(tmp_path: Path) -> None:
    config_path = _base_config_path()
    cfg = load_config(
        config_path,
        overrides=[
            "io.archive.enabled=true",
            f"io.archive.dir={tmp_path}",
        ],
    )
    assert cfg.io.archive.enabled is True
    assert cfg.io.archive.dir is not None
