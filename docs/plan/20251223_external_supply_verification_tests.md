# 実装プラン：外部供給の検証テスト追加

## 目的
- 外部供給が run_zero_d の計算パスで適切に評価・適用されていることをテストで確認する。
- 供給ゲート、スケーリング、深層混合の回帰を早期に検出できるようにする。

## 背景 / 現状
- 供給は `evaluate_supply` -> `split_supply_with_deep_buffer` -> Smol で適用される。[marsdisk/physics/supply.py:176-495][marsdisk/run_zero_d.py:1986-2455]
- 外部供給のデフォルトは `optical_depth` + `mu_orbit10pct` + `epsilon_mix` + `transport=direct` で、`run_zero_d` が `mu_orbit10pct` から `prod_area_rate_kg_m2_s` を導出して供給率を決める。[marsdisk/run_zero_d.py:1180-1338]
- 既存テストは供給の単独関数やカラム存在、reservoir/feedback の一部を確認しているが、step 遅延や applied rate の整合を直接検証していない。
- `prod_subblow_area_rate_raw`/`supply_rate_*`/`prod_subblow_area_rate`/`prod_rate_into_deep` の関係を E2E で確認する必要がある。

## 対象範囲
- 0D run_zero_d の外部供給パス（供給評価、混合、深層バッファ、出力カラム）。
- デフォルト供給（`optical_depth` + `mu_orbit10pct` + `transport=direct`）の供給率スケーリングとゲート挙動。
- `supply.enabled` の無効化時のゼロ供給。

## 非対象
- 物理モデルや式の追加/変更。
- 1D 拡散や表層以外の供給パス。
- 供給関連の新しいスキーマ追加。

## 成功条件
- 新規テストが CI で安定し、`prod_subblow_area_rate` と `supply_rate_*` の関係が仕様どおり（デフォルト供給の `mu_orbit10pct` スケーリングを優先）。
- step 0 の供給遅延が明示的に検証される。
- `supply.enabled=false` のとき供給関連カラムがゼロ。
- テストは `collision_solver=smol` で統一され、`io.streaming.enable=false` で軽量に完走。

## テスト設計
### T1: デフォルト供給（mu_orbit10pct）パイプライン検証
- 概要: デフォルト供給（`optical_depth` + `mu_orbit10pct` + `transport=direct`）のスケーリングを Smol 経路で検証する。
- 期待値:
  - `dotSigma_target = mu_orbit10pct * orbit_fraction_at_mu1 * sigma_surf_mu_reference / t_orb` を `run_config.json` と `t_orb_s` から再計算できる。[marsdisk/run_zero_d.py:918-933][marsdisk/run_zero_d.py:1283-1338]
  - `supply_rate_nominal` と `supply_rate_scaled` が `dotSigma_target` に一致（温度/feedback/リザーバなし）。
  - `prod_subblow_area_rate_raw` は `dotSigma_target / epsilon_mix` に一致。
  - `supply_rate_applied == prod_subblow_area_rate`（`transport=direct` かつ headroom 無効で減衰なし）。
  - step 0 は `allow_supply_step` が false なので applied は 0。[marsdisk/run_zero_d.py:1986-2335]
- 構成メモ:
  - `configs/base.yml` をベースにし、短時間化と `io.streaming.enable=false` を上書きする。
  - 供給ゲートを安定化するため `phase.enabled=false` とし、Smol を前提に `surface.collision_solver=smol` を明示する。
  - `Sigma_surf` の増分まで検証する場合のみ `blowout.enabled=false` と `sinks.mode="none"` を併用する。

### T2: supply.enabled=false のゼロ供給
- 概要: `supply.enabled=false` にして `prod_subblow_area_rate` と `supply_rate_*` が全て 0 になることを確認。
- 期待値: `prod_subblow_area_rate`/`supply_rate_nominal`/`supply_rate_scaled`/`supply_rate_applied` が全行ゼロ。

## 実装タスク
- [ ] `tests/integration/test_external_supply_pipeline.py` を新規作成し、T1/T2 を追加。
- [ ] テストは `collision_solver=smol` で統一し、`io.streaming.enable=false` を強制。

## 影響範囲
- テスト追加のみ（実装コード変更なし）。
- 新規テストファイル: `tests/integration/test_external_supply_pipeline.py`.

## リスク / 注意点
- step 0 の `prod_subblow_area_rate_raw` は非ゼロになり得るため、applied との差を区別して検証する。
- `phase.enabled=true` だと供給がゲートされる可能性があるため、テストでは無効化する。
- Smol 経路では供給レートは出力カラムで検証し、`Sigma_surf` 増分は loss 無効化時のみ確認する。

## 参照
- 供給評価と深層バッファ: [marsdisk/physics/supply.py:176-495]
- デフォルト供給の導出（mu_orbit10pct）: [marsdisk/run_zero_d.py:1180-1338]
- 供給ゲートと run_zero_d への適用: [marsdisk/run_zero_d.py:1986-2455]
- Smol 供給注入（既存テストで補完）: [marsdisk/physics/collisions_smol.py:177-260]
