# run_temp_supply_sweep.sh で spill 供給を使うための設定メモ

> 作成日: 2025-12-20  
> 区分: 運用ガイド（スイープスクリプトでの spill モード活用）

---

## 本プロジェクト・ドキュメントについて

### プロジェクト概要

本リポジトリ（MarsDiskSimulation / `marsshearingsheet`）は、**火星ロッシュ限界内の高密度ダストディスク**を対象に、放射圧によるブローアウトと衝突破砕カスケードを2年間シミュレーションして質量損失・流出率を定量化するものです。詳細は以下を参照してください：

- **全体仕様**: [analysis/overview.md](analysis/overview.md)
- **物理モデル式**: [analysis/equations.md](analysis/equations.md)
- **実行レシピ**: [analysis/run-recipes.md](analysis/run-recipes.md)
- **AI向け利用ガイド**: [analysis/AI_USAGE.md](analysis/AI_USAGE.md)

### 用語定義

本ドキュメントで使用される主な用語を以下に定義します：

| 用語 | 意味 | 参考 |
|------|------|------|
| $\Sigma_{\tau=1}$ (`sigma_tau1`) | 光学的深さ τ = 1 となる臨界面密度 | (E.016), (E.017) |
| **headroom** | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$。供給ゲートの開閉を決定 | (E.031) |
| **clip モード** | headroom がゼロになると供給を遮断する方式（従来動作） | — |
| **spill モード** | 供給は止めず、τ=1 超過分を系外ロスとして除去する方式 | [20251220_supply_headroom_policy_spill.md](.docs/plan/20251220_supply_headroom_policy_spill.md) |
| `supply.headroom_policy` | headroom 処理のモード設定（`clip` / `spill`） | [schema.py](marsdisk/schema.py) |
| **deep_mixing** | 深部→表層の物質輸送モード。`t_mix_orbits` で時定数を指定 | [supply.py](marsdisk/physics/supply.py) |
| **headroom gate** | deep_mixing 時に headroom に応じて供給を制御する機構 | — |

### ドキュメントの位置付け

`docs/plan/` 内のドキュメントは開発プラン・イシュー整理・振り返りを管理します。本メモは **run_temp_supply_sweep.sh スクリプトで spill モードを使用する際の設定・注意点**をまとめた運用ガイドです。

関連ドキュメント：
- [20251220_supply_headroom_policy_spill.md](.docs/plan/20251220_supply_headroom_policy_spill.md) — spill モードの実装仕様
- [20251219_tau_clip_gate_review.md](.docs/plan/20251219_tau_clip_gate_review.md) — τクリップと供給ゲートの現状整理
- [20251216_temp_supply_sigma_tau1_headroom.md](.docs/plan/20251216_temp_supply_sigma_tau1_headroom.md) — 供給クリップ事象の報告

---

## 概要

- **対象**: `scripts/research/run_temp_supply_sweep.sh` を使って新しい外部供給（`supply.headroom_policy=spill`）でスイープ実行する際の設定
- **目的**: headroom クリップで供給が 0 になるのを防ぎ、spill ロスを明示的に追跡しつつスイープ実行する

---

## 必須・推奨環境変数

### 基本設定

```bash
# spill モードを有効化
export SUPPLY_HEADROOM_POLICY=spill

# スクリプト内で SUPPLY_OVERRIDES に反映
SUPPLY_OVERRIDES+=(--override "supply.headroom_policy=${SUPPLY_HEADROOM_POLICY:-clip}")
```

> **Note**: 既定は `clip` を維持し、必要なバッチだけ `spill` に切り替える運用を推奨

### 確認すべき既存変数

| 変数 | 説明 | spill との関係 |
|------|------|---------------|
| `SUPPLY_MODE` | 供給モード（const/table/powerlaw/piecewise） | 必ず確認 |
| `SUPPLY_RATE` | const モード時の供給レート | 必ず確認 |
| `SUPPLY_TRANSPORT_MODE` | 輸送モード（direct/deep_mixing） | spill の動作に影響 |
| `SUPPLY_TRANSPORT_HEADROOM` | headroom gate（hard/soft） | spill は gate をバイパス |
| `SUPPLY_TRANSPORT_TMIX_ORBITS` | deep_mixing の混合時定数 | 短すぎると spill ロス増加 |
| `SHIELDING_MODE` / `SHIELDING_SIGMA` | Σ_τ1 の決定方法 | 固定/auto_max を明示推奨 |
| `SUPPLY_TEMP_*` | 温度カップリング設定 | 事前にセット |
| `SUPPLY_FEEDBACK_*` | フィードバック設定 | 事前にセット |
| `SUPPLY_RESERVOIR_*` | リザーバ設定 | 事前にセット |

### モード選択ガイド

| シナリオ | 推奨設定 |
|----------|----------|
| deep バッファを活かしたい | `headroom_policy=clip` + `headroom_gate=soft` |
| 超過分を系外ロスとして追跡 | `headroom_policy=spill` + `headroom_gate=hard` |

---

## 実行時のおすすめオプション

| 項目 | 推奨設定 | 理由 |
|------|----------|------|
| **初期化** | `INIT_SCALE_TO_TAU1=true` | 低 headroom ケースでの初期供給ゼロ貼り付きを防止 |
| **出力先** | `OUT_ROOT` で外部 SSD か `out/<run_id>/` を指定 | 大量データ対応 |
| **タイトル形式** | `${RUN_TS}__${sha}__seed${batch}` | 既定のまま維持 |

### 診断用プロット追加カラム

spill 量の可視化を行う場合は、以下のカラムをプロットに追加：

| カラム名 | 単位 | 説明 |
|----------|------|------|
| `supply_tau_clip_spill_rate` | kg m⁻² s⁻¹ | spill レート |
| `mass_lost_tau_clip_spill_step` | M_Mars | ステップごとの spill 質量 |
| `cum_mass_lost_tau_clip_spill` | M_Mars | 累積 spill 質量 |

---

## 注意点・落とし穴

### 設計上の注意

| 項目 | 内容 |
|------|------|
| **spill の行き先** | 系外ロスとして扱い、deep に戻さない |
| **適用タイミング** | Smol ステップ後に適用。出力の Σ_surf は spill 反映後 |
| **レート保持** | blowout・sink レートはステップ計算時の値を保持（再評価しない） |

### 運用上の注意

| 項目 | 内容 |
|------|------|
| **単位混在** | rate 系は `kg m⁻² s⁻¹`、`mass_lost_*` / `cum_mass_lost_*` は `M_Mars`。解析スクリプト側で注意 |
| **deep_mixing + spill** | deep→surface が headroom で止まらないため、Σ_τ1 が小さいと spill ロス増大。t_mix を長めにするか clip に戻す選択肢を用意 |
| **深部バッファ活用** | 深部に戻したい場合は `clip` + `soft` gate を使用 |

---

## 参考

### 関連ドキュメント
- 実装仕様: [20251220_supply_headroom_policy_spill.md](.docs/plan/20251220_supply_headroom_policy_spill.md)
- 物理式の詳細: [analysis/equations.md](analysis/equations.md)
- AI向け利用ガイド: [analysis/AI_USAGE.md](analysis/AI_USAGE.md)

### コード参照
| 機能 | ファイル | 備考 |
|------|----------|------|
| スイープスクリプト | [run_temp_supply_sweep.sh](scripts/research/run_temp_supply_sweep.sh) | 環境変数で制御 |
| headroom 処理 | [collisions_smol.py](marsdisk/physics/collisions_smol.py) | spill 適用ロジック |
| 設定スキーマ | [schema.py](marsdisk/schema.py) | `headroom_policy` 定義 |
