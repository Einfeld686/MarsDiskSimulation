# Deprecated API スケジュールと移行ガイド

本書は `marsdisk/` 内の deprecated 警告について、削除予定日と移行手順を整理したものです。
スケジュールは暫定であり、実装都合により日付が変更される場合があります。

## スケジュール

| 対象 | 代替 | 期限 | 状態 | 備考 |
|------|------|------|------|------|
| `temps.T_M` | `radiation.TM_K` | 2026-12 | 互換維持 | `schema.py` で警告表示 |
| `supply.mixing.mu` | `supply.mixing.epsilon_mix` | 2026-06 | 互換維持 | alias 禁止で明示エラー |
| `supply.reservoir.smooth_fraction` | `supply.reservoir.taper_fraction` | 2026-06 | 互換維持 | 設定名のみ変更 |
| `supply.reservoir.depletion_mode='smooth'` | `'taper'` | 2026-06 | 互換維持 | スキーマで警告 |
| `supply.injection.deep_reservoir_tmix_orbits` | `supply.injection.t_mix_orbits` | 2026-06 | 互換維持 | キー名整理 |
| `shielding.mode='table'` | `shielding.mode='psitau'` + `shielding.table_path` | 2026-06 | 互換維持 | 旧モード警告 |
| `io.columnar_records` | `io.record_storage_mode` | 2026-06 | 互換維持 | 旧フラグ警告 |
| `compute_s_min_F2()` | `max(s_min_cfg, blowout_radius)` | 2026-12 | 互換維持 | 関数は暫定互換 |
| `surface_ode solver` | 新しい表層 ODE 実装 | 2026-06 | 互換維持 | `surface.py` の警告に記載 |
| `dynamics.e_profile.mode='off'/'table'` | `mars_pericenter` / `table_path` 必須 | 2026-12 | 互換維持 | 旧モード警告 |
| `v_rel_mode='ohtsuki'` | `v_rel_mode='pericenter'` | 2026-12 | 互換維持 | 高 e 用に警告 |
| `supply.*` 非デフォルト拡張 | 既定の optical_depth + mu_orbit10pct | 2026-12 | 互換維持 | 感度試験のみ想定 |

現時点（2026-01）では期限超過の削除対象はありません。

## 移行ガイド（要点）

- `temps.T_M` は `radiation.TM_K` を使い、`temps` ブロックは削除する。
- `supply.mixing.mu` は `supply.mixing.epsilon_mix` に置換する。
- reservoir の `smooth_fraction` は `taper_fraction` に置換し、`depletion_mode='taper'` を使う。
- `supply.injection.deep_reservoir_tmix_orbits` は `supply.injection.t_mix_orbits` に置換する。
- `shielding.mode='table'` は `mode='psitau'` + `table_path` の組で設定する。
- `io.columnar_records` は `io.record_storage_mode` に置換する。
- `compute_s_min_F2()` の呼び出しは `max(s_min_cfg, blowout_radius)` へ移行する。
- `surface_ode solver` を使う設定は新実装へ切り替える。
- `dynamics.e_profile.mode='off'/'table'` は `mars_pericenter` または `table_path` 指定に統一する。
- `v_rel_mode='ohtsuki'` は `pericenter` に移行する。

