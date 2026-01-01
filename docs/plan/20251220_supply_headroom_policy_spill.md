# Supply Headroom Policy: Spill モード実装提案

> 作成日: 2025-12-20  
> 区分: 機能追加提案（headroom 処理の新モード）

---

## 本プロジェクト・ドキュメントについて

### プロジェクト概要

本リポジトリ（MarsDiskSimulation / `marsshearingsheet`）は、**火星ロッシュ限界内の高密度ダストディスク**を対象に、放射圧によるブローアウトと衝突破砕カスケードを2年間シミュレーションして質量損失・流出率を定量化するものです。詳細は以下を参照してください：

- **全体仕様**: [analysis/overview.md](../../analysis/overview.md)
- **物理モデル式**: [analysis/equations.md](../../analysis/equations.md)
- **実行レシピ**: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- **AI向け利用ガイド**: [analysis/AI_USAGE.md](../../analysis/AI_USAGE.md)

### 用語定義

本ドキュメントで使用される主な用語を以下に定義します：

| 用語 | 意味 | 参考 |
|------|------|------|
| $\Sigma_{\tau=1}$ (`sigma_tau1`) | 光学的深さ τ = 1 となる臨界面密度。$\kappa_{\rm eff}^{-1}$ として計算 | (E.016), (E.017) |
| **headroom** | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$。表層が τ=1 を超えないための余裕 | (E.031) |
| **clip モード（従来）** | headroom がゼロになると供給自体を遮断する方式 | — |
| **spill モード（提案）** | 供給は止めず、τ=1 超過分のみをステップ後に除去する方式 | — |
| `supply.headroom_policy` | headroom 処理のモード設定（`clip` / `spill`） | [schema.py](../../marsdisk/schema.py) |
| **deep_mixing** | 深部→表層の物質輸送モード | [supply.py](../../marsdisk/physics/supply.py) |
| **Smol** | Smoluchowski 衝突＋破砕を扱う内部ソルバー | [collisions_smol.py](../../marsdisk/physics/collisions_smol.py) |

### ドキュメントの位置付け

`docs/plan/` 内のドキュメントは開発プラン・イシュー整理・振り返りを管理します。本メモは **headroom 超過時の処理方針に関する新モード（spill）の実装提案**です。

関連ドキュメント：
- [20251219_tau_clip_gate_review.md](./20251219_tau_clip_gate_review.md) — τクリップと供給ゲートの現状整理
- [20251216_temp_supply_sigma_tau1_headroom.md](./20251216_temp_supply_sigma_tau1_headroom.md) — 供給クリップ事象の報告

---

## 背景と目的

### 問題点
現行の **clip モード**では、headroom（= $\Sigma_{\tau=1} - \Sigma_{\rm surf}$）がゼロに近づくと供給レートを完全に遮断する。この挙動は τ≤1 を安全に保つ反面、以下の問題を生じる：

1. 初期 $\Sigma_{\rm surf}$ が $\Sigma_{\tau=1}$ に近いと、供給が長時間ゼロになり「律速シナリオ」の比較ができない
2. 急峻なオン/オフ切替が $\dot{M}_{\rm out}$ のギザギザを引き起こす
3. deep_mixing の t_mix を調整しても供給が通らない

### 提案（spill モード）
供給自体は止めず、ステップ終了後に $\Sigma_{\rm surf} > \Sigma_{\tau=1}$ となった超過分のみを除去（spill）する方式を新設する。これにより：

- 供給レートの連続性を維持しつつ τ≤1 制約を守る
- 超過質量は明示的に追跡・記録され、質量収支の検証が容易

---

## 変更点

### 設定追加
```yaml
supply:
  headroom_policy: clip  # 従来動作（デフォルト）
  # headroom_policy: spill  # 新モード
```

### 実装詳細

| 項目 | 内容 |
|------|------|
| **行き先** | spill は系外ロスとして扱い、質量収支では sinks 側に加算（deep へ戻さない） |
| **Smol 側処理** | spill モード時は headroom で supply を 0 にしない。ステップ後に $\Sigma_{\rm surf} > \Sigma_{\tau=1}$ なら $f=\Sigma_{\tau=1}/\Sigma_{\rm surf}^{\rm raw}$ で全 bin の $N_k$ を比例縮小し、$\Delta\Sigma=\Sigma_{\rm surf}^{\rm raw}-\Sigma_{\tau=1}$ を spill 量として記録 |
| **タイミング** | Smol ステップの計算完了後に spill を適用し、出力・診断の $\Sigma_{\rm surf}$ は spill 反映後を使用（blowout/sink レートはステップ計算時の値を保持し再評価しない） |
| **deep_mixing 連携** | spill モードでは headroom gate で供給を遮断せず、spill 処理は Smol 側に集約 |
| **新規出力カラム** | `supply_tau_clip_spill_rate` (kg m^-2 s^-1), `mass_lost_tau_clip_spill_step` (M_Mars), `cum_mass_lost_tau_clip_spill` (M_Mars) |
| **summary/run_config** | spill 統計（累積除去量、rate の min/median/max、発生比率など）を追加 |

---

## テスト

新規テストファイル: `tests/integration/test_supply_headroom_policy.py`

検証項目：
- [x] spill モードで供給がゼロに貼り付かないこと
- [x] $\Sigma_{\rm surf} \le \Sigma_{\tau=1}$ が常に維持されること
- [x] spill 関連カラムが正値で記録されること
- [ ] 質量収支が維持されること（spill 分を含めて誤差 < 0.5%）

---

## 影響範囲・互換性

| 観点 | 影響 |
|------|------|
| **既存 YAML** | デフォルトは `clip` のまま → 動作変更なし |
| **出力カラム** | spill モードのみ新規カラム追加。既存カラム名は不変 |
| **deep_mixing** | spill モード時のみ挙動変更。clip モードは従来どおり |

---

## 参考

### 関連ドキュメント
- 物理式の詳細: [analysis/equations.md](../../analysis/equations.md)
- シミュレーション実行方法: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- AI向け利用ガイド: [analysis/AI_USAGE.md](../../analysis/AI_USAGE.md)

### コード参照
| 機能 | ファイル | 備考 |
|------|----------|------|
| headroom クリップ実装 | [collisions_smol.py](../../marsdisk/physics/collisions_smol.py) | L308–352 |
| deep_mixing 供給制御 | [supply.py](../../marsdisk/physics/supply.py) | `split_supply_with_deep_buffer()` |
| 設定スキーマ | [schema.py](../../marsdisk/schema.py) | `headroom_policy` 追加予定 |
