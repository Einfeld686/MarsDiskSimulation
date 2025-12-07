"""Planck 平均 Q_pr テーブル生成ユーティリティの互換ラッパー."""

from __future__ import annotations

from marsdisk.ops.make_qpr_table import (  # noqa: F401
    compute_planck_mean_qpr,
    main,
)

__all__ = ["compute_planck_mean_qpr", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
