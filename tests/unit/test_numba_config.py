from __future__ import annotations

from marsdisk.runtime.numba_config import numba_disabled_env


def test_numba_disabled_env_prefers_new_variable(monkeypatch) -> None:
    monkeypatch.setenv("MARSDISK_DISABLE_NUMBA", "1")
    monkeypatch.setenv("MARSDISK_NUMBA_DISABLE", "0")
    assert numba_disabled_env() is False

    monkeypatch.setenv("MARSDISK_NUMBA_DISABLE", "1")
    assert numba_disabled_env() is True


def test_numba_disabled_env_compat_variable(monkeypatch) -> None:
    monkeypatch.delenv("MARSDISK_NUMBA_DISABLE", raising=False)
    monkeypatch.setenv("MARSDISK_DISABLE_NUMBA", "1")
    assert numba_disabled_env() is True
