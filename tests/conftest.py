from __future__ import annotations

import sys
import os
import pytest
from pathlib import Path

os.environ["NUMBA_NUM_THREADS"] = "1"  # Keep Numba thread count stable across tests.

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STREAMING_OVERRIDES = {"io.streaming.enable": False}
TESTS_ROOT = ROOT / "tests"


def _env_flag(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v in {"1", "true", "yes", "on", "enable", "enabled"}:
        return True
    if v in {"0", "false", "no", "off", "disable", "disabled"}:
        return False
    return None


def _classify_test_path(path: Path) -> str | None:
    try:
        rel = path.relative_to(TESTS_ROOT)
    except ValueError:
        return None
    if not rel.parts:
        return None
    top = rel.parts[0]
    if top in {"unit", "integration", "research", "legacy"}:
        return top
    return None


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--no-streaming",
        action="store_true",
        default=False,
        help="Force FORCE_STREAMING_OFF=1 during tests to keep streaming disabled.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        category = _classify_test_path(Path(str(item.fspath)))
        if category is None:
            continue
        item.add_marker(getattr(pytest.mark, category))


@pytest.fixture(autouse=True)
def _force_streaming_off_by_default(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Keep streaming disabled in tests unless explicitly opted in."""

    force_off = bool(request.config.getoption("--no-streaming"))
    env_force_off = _env_flag(os.environ.get("FORCE_STREAMING_OFF"))
    env_force_on = _env_flag(os.environ.get("FORCE_STREAMING_ON"))
    io_streaming_flag = _env_flag(os.environ.get("IO_STREAMING"))

    if env_force_off is True or io_streaming_flag is False:
        force_off = True
    if env_force_on is True or io_streaming_flag is True:
        force_off = False

    # Default: force streaming off for tests to reduce I/O unless explicitly enabled.
    if force_off or (env_force_off is None and env_force_on is None and io_streaming_flag is None):
        monkeypatch.setenv("FORCE_STREAMING_OFF", "1")
