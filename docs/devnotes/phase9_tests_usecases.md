# フェーズ9 テストとユースケース（内側円盤・単一過程比較）

## 目的
- 研究者が **「昇華のみ（経路A）」** と **「衝突カスケード＋火星放射圧ブローアウトのみ（経路B）」** を **同一の時間グリッドで別々に走らせ、2 年スケールの質量損失を比較**できるようにする。
- スコープは内側円盤固定・火星放射限定で、`physics_mode` の解決結果を `primary_process` / `primary_scenario` として出力メタデータに残す。[marsdisk/run.py:575–695][marsdisk/run.py:2142–2352][marsdisk/run.py:2429–2535]

## 適用範囲と既知の限界
- 対象は `scope.region="inner"` の 0D 内側円盤のみ。外側円盤や半径方向輸送は含まない。[marsdisk/run.py:575–695]
- 時間窓は `scope.analysis_years`（既定 2 年）で、`numerics.t_end_*` 未指定ならこの値が時間軸に書き戻される。[marsdisk/run.py:575–695][marsdisk/run.py:2142–2189]
- 放射圧は火星のみ。`use_solar_rp` は常に無効記録され、`summary` / `run_config` に Mars-only として残る。[marsdisk/run.py:664–920][marsdisk/run.py:2333–2345][marsdisk/run.py:2507–2515]
- 衝突カスケード×昇華×ブローアウトの同時解はサポートせず、**経路A と経路B を別ランで比較する運用前提**（`physics_mode` を切り替えた個別ラン＋extended_diagnostics でログ）。[marsdisk/run.py#run_zero_d][docs/devnotes/phase7_minimal_diagnostics.md]

## 仕様（What）
### フラグと有効/無効の整理（A1）
| シナリオ | collisions_active / blowout | sinks_active / sublimation | 備考 |
| --- | --- | --- | --- |
| sublimation_only | OFF → `blowout_active=false` | ON（昇華・ガス抗力） | `summary.primary_process="sublimation_only"`、`M_out_dot` 系は 0。[marsdisk/run.py:575–915][marsdisk/run.py:2142–2352] |
| collisions_only | ON（火星RP gateあり） | OFF（`sinks` 無効化） | `summary.primary_process="collisions_only"`、`M_loss_from_sinks=0`。[marsdisk/run.py:575–915][marsdisk/run.py:2142–2352] |
| combined/off | ON | ON | 従来挙動と同一。後方互換のため既存 YAML/Phase5 比較は変わらない。 |

### 出力メタデータ（A2）
- `summary.json`: `M_loss` / `M_out_cum` / `M_sink_cum`、`primary_process` / `primary_scenario`、`collisions_active` / `sinks_active` / `sublimation_active` / `blowout_active`、`inner_disk_scope`、`analysis_window_years`、`radiation_field`、`time_grid.*`、`solar_radiation.enabled=false` を必須とする。[marsdisk/run.py:2142–2352]
- `run_config.json`: `process_controls` / `process_overview` / `scope_controls` / `radiation_provenance` / `time_grid` に上記フラグと Mars-only 設定を保持する。[marsdisk/run.py:2429–2535]

## テスト観点（A3）
- A1-1 昇華のみ整合性: ブローアウト由来列が 0、`collisions_active=false`、primary が sublimation を指すことを確認。[tests/test_phase9_usecases.py:65–84]
- A1-2 衝突のみ整合性: `sinks_active=false`、ブローアウトフラックスが非ゼロ、primary が collisions を指すことを確認。[tests/test_phase9_usecases.py:86–107]
- A1-3 スコープ固定: `scope.region!="inner"` を弾くガードを維持。[marsdisk/run.py:643–695][tests/test_phase9_usecases.py:109–115]
- A2-1 時間窓デフォルト: `t_end_years` 未指定でも `analysis_years=2` が time_grid に反映され、scope/radiation メタデータが Mars-only で書き出される。[marsdisk/run.py:575–695][marsdisk/run.py:2142–2352][marsdisk/run.py:2429–2467][tests/test_phase9_usecases.py:117–144]
- A3-1 比較可能性: 同一時間グリッド・同一初期条件の `sublimation_only` と `collisions_only` で `M_loss` が異なり、primary / radiation / time_grid メタデータで比較できること、再実行で衝突系 `M_loss` が再現すること。[tests/test_phase9_usecases.py:146–178]

## YAML/CLI ユースケース
- ユースケース1（経路A 昇華のみ, 2 年・内側円盤）  
  `configs/examples/phase9_sublimation_only.yaml` を用い、`summary.json` で `primary_process="sublimation_only"`、`M_loss`、`analysis_window_years=2`、`radiation_field="mars"` を確認。  
  ```bash
  python -m marsdisk.run --config configs/examples/phase9_sublimation_only.yaml
  ```
- ユースケース2（経路B 衝突＋ブローアウトのみ, 同一条件）  
  `configs/examples/phase9_collisions_only.yaml` を同じ outdir パターンで実行し、`primary_process="collisions_only"`、`collisions_active=true`、`M_loss` の値差をユースケース1と比較。  
  ```bash
  python -m marsdisk.run --config configs/examples/phase9_collisions_only.yaml
  ```
- いずれも Mars-only scope なので `summary.solar_radiation.enabled=false` と `run_config.radiation_provenance.use_solar_rp=false` が一致しているか確認する。

## 既存との差分・後方互換性
- Phase3/5/7 で導入したブローアウト監査・単一過程モードの仕様を流用し、**新しい式や計算モードは追加していない**。既存 YAML/Phase5 比較ランは `physics_mode=default` のまま動作し、後方互換テスト（A1-3/A2-1）で scope ガードと time_grid 書き戻しが維持されることを保証する。
