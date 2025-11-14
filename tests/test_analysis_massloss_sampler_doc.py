from __future__ import annotations

from pathlib import Path


TARGET_HEADER = "### 感度掃引（質量損失サンプラー連携）"
DOC_PATH = Path("analysis/run-recipes.md")


def _slice_section(text: str, header: str) -> str:
    start = text.find(header)
    assert start != -1, f"Missing section header '{header}' in {DOC_PATH}"
    end = text.find("\n###", start + len(header))
    if end == -1:
        end = len(text)
    return text[start:end]


def test_massloss_sampler_section_lists_key_requirements() -> None:
    """Ensure the mass-loss sampler doc retains the agreed-upon content."""

    text = DOC_PATH.read_text(encoding="utf-8")
    section = _slice_section(text, TARGET_HEADER)

    required_terms = {
        "sample_mass_loss_one_orbit": "API名の明示",
        "summary.json": "サマリの再読み取り",
        "series/run.parquet": "タイムシリーズ再読み取り",
        "mass_budget_max_error_percent": "質量収支誤差指標",
        "sinks_mode": "シンク切替パラメータ",
        "--override": "override書式",
        "dt_over_t_blow": "タイムステップ制約",
    }
    for term, reason in required_terms.items():
        assert (
            term in section
        ), f"'{term}' ({reason}) が {TARGET_HEADER} 節から抜けています。"
