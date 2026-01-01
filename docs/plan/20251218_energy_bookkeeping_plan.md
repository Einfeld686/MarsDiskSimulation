# 衝突エネルギー簿記・反発係数対応 導入計画

> 作成日: 2025-12-18  
> 出典: [collision_energy_conservation_requirements.md](docs/plan/collision_energy_conservation_requirements.md)

---

## 1. 目的

1. 衝突による運動エネルギーの散逸量をログする
2. 速度減衰（e/i 更新）と散逸量が整合する形で反発係数を導入する
3. オプションとして表面エネルギー制約による最小粒径を計算可能にする

---

## 2. 達成すべき要件

### 2.1 エネルギー定義（要件メモ §2）

$E_{\mathrm{rel}} = \frac{1}{2}\mu v^2$ をペア $(i,j)$ ごとに計算・記録。

**Numba基本方針**: 衝突カーネル呼び出し時に同じ入力を JIT へ渡し、`E_rel` と簿記用集計も Numba カーネル内で実行する（Fallback は NumPy ベクトル化 + `np.triu` で上三角のみ集計）。Python 二重ループは使用しない。

### 2.2 残存率（非散逸率） $f_{\mathrm{ke}}$（要件メモ §3–§4.1）

| パラメータ | 制約 | 既定値 |
|---|---|---|
| `f_ke_cratering` | $0 \le f \le 1$ | 0.1 |
| `f_ke_fragmentation` | $0 \le f \le 1$ または None | None（→ $\varepsilon^2$） |
| `eps_restitution` | $0 < \varepsilon \le 1$ | 0.5 |

**定義と整合性ルール**:
- $f_{\mathrm{ke}}$ は **衝突後に残る運動エネルギーの割合（非散逸率）**。式は常に $E_{\mathrm{ret}} = f_{\mathrm{ke}} E_{\mathrm{rel}}$ を用い、散逸分は $(1-f_{\mathrm{ke}})E_{\mathrm{rel}}$。
- `f_ke_fragmentation` 未設定時は自動的に $\varepsilon^2$ を使用
- 明示的に設定した場合、$\varepsilon^2$ との差分を `f_ke_eps_mismatch` としてログ
- 差分が大きい場合（例: $|f_{\mathrm{ke,frag}} - \varepsilon^2| > 0.1$）は警告出力

### 2.3 侵食/破砕の分岐条件

| 条件 | 衝突タイプ | 適用 $f_{\mathrm{ke}}$ |
|---|---|---|
| $F_{\mathrm{lf}} > 0.5$ | 侵食 | `f_ke_cratering` |
| $F_{\mathrm{lf}} \le 0.5$ | 壊滅的破砕 | `f_ke_fragmentation` |

### 2.4 e/i 減衰更新（要件メモ §4.3）

$$
t_{\mathrm{damp}} = \frac{t_{\mathrm{coll}}}{\varepsilon^2}
$$

$$
e_{n+1} = e_n + \left(\frac{c_{\mathrm{eq}}}{v_K} - e_n\right) \left(1 - \exp\left(-\frac{\Delta t}{t_{\mathrm{damp}}}\right)\right)
$$

$i$ も同形。

### 2.5 表面エネルギー制約（要件メモ §4.4, Krijt & Kama 2014）

**計算式** (Krijt & Kama Eq.4, \(\alpha=3.5\)):
$$
s_{\min,\mathrm{surf}} =
\left(\frac{24\gamma s_0}{\eta\rho s_0 v_{\mathrm{rel}}^2 + 24\gamma}\right)^2
s_{\max}^{-1}
$$

**入力パラメータ**:

| パラメータ | 取得元 | スキーマ |
|---|---|---|
| $\gamma$ | 表面エネルギー [J/m²] | `surface_energy.gamma_J_m2`（既定 1.0） |
| $\eta$ | KE→表面変換効率 | `surface_energy.eta`（既定 0.1） |
| $\rho$ | 材料密度 [kg/m³] | `material.rho` |
| $\alpha$ | PSD 勾配 | `psd.alpha`（式は \(\alpha=3.5\) 前提） |
| $s_0$ | コライダサイズ [m] | `surface_energy.collider_size_m`（未指定時は `sizes.s_max`） |
| $f_{\mathrm{lf}}$ | 最大破片質量比 | `surface_energy.largest_fragment_mass_fraction`（既定 0.5） |
| $s_{\max}$ | 最大破片サイズ [m] | $s_0 f_{\mathrm{lf}}^{1/3}$ |
| $v_{\mathrm{rel}}$ | 衝突相対速度 [m/s] | ステップ中の `v_rel_kernel` |

**スキーマ追加**:
```yaml
surface_energy:
  enabled: false        # トグル
  gamma_J_m2: 1.0       # J/m²
  eta: 0.1              # 変換効率
```

**floor 統合**:
```
s_min_effective = max(config, blowout, floor_dynamic, surface_energy)
```
`s_min_components` に `surface_energy` キーを追加。

---

## 3. 技術仕様

### 3.1 Numba を前提にした集計経路

- `collision_kernel_numba` を拡張、あるいは簿記専用の JIT カーネルを併設し、以下を **単一 JIT パス** で返す: `C`, `E_rel_step`（上三角和）, `E_dissipated_step`, `E_retained_step`, `f_ke_mean`, `F_lf_mean`, `n_cratering`, `n_fragmentation`。  
- `F_lf`/`f_ke` 行列は、`fragments`/`qstar` 依存の判定を **Python→NumPy ベクトル化で事前計算** し、JIT へ入力として渡す。JIT 内で分岐・カウントすることで、Numba 経路と Fallback で同一ロジックを保証する。  
- Fallback（Numba 無効時）は、同じ入力行列を用いて NumPy で計算し、`np.triu_indices` で上三角のみを集計する。Python ループは使用しない。
- 提案 API 例:  
  ```python
  C, stats_vec = collision_kernel_bookkeeping_numba(
      N, s, H, v_rel_scalar, v_rel_matrix, use_matrix_velocity,
      f_ke_matrix, F_lf_matrix,
  )
  # stats_vec: 固定長タプル or 1D array with
  # (E_rel_step, E_dissipated_step, E_retained_step,
  #  f_ke_mean_C, f_ke_energy, F_lf_mean,
  #  n_cratering_rate, n_fragmentation_rate,
  #  frac_cratering, frac_fragmentation)
  ```
  既存 `collision_kernel_numba` は互換性維持のため残し、新簿記カーネルは `marsdisk.physics._numba_kernels` に追加する。

### 3.2 速度場と再利用

- `C` 生成に使う `v_rel`（スカラー/行列）を簿記カーネルへそのまま渡し、`E_rel` 集計と `s_min_surface_energy` 評価に再利用する。再計算は行わない。  
- `s_min_surface_energy` が必要な場合は、簿記カーネルから `v_rel` のレート重み付き代表値を返すか、カーネル内部で `s_min_surface_energy` 候補まで計算して返す。

### 3.3 C_ij と要件メモの対応

上三角和 $\sum_{i \le j} C_{ij}$ をそのまま使用。$(1+\delta)$ 復元は不要。Numba カーネルでも上三角だけを集計する実装とする。

### 3.4 F_lf / f_ke の前計算責務

- `F_lf` 判定・`f_ke` マトリクス生成は **Python→NumPy ベクトル化** で一度だけ計算し、`collision_kernel_bookkeeping_numba` に渡す。  
- 責務候補: `marsdisk.physics.fragments` に「最大残骸分岐 + f_ke 適用行列」を返すヘルパを追加し、`marsdisk.physics.collide` が呼び出して C とともに簿記カーネルへ渡す。  
- これにより、Numba/Fallback のどちらでも同じ入力マトリクスを使い、簿記カウント（n_cratering/n_fragmentation）を一貫させる。

### 3.5 パフォーマンスと上限目安

- 目標: 40–60 ビンで 0D ステップあたりの衝突簿記追加コストを < 10% に抑える。  
- 上三角集計は `n(n+1)/2` オーダー。Numba 経路では prange で上三角を埋めつつ統計を累積し、追加バッファは n×n の f_ke/F_lf 入力を共有するのみで新規テンソルを増やさない（出力統計はスカラ/小ベクトル）。

### 3.6 t_damp の単調性とデフォルト

- 現行案: $t_{\mathrm{damp}} = t_{\mathrm{coll}} / \varepsilon^2$ は、$\varepsilon \to 1$ でも有限で減衰が残る。  
- 代替案（物理直観優先）: $t_{\mathrm{damp}} = t_{\mathrm{coll}} / \max(1-\varepsilon^2, \varepsilon_{\mathrm{floor}})$ で $\varepsilon \to 1$ では発散させる。  
- デフォルトは `enable_e_damping = false` のまま据え置き、導入前にどちらの式を採るか決める。

### 3.7 検証指標

**数値精度チェック**:
$$
E_{\mathrm{numerical\_error\_relative}} = \frac{|E_{\mathrm{diss}} + E_{\mathrm{ret}} - E_{\mathrm{rel}}|}{E_{\mathrm{rel}}}
$$

**閾値設計**:
| レベル | 閾値 | 根拠 |
|---|---|---|
| 警告 | $\varepsilon_{\mathrm{mach}} \times \sqrt{n_{\mathrm{bins}}}$ | 累積丸め誤差の期待値 |
| エラー | $10^{-6}$ | 計算論理のバグ検出 |

- $\varepsilon_{\mathrm{mach}} \approx 2.2 \times 10^{-16}$（倍精度）
- $n_{\mathrm{bins}} = 40$ の場合、警告閾値 $\approx 1.4 \times 10^{-15}$
- 実運用では $10^{-12}$ ～ $10^{-9}$ 程度を観測、$10^{-6}$ 超でエラー

**モニタリング運用**:
- 初期運用で閾値超過頻度を観測し、必要に応じて調整
- 超過時は `out/<run_id>/checks/energy_budget.csv` の該当行に `warning`/`error` フラグを付与

---

## 4. 出力定義

**I/O 方針**: `io.streaming` ON/OFF いずれでも `out/<run_id>/series/run.parquet` と `out/<run_id>/checks/energy_budget.csv` を生成する。`writer`/`streaming` 層に簿記列を追加し、ストリーミング OFF 時でも欠損しないようにする。

- `out/<run_id>/series/run.parquet`: 既存 `writer.write_parquet` の units/definitions に新規列を追加。  
- `out/<run_id>/checks/energy_budget.csv`: `writer` 側に新しい CSV ライタを追加し、ストリーミング OFF でも run 終了時に flush する経路を用意。  
- streaming ON 時は `io/streaming.py` に追加バッファを持たせ、`step_flush_interval` に従い逐次フラッシュする。
- `out/<run_id>/summary.json`/`out/<run_id>/run_card.md`: エネルギー簿記の累積合計と `frac_fragmentation`/`frac_cratering` を集約し、`run_card` に記録する。

### 4.1 series/run.parquet 追加列

| 列名 | 単位 | 定義 |
|---|---|---|
| `E_rel_step` | J/m² | 総衝突相対エネルギー |
| `E_dissipated_step` | J/m² | 散逸エネルギー |
| `E_retained_step` | J/m² | 残存エネルギー |
| `f_ke_mean` | — | 衝突レート重み付き平均（C_ij で重み付け） |
| `f_ke_energy` | — | エネルギー重み付き平均 = `E_retained_step / E_rel_step` |
| `F_lf_mean` | — | 衝突レート重み付き平均 |
| `frac_cratering` | — | 衝突率比 = Σ(C_ij · 1_crat) / ΣC_ij |
| `frac_fragmentation` | — | 衝突率比 = Σ(C_ij · 1_frag) / ΣC_ij |
| `s_min_surface_energy` | m | Krijt & Kama 由来（有効時） |

### 4.2 checks/energy_budget.csv

| 列名 | 単位 | 説明 |
|---|---|---|
| `step` | — | ステップ番号 |
| `time` | s | 通算時刻 |
| `dt` | s | ステップ幅 |
| `E_rel_step` | J/m² | 総衝突相対エネルギー |
| `E_dissipated_step` | J/m² | 散逸エネルギー |
| `E_retained_step` | J/m² | 残存エネルギー |
| `f_ke_mean` | — | ステップ平均 |
| `F_lf_mean` | — | ステップ平均（分岐診断用） |
| `n_cratering` | — | 侵食の衝突率和 Σ(C_ij · 1_crat) |
| `n_fragmentation` | — | 破砕の衝突率和 Σ(C_ij · 1_frag) |
| `frac_cratering` | — | 侵食の衝突率比 = n_cratering / (n_cratering + n_fragmentation) |
| `frac_fragmentation` | — | 破砕の衝突率比 = n_fragmentation / (n_cratering + n_fragmentation) |
| `eps_restitution` | — | 使用した反発係数 |
| `f_ke_eps_mismatch` | — | $|f_{\mathrm{ke,frag}} - \varepsilon^2|$ |
| `E_numerical_error_relative` | — | 数値誤差（相対） |
| `error_flag` | — | `ok` / `warning` / `error` |

### 4.3 系外搬出エネルギー

Phase 2 以降で検討。

---

## 5. スキーマ設計

| パラメータ | 型 | 制約 | 既定値 |
|---|---|---|---|
| `eps_restitution` | float | $(0, 1]$ | 0.5 |
| `f_ke_cratering` | float | $[0, 1]$ | 0.1 |
| `f_ke_fragmentation` | float \| None | $[0, 1]$ | None |
| `enable_e_damping` | bool | — | False |
| `surface_energy.enabled` | bool | — | False |
| `surface_energy.gamma_J_m2` | float | $> 0$ | 1.0 |
| `surface_energy.eta` | float | $(0, 1]$ | 0.1 |
| `energy_bookkeeping.enabled` | bool | — | True |
| `energy_bookkeeping.stream` | bool | — | True（`FORCE_STREAMING_OFF` を優先） |

---

## 6. equations.md 追記

E.047–E.053 を追加（E.053: Krijt & Kama 式）。  
列対応メモ:  
- E.047/E.048 (E_rel 定義) → `E_rel_step`  
- E.049 (E_diss/E_ret) → `E_dissipated_step`, `E_retained_step`  
- E.050 (f_ke 整合) → `f_ke_mean`, `f_ke_energy`, `f_ke_eps_mismatch`  
- E.053 (Krijt & Kama) → `s_min_surface_energy`

---

## 7. 検証基準

| 項目 | 合格条件 |
|---|---|
| 数値精度（警告） | $E_{\mathrm{error}} < \varepsilon_{\mathrm{mach}} \sqrt{n}$ |
| 数値精度（エラー） | $E_{\mathrm{error}} < 10^{-6}$ |
| 侵食 $f_{\mathrm{ke}}$ | $F_{\mathrm{lf}} > 0.5$ で適用 |
| 破砕 $f_{\mathrm{ke}}$ | $F_{\mathrm{lf}} \le 0.5$ で適用 |
| f_ke/ε 整合性 | 不一致時に警告ログ |
| Numba/Fallback 一致 | 同一入力で統計列が一致すること（小ビン数のユニットテストを追加） |
| streaming ON/OFF 一致 | `FORCE_STREAMING_OFF=1` でも energy_budget が生成されること |
| dt 積分の正しさ | rate と step 量の混同がないことを toy テストで確認 |
| ε 極限 | $\varepsilon \to 1$（散逸ゼロ）と $\varepsilon \to 0$（強散逸）で符号・単調性が崩れない |
| α 境界 | $\alpha \le 3$ や $\alpha \approx 5$ で `s_min_surface_energy` が NaN/inf にならない |

---

## 8. Open Questions

### 8.1 t_coll の定義

仮決定: `kernel_minimum_tcoll` を使用。

### 8.2 下流互換

既存の可視化・解析スクリプトへの影響があれば、互換カラムを併存（新列追加のみ、既存列は不変）し、追従作業を別タスクで管理する。

### 8.3 テストシナリオ

- 5ビン固定で単一ペア衝突（固定 C, Y, f_ke, F_lf）を使い、Numba ON/OFF の簿記列一致を検証するユニットテストを追加。  
- streaming ON/OFF で `out/<run_id>/checks/energy_budget.csv` と Parquet 列が同じ値になることを比較する統合テストを追加。
- ε 極限テストと dt 積分テスト（rate/step 混同防止）を追加。
- surface_energy: $\alpha \le 3$ でガードが効くこと、`s_min_surface_energy > s_max` の場合にログすることを確認。

## チェックリスト（実装状況）

### 完了
- [x] 表面エネルギー床（Krijt & Kama）の計算と s_min 統合
- [x] energy_budget の streaming ON/OFF 出力（streaming 時は逐次 append）
- [x] energy_series の streaming 中間フラッシュ（CSV append）
- [x] run_card への主要メタ（git ハッシュ・コマンド・seed・エネルギー合計等）記録
- [x] 追加テスト（surface_energy ガード・energy_series streaming flush 等）

### 完了（フォロー分）
- [x] s_min_surface_energy を series/run.parquet に列追加
- [x] f_ke_fragmentation と eps_restitution^2 の不一致警告ログ出力（閾値判定）
- [x] energy_bookkeeping.stream フラグの適用と streaming=ON 時の energy.parquet 出力整合
- [x] e/i 減衰式を計画仕様（t_coll/eps^2）に合わせるか、採用式の差分を文書化
- [x] equations.md への E.047–E.053 追加とアンカー同期
