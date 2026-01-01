# スピル経路とブローアウト無反応の整理（2025-12-13）

> 本メモは外部供給シミュレーションにおいて、**供給がスピル（溢れ流出）**に回り**ブローアウト（放射圧脱出）が発生しない**問題の原因と対策を記録したものです。

---

## 背景

**火星月形成円盤**モデルでは、外部から供給された質量が表層に蓄積し、放射圧によるブローアウト（小粒子の系外脱出）と衝突カスケード（破砕連鎖）を通じて質量損失を引き起こします。しかし、**ヘッドルームポリシーが `spill` の場合**、光学深度 $\tau=1$ を超える供給分が即座にスピル（溢れ流出）として系外へ排出され、表層に「燃料」が残らない状態が発生しました。

### この文書で扱う物理
- **ブローアウト**: $\beta \geq 0.5$ の小粒子が放射圧で系外へ脱出（式 [E.013](file://analysis/equations.md#E013), [E.014](file://analysis/equations.md#E014)）
- **スピル**: $\tau > 1$ 超過時に供給を表層に入れず系外へ逃がす経路
- **光学深度クリップ**: $\Sigma_{\rm surf}$ を $\Sigma_{\tau=1}$ 以下に制限する処理（式 [E.016](file://analysis/equations.md#E016)）

---

## 主要用語の定義

| 用語 | 記号 | 意味 | 参照 |
|------|------|------|------|
| **ブローアウト** | blowout | $\beta \geq 0.5$ での粒子脱出 | E.013, E.014 |
| **スピル** | spill | τ超過時の供給溢れ流出 | `headroom_policy=spill` |
| **クリップ** | clip | τ超過分を捨てず供給を制限 | `headroom_policy=clip` |
| **ヘッドルーム** | headroom | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$：追加供給可能な余地 | スクリプト内定義 |
| **光学深度** | $\tau$ | 表層の光学的厚さ。$\tau=1$ が遮蔽閾値 | E.015–E.017 |
| **表層面密度** | $\Sigma_{\rm surf}$ | 表層の質量面密度 [kg m⁻²] | E.007 |
| **τ=1 面密度** | $\Sigma_{\tau=1}$ | $\tau=1$ となる上限 = $1/\kappa_{\rm eff}$ | E.016 |
| **s_min_effective** | $s_{\min,\rm eff}$ | 実効下限粒径（設定とブローアウト限界の max） | E.008 |
| **衝突カスケード** | — | 大粒子→小粒子の破砕連鎖 | E.010 (Smoluchowski) |

---

## 関連コードとスキーマ

| モジュール | 役割 |
|------------|------|
| [marsdisk/run.py](file://marsdisk/run.py) | メインループ `run_zero_d`、昇華→ブローアウト振替ロジック |
| [marsdisk/physics/supply.py](file://marsdisk/physics/supply.py) | 供給率計算、headroom_policy の適用 |
| [marsdisk/physics/shielding.py](file://marsdisk/physics/shielding.py) | 遮蔽と $\Sigma_{\tau=1}$ クリップ |
| [marsdisk/schema.py](file://marsdisk/schema.py) | YAML 設定のバリデーション |

---

## 状況（設定とコードの実施内容）
- 設定ファイル群：`configs/sweep_temp_supply/*.yml`（T2000/T4000/T6000 × eps0p1/eps1）
  - `sizes.s_min: 1e-7`、`sizes.evolve_min_size: false`
  - `psd.floor.mode: none`（ブローアウト下限に縛らず、設定値まで刻む）
  - `supply.headroom_policy: clip`（τ≤1 超過分をスピルさせず、供給を捨てない）
  - `supply.mode: const`、`prod_area_rate_kg_m2_s: 1e-10`
  - `sinks.mode: sublimation`、`sub_params.mass_conserving: true`（昇華は質量を減らさず、ブローアウトへ振替）
  - `blowout.enabled: true`、`blowout.layer: surface_tau_le_1`（既定）
  - 遮蔽：`shielding.mode: psitau`、φテーブルは各レシピ既定（例: phi_const_0p20/0p37）
- コード側（`marsdisk/run.py`）
  - `psd.floor.mode=none` 時、ステップごとも `s_min` を設定値に維持し a_blow で上書きしないよう修正。
  - 昇華ドリフトの床を mass_conserving 時に 0 まで緩め、粒径が設定未満に落ちても許容。
  - 昇華で削れた質量を sink ではなくブローアウトに振り替え、`outflux_surface` と `M_loss_cum` に積算。

## 直近の問題
- スピル有効時は供給が全量 `mass_loss_rate_spill` に回り、表層に在庫が残らず `M_out_dot=0` が継続していた（例: `/Volumes/KIOXIA/marsdisk_out/temp_supply_sweep/20251213-204205__a7763f697__seed2041193009`）。
- `s_min_effective` は 1e-7 に下げられたが、`headroom_policy="spill"` により供給が燃料にならず衝突カスケードが立たなかった。

## 対応方針
1. スピル無効化: `headroom_policy: clip` でスピル経路を閉じる（全レシピ反映済み）。
2. 再実行: 代表ケースを再実行し、`supply_tau_clip_spill_rate` が 0 近傍に落ち、`M_out_dot` が立つか確認。
3. 必要に応じて `shielding.fixed_tau1_sigma` や φ テーブルを調整し、`Sigma_tau1` を下げて表層に在庫を確保する。

## 参考パス
- 設定: `configs/sweep_temp_supply/temp_supply_T4000_eps1.yml` ほか全6ファイル。
- 変更コード: `marsdisk/run.py`（昇華→ブローアウト振替、s_min 更新ロジック）。

---

## 確認すべき出力項目

| ファイル | 確認項目 | 期待値 |
|----------|----------|--------|
| `out/<run_id>/summary.json` | `M_out_dot` (最終ステップ) | > 0（ブローアウト発生） |
| `out/<run_id>/summary.json` | `supply_clip_time_fraction` | < 1（常時クリップでない） |
| `out/<run_id>/series/run.parquet` | `mass_loss_rate_spill` | ≈ 0（spill→clip 後） |
| `out/<run_id>/series/run.parquet` | `headroom` | > 0（供給余地あり） |

---

## 関連ドキュメント

| ドキュメント | 内容 |
|--------------|------|
| [analysis/equations.md](file://analysis/equations.md) | β, s_blow, 遮蔽 (E.013–E.017) の数式定義 |
| [analysis/AI_USAGE.md](file://analysis/AI_USAGE.md) | 出力ファイルのカラム定義 |
| [analysis/glossary.md](file://analysis/glossary.md) | 用語集と変数命名規約 |
| [docs/plan/20251221_temp_supply_external_supply.md](file://docs/plan/20251221_temp_supply_external_supply.md) | 外部供給スイープの環境変数リファレンス |

