# ⟨Q_pr⟩ 設定の背景と現状整理

**作成日**: 2024-12-22  
**担当**: Mars Disk Simulation Project  
**関連先行研究**: Burns et al. (1979); Strubbe & Chiang (2006); Wyatt (2008)

---

## 本ドキュメントの目的

本ドキュメントでは、火星ロッシュ限界内ダスト円盤シミュレーション (Mars Disk Simulation) における**放射圧効率パラメータ ⟨Q_pr⟩（Planck平均）**の設定に関する技術的課題と、その解決に向けた選択肢を整理する。

---

## プロジェクトの概要（外部読者向け）

### 科学的背景

火星の衛星フォボス・ダイモスは巨大衝突による火星周回円盤から形成されたとする説が有力である（Rosenblatt 2011, Canup & Salmon 2018）。本プロジェクトでは、**ロッシュ限界内（約2.4火星半径）に形成された高温・高密度ダスト円盤**の物質進化をシミュレートし、約2年間の質量損失 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}$ を定量化する。

### 主な物理過程

1. **衝突カスケード** — Smoluchowski方程式による粒子破砕・再分布
2. **放射圧ブローアウト** — 火星からの赤外放射で小粒子を吹き飛ばす
3. **昇華** — 高温環境での粒子蒸発（Hertz-Knudsen-Langmuir式）

### 放射圧とブローアウトサイズ

放射圧の強さは無次元量 **β**（放射圧と重力の比）で定量化される：

$$
\beta = \frac{3 L_M \langle Q_{\rm pr} \rangle}{16 \pi c G M_M \rho s}
$$

ここで:
- $L_M$: 火星の光度 $L_M = 4\pi R_M^2 \sigma T_M^4$
- $\langle Q_{\rm pr} \rangle$: Planck平均放射圧効率（サイズ・温度依存）
- $\rho$: 粒子密度
- $s$: 粒径
- $c$: 光速、$G$: 重力定数、$M_M$: 火星質量

**β = 0.5 を超える粒子**は重力束縛を脱して系から放出される。この閾値サイズを**ブローアウトサイズ $a_{\rm blow}$（または $s_{\rm blow}$）** と呼ぶ（Burns et al. 1979; Strubbe & Chiang 2006）。

---

## なぜ整理が必要か

温度スイープ実験（`temp_supply`）で以下の問題が発生した：

- `stop_on_blowout_below_smin` フラグが発火し、温度 2.5e3 K 付近で s_blow が `s_min=1e-7 m` を下回って早期終了した。
- 原因は旧 ⟨Q_pr⟩ テーブル `marsdisk/io/data/qpr_planck.csv` の小粒径域で Q_pr が低く、s_blow が小さく評価されるため。設定意図と挙動の齟齬を解消する必要がある。
- 対応としてデフォルトの参照テーブルを `marsdisk/io/data/qpr_planck_sio2_generated.csv`（SiO₂ 想定で新生成）に差し替え済み。

---

## 現行実装の詳細

### ブローアウトサイズの計算フロー

```
火星表面温度 T_M  →  ⟨Q_pr⟩テーブル補間  →  β(s) 計算  →  s_blow (β=0.5)
                ↑
          サイズ s と T_M で2D補間
```

**主要関数**:
- `blowout_radius(rho, T_M, Q_pr)`: β=0.5 を解いて s_blow を返す
  - 実装: [marsdisk/physics/radiation.py#L274–L288](marsdisk/physics/radiation.py#L274-L288)
- `_resolve_blowout`: `run.py` 内で `s_min` を床として反復（最大6回）し、self-consistent な ⟨Q_pr⟩ を参照

### ⟨Q_pr⟩テーブルの構造

テーブル（現デフォルト: `marsdisk/io/data/qpr_planck_sio2_generated.csv`、以下の例は旧 `qpr_planck.csv`）は以下の形式：

| T_M [K] | s [m]    | Q_pr [-] |
|---------|----------|----------|
| 2000.0  | 1e-07    | 0.034    |
| 2000.0  | 2.5e-07  | 0.585    |
| ...     | ...      | ...      |
| 4000.0  | 1e-07    | 0.36     |

**ポイント**: 小粒径（s ≤ 1e-7 m）かつ低温（T ≤ 3000 K）で Q_pr が急落する。

### テーブル値と結果の例（旧 `qpr_planck.csv`, s=1e-7 m）

| 温度 T_M [K] | Q_pr [-] | 計算される s_blow [m] | 判定 |
|-------------|----------|----------------------|------|
| 4000        | ≈ 0.36   | ≈ 2.3e-6            | ✓ s_min より十分大 |
| 3000        | ≈ 0.15   | ≈ 3.1e-7            | 境界付近 |
| 2550        | ≈ 0.086  | ≈ 9.2e-8            | **s_blow < s_min=1e-7** 🚨 |

- T_M=4000 K の冷却テーブル `data/mars_temperature_T4000p0K.csv` は 2550 K までしか降りず、旧テーブルの Q_pr 落ち込みがそのまま s_blow を縮める。
- 早期終了トリガ: `numerics.stop_on_blowout_below_smin=true`（スイープスクリプトでデフォルト上書き済み）。

---

## 問題の本質：想定とのズレ

### 期待した挙動

2–3×10³ K 帯でも s_blow > 1e-7 m で推移し、シミュレーションは s_min より上で完走するはず。

### 実際の挙動

Q_pr が 0.1 未満に落ち込み、s_blow が 1e-7 m を割って早期終了する。

### 根本原因

**テーブル依存**: ⟨Q_pr⟩ テーブルは Mie 散乱理論に基づくが、小粒径・低温域で Planck 平均が急落する物理的特性がある。一方、Q_pr を定数 1.0 に固定すると s_blow は 1e-6–1e-5 m オーダーで、早期終了しない。

```
【図解】Q_pr と s_blow の関係（概念図）

Q_pr ↑                                s_blow ↑
     |  ********                            |  ++++++++++++
     |       *****                          |            +++++
     |            ****   ← 低温域で急落      |                ++++
     |                ***                   |                    +++ ← s_min=1e-7 を割る
-----+------------------→ T_M             --+------------------------→ T_M
   4000K          2550K                   4000K              2550K
```

---

## 取れる選択肢（トレードオフ比較）

| # | 選択肢 | 長所 | 短所 | 優先度 |
|---|--------|------|------|--------|
| 1 | 早期終了を無効化 | 最速で挙動確認可能 | 物理的妥当性の検証が後回し | 🔵 即時対応 |
| 2 | Q_pr を固定値に | シンプル、再現性高い | 物理的な温度依存性を失う | 🟢 許容可 |
| 3 | Q_pr テーブル差替え | より正確な物理 | テーブル生成の手間 | 🟡 中期 |
| 4 | s_min を下げる | 計算領域拡大 | 数値安定性リスク | 🔴 要検討 |

### 各選択肢の詳細

#### 選択肢 1: 早期終了を無効化
```yaml
numerics:
  stop_on_blowout_below_smin: false
```
**影響**: s_blow < s_min の状態でも計算を続行。質量収支のチェックで異常を検出可能。

#### 選択肢 2: Q_pr を固定値にする
```yaml
radiation:
  Q_pr: 1.0
```
**物理的許容範囲**: 幾何光学極限（s >> λ）では Q_pr ≈ 1 は妥当。ただし小粒径では過大評価。

#### 選択肢 3: Q_pr テーブルを差し替え・補正
Mie 理論に基づく新テーブルを作成し、小粒径域で Q_pr = 0.3–1.0 程度を維持するよう調整。`marsdisk/ops/make_qpr_table.py` のユーティリティを活用。

#### 選択肢 4: s_min を下げる
```yaml
sizes:
  s_min: 1e-8  # from 1e-7
```
**リスク**: ビン数増加による計算コスト増、Smoluchowski 積分の数値安定性要確認。

---

## 今後のアクション項目（TODO）

- [ ] 想定どおりの Q_pr プロファイル（小粒径域で 0.3–1.0 程度）を持つテーブル候補を作成し、s_blow 曲線を可視化するノートを用意。
- [ ] スイープ config に `stop_on_blowout_below_smin` を明示可変にする（現状スクリプトで強制 true）。
- [ ] `qpr_planck_sio2_generated.csv` の由来と適用範囲を README に短く追記（誰がいつ生成したかを残す）。

---

## 関連ファイル・リンク

| リソース | パス | 説明 |
|----------|------|------|
| Q_pr テーブル | `marsdisk/io/data/qpr_planck_sio2_generated.csv` | Planck平均放射圧効率（サイズ×温度） |
| テーブルローダ | `marsdisk/io/tables.py` | `interp_qpr`, `load_qpr_table` |
| ブローアウト計算 | `marsdisk/physics/radiation.py` | `blowout_radius`, `beta_from_qpr` |
| テーブル生成 | `marsdisk/ops/make_qpr_table.py` | CLI ユーティリティ |
| 物理式リファレンス | `analysis/equations.md` | (E.004)–(E.005) |

---

## 参考文献

- Burns, J. A., Lamy, P. L., & Soter, S. (1979). "Radiation forces on small particles in the solar system." *Icarus*, 40, 1–48.
- Strubbe, L. E., & Chiang, E. I. (2006). "Dust dynamics, surface brightness profiles, and thermal spectra of debris disks." *ApJ*, 648, 652.
- Wyatt, M. C. (2008). "Evolution of debris disks." *ARAA*, 46, 339.
- Canup, R. M., & Salmon, J. (2018). "Origin of Phobos and Deimos by the impact of a Vesta-to-Ceres sized body with Mars." *Science Advances*, 4, eaar6887.
- Hyodo, R., et al. (2017, 2018). 火星衛星形成に関する一連の論文。
