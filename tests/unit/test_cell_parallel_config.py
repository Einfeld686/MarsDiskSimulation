from __future__ import annotations

import pytest

from marsdisk import run_one_d


@pytest.mark.parametrize(
    "payload, expected_reason",
    [
        (
            {
                "os_name": "nt",
                "n_cells": 8,
                "cell_parallel_requested": False,
                "cell_jobs_requested": 4,
                "cell_min_cells": 4,
                "cell_chunk_size_raw": 0,
                "cell_coupling_enabled": False,
            },
            "not_requested",
        ),
        (
            {
                "os_name": "posix",
                "n_cells": 8,
                "cell_parallel_requested": True,
                "cell_jobs_requested": 4,
                "cell_min_cells": 4,
                "cell_chunk_size_raw": 0,
                "cell_coupling_enabled": False,
            },
            "non_windows",
        ),
        (
            {
                "os_name": "nt",
                "n_cells": 2,
                "cell_parallel_requested": True,
                "cell_jobs_requested": 4,
                "cell_min_cells": 4,
                "cell_chunk_size_raw": 0,
                "cell_coupling_enabled": False,
            },
            "too_few_cells",
        ),
        (
            {
                "os_name": "nt",
                "n_cells": 8,
                "cell_parallel_requested": True,
                "cell_jobs_requested": 4,
                "cell_min_cells": 4,
                "cell_chunk_size_raw": 0,
                "cell_coupling_enabled": True,
            },
            "cell_coupling_enabled",
        ),
        (
            {
                "os_name": "nt",
                "n_cells": 8,
                "cell_parallel_requested": True,
                "cell_jobs_requested": 1,
                "cell_min_cells": 4,
                "cell_chunk_size_raw": 0,
                "cell_coupling_enabled": False,
            },
            "single_job",
        ),
    ],
)
def test_cell_parallel_disabled_reasons(payload: dict[str, object], expected_reason: str) -> None:
    config = run_one_d._resolve_cell_parallel_config(**payload)

    assert config["enabled"] is False
    assert config["reason"] == expected_reason


def test_cell_parallel_job_capping_and_auto_chunking() -> None:
    config = run_one_d._resolve_cell_parallel_config(
        os_name="nt",
        n_cells=5,
        cell_parallel_requested=True,
        cell_jobs_requested=10,
        cell_min_cells=1,
        cell_chunk_size_raw=0,
        cell_coupling_enabled=False,
    )

    assert config["enabled"] is True
    assert config["jobs_effective"] == 5
    assert config["chunk_mode"] == "auto"
    assert config["chunk_size"] == 1


def test_cell_parallel_fixed_chunk_size() -> None:
    config = run_one_d._resolve_cell_parallel_config(
        os_name="nt",
        n_cells=10,
        cell_parallel_requested=True,
        cell_jobs_requested=3,
        cell_min_cells=1,
        cell_chunk_size_raw=2,
        cell_coupling_enabled=False,
    )

    assert config["enabled"] is True
    assert config["chunk_mode"] == "fixed"
    assert config["chunk_size"] == 2
