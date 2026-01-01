# 放射圧・外部供給・昇華の式と設定まとめ（T6000_mu0p5_phi20）

> **本資料について**: 本ドキュメントは火星デブリ円盤シミュレーション（marsdisk）の特定実行パラメータを記録したものです。プロジェクト全体の概要は [analysis/overview.md](analysis/overview.md) および [README.md](../../README.md) を参照してください。

## 背景：火星衝撃形成デブリ円盤
本シミュレーションは、原始火星への巨大衝突により形成されたと考えられるデブリ円盤（SiO₂ 主体の高密度・ガス希薄円盤）の時間発展を追跡します。特に以下の物理過程を 0D（半径無次元）モデルでカップリングしています：
- **放射圧（blow-out）**: 小粒子が火星からの熱放射圧で系外へ吹き飛ばされる
- **外部供給**: 衝突破砕により小粒子が常時生成される
- **昇華（sublimation）**: 高温環境下で粒子表面が蒸発する

詳細な物理式と仕様は `analysis/equations.md` を正とし、本メモはその参照位置とシミュレーション設定のスナップショットを提供します。

## ファイル名の読み方（命名規則）
| 記号           | 意味                              | 本設定での値          |
| ------------- | --------------------------------- | -------------------- |
| `T6000`       | 火星表面温度 T_M の初期値（K）       | 6000 K（テーブル参照） |
| `mu0p5`       | 混合効率 ε_mix（供給が円盤に取り込まれる割合） | 0.5（50%）           |
| `phi20`       | 遮蔽係数 Φ（光学的厚さによる減衰）   | 0.20（20%透過）       |

## 目的
放射圧（ブローアウト）、外部供給、昇華に関する式の参照位置と、現在の設定値（run_config.json ベース）を 1 か所で確認できるようにする。式そのものは analysis/ を唯一の仕様源とし、ここではアンカーだけを列挙する。

## 式の参照（再掲せずリンクのみ）

> **式番号（E.xxx）の読み方**: 本プロジェクトでは物理式を `analysis/equations.md` に一元管理しており、式番号は `(E.001)` 〜 `(E.xxx)` の形式で付与されています。以下の行範囲は `analysis/equations.md` のおおよその該当行です。最新版ではズレている場合があるため、式番号（E.xxx）で検索してください。

- **放射圧効率・β・ブローアウト下限と表層 ODE**（t_blow, Σ更新, outflux）：Q_pr 補間とローダ、β 診断、Wyatt 衝突寿命と表層 ODE。[analysis/equations.md:53–129]
- **外部供給**（混合効率 ε_mix と基礎率 R_base、無次元 μ→供給率の変換）：[analysis/equations.md:714–758]
  - `mu`→R_base 変換に使う (E.027a) は supply モジュールの定義式
- **昇華**（HKL フラックス、Clausius/tabulated P_sat、液相分岐、瞬時シンク尺度 s_sink）：[analysis/equations.md:441–506]

## 現行設定

> **出典**: [`scripts/research/run_temp_supply_sweep.sh`](scripts/research/run_temp_supply_sweep.sh)
> 
> このスクリプトは温度・供給・遮蔽のパラメータスイープを自動実行します。デフォルト値と環境変数によるオーバーライドを以下に整理します。

### パラメータグリッド
| パラメータ         | 掃引値                       | 対応するオーバーライド              |
| ---------------- | --------------------------- | -------------------------------- |
| 火星温度 T_M (K)  | 6000, 4000, 2000            | `radiation.TM_K`, `mars_temperature_driver.table.path` |
| 混合効率 ε_mix    | 1.0, 0.5, 0.1               | `supply.mixing.epsilon_mix`       |
| 遮蔽係数 Φ        | 0.20, 0.37, 0.60            | `shielding.table_path` (phi_const_0pXX.csv) |

ベース設定ファイル: `configs/sweep_temp_supply/temp_supply_T4000_eps1.yml`

### 放射圧/遮蔽
- 火星放射のみ（太陽放射は無効）
- 温度テーブル: `data/mars_temperature_T{T}p0K.csv`（T=6000/4000/2000）
- 遮蔽モード: `fixed_tau1`（デフォルト）または環境変数 `SHIELDING_MODE` で変更可
- Σ_{τ=1} 設定: `SHIELDING_SIGMA`（デフォルト `auto`）
- Φ テーブル: `tables/phi_const_0p{20,37,60}.csv` から選択

### 外部供給（supply）
| 項目                  | デフォルト値                 | 環境変数                          |
| -------------------- | -------------------------- | -------------------------------- |
| モード                | `const`                    | `SUPPLY_MODE`                    |
| 基礎供給率             | 3.0×10⁻³ kg m⁻² s⁻¹       | `SUPPLY_RATE`                    |
| 初期Σをτ=1にクリップ   | true                       | `INIT_SCALE_TO_TAU1`             |

**フィードバック制御**（デフォルト有効）:
| 項目            | デフォルト値   | 環境変数                          |
| -------------- | ------------ | -------------------------------- |
| ターゲットτ     | 1.0          | `SUPPLY_FEEDBACK_TARGET`         |
| ゲイン          | 1.0          | `SUPPLY_FEEDBACK_GAIN`           |
| 応答時間        | 0.5 年       | `SUPPLY_FEEDBACK_RESPONSE_YR`    |
| スケール範囲    | [0.0, 10.0]  | `SUPPLY_FEEDBACK_MIN/MAX_SCALE`  |
| τフィールド     | tau_los | `SUPPLY_FEEDBACK_TAU_FIELD`      |

**温度カップリング**（デフォルト有効）:
| 項目             | デフォルト値   | 環境変数                         |
| --------------- | ------------ | ------------------------------- |
| モード           | scale        | `SUPPLY_TEMP_MODE`              |
| 参照温度         | 1800 K       | `SUPPLY_TEMP_REF_K`             |
| 指数             | 1.0          | `SUPPLY_TEMP_EXP`               |
| キャップ         | 10.0         | `SUPPLY_TEMP_CAP`               |

**リザーバ**（デフォルト無効）:
- `SUPPLY_RESERVOIR_M` を設定すると有限リザーバモードが有効化
- 枯渇モード: `hard_stop`（デフォルト）または `smooth`

### 昇華/シンク
シンク設定はベース YAML（`temp_supply_T4000_eps1.yml`）に従い、スクリプトからの直接オーバーライドはありません。HKL 昇華モデルが有効な場合は analysis の式 (E.016)〜(E.018) を参照。

### その他数値条件
- 時間ステップ: dt=20 s（固定、`numerics.dt_init=20`）
- シード: 各実行ごとに乱数生成（`dynamics.rng_seed`）
- 出力先: `${OUT_ROOT}/temp_supply_sweep/<timestamp>__<sha>__seed<batch>/T{T}_mu{eps}_phi{phi}/`

## 使い方メモ
- 式の変更や追加は必ず `analysis/equations.md` に反映し、本メモは参照行を更新するだけに留める。
- 設定を変える場合は sweep YAML（`configs/sweep_temp_supply/temp_supply_T6000_eps1.yml` など）を編集し、`out/<run_id>/run_config.json` で実績値を確認する。

---

## 関連資料
外部の方が理解を深めるための関連ドキュメント：

| 資料 | 内容 |
| ---- | ---- |
| [analysis/overview.md](analysis/overview.md) | プロジェクト全体の構造とモジュール責務 |
| [analysis/equations.md](analysis/equations.md) | 全物理式の定義（唯一の仕様源） |
| [analysis/glossary.md](analysis/glossary.md) | 用語・記号の定義一覧 |
| [analysis/AI_USAGE.md](analysis/AI_USAGE.md) | AI・自動化ツール向けの実行ガイド |
| [analysis/run-recipes.md](analysis/run-recipes.md) | 代表的な実行レシピ集 |
