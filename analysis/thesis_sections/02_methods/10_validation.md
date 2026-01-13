### 6.2 検証手順

#### 6.2.1 ユニットテスト

```bash
pytest tests/ -q
```

主要テストは analysis/run-recipes.md §検証チェックリスト を参照。特に以下でスケールと安定性を確認する。

- Wyatt/Strubbe–Chiang 衝突寿命スケール: `pytest tests/integration/test_scalings.py::test_strubbe_chiang_collisional_timescale_matches_orbit_scaling`
- Blow-out 起因 “wavy” PSD の再現: `pytest tests/integration/test_surface_outflux_wavy.py::test_blowout_driven_wavy_pattern_emerges`
- IMEX-BDF(1) の $\Delta t$ 制限と質量保存: `pytest tests/integration/test_mass_conservation.py::test_imex_bdf1_limits_timestep_and_preserves_mass`
- 1D セル並列の on/off 一致確認（Windowsのみ）: `pytest tests/integration/test_numerical_anomaly_watchlist.py::test_cell_parallel_on_off_consistency`
- 質量収支ログ: `out/checks/mass_budget.csv` で |error| ≤ 0.5% を確認（C4）

検証では、$t_{\rm coll}$ スケールが理論式のオーダーと一致すること、$\Delta t$ の制約が安定性を満たすこと、ブローアウト近傍で wavy 構造が再現されることを確認する。これらの基準は設定変更後の回帰検証にも適用する。

#### 6.2.2 実行後の数値チェック（推奨）

- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内であること。
- `series/run.parquet` の `dt_over_t_blow` が 1 未満に収まっているかを確認し、超過時は `fast_blowout_flag_*` と併せて評価する。
- 衝突が有効なケースでは `smol_dt_eff < dt` が成立し、`t_coll_kernel_min` と一貫しているかを確認する。

#### 6.2.3 ドキュメント整合性

```bash
make analysis-sync      # DocSync
make analysis-doc-tests # アンカー健全性・参照率検査
python -m tools.evaluation_system --outdir <run_dir>  # Doc 更新後に直近の out/* を指定
```

> **詳細**: analysis/overview.md §16 "DocSync/検証フローの固定"

---
