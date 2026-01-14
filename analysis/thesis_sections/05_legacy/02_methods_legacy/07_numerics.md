## 5. 数値解法と停止条件

### 5.1 IMEX-BDF(1)

Smoluchowski 衝突カスケードの時間積分には IMEX（implicit-explicit）と BDF(1)（backward differentiation formula）の一次組合せを採用する（[@Krivov2006_AA455_509; @Wyatt2008]）。状態ベクトルはサイズビン $k$ ごとの数密度（または面密度）で表現し、衝突ゲイン・ロスと表層再供給・シンクを同時に組み込む。剛性の強いロス項を陰的に扱うことで安定性を確保し、生成・供給・表層流出は陽的に更新する。

- **剛性項（損失）**: 陰的処理
- **非剛性項（生成・供給）**: 陽的処理
- **ロス項の構成**: 衝突ロスに加え、ブローアウト（$s \le s_{\rm blow}$）と追加シンク（$t_{\rm sink}$）を損失項として組み込む。表層 ODE では $t_{\rm coll}$ と $t_{\rm sink}$ を同一の陰的更新式にまとめる。
- **時間刻み（外側）**: `numerics.dt_init` が外側の結合ステップ $dt$ を与え、温度・遮蔽・供給・相判定・出力などの更新はこの $dt$ で進む。1D では `numerics.dt_min_tcoll_ratio` により $dt \ge \mathrm{ratio}\cdot\min t_{\rm coll}$ の下限を課し、0D ではこの制約を使わない。
- **内部ステップ（Smol）**: IMEX ソルバ内部では $dt_{\rm eff}=\min(dt,\,\mathrm{safety}\cdot\min t_{\rm coll})$ を初期値とし、$N_k<0$ となる場合や質量誤差が許容値を超える場合は $dt_{\rm eff}$ を 1/2 に縮めて再評価する。`smol_dt_eff` として記録され、外側の時間は $dt$ だけ進む。非有限の質量誤差が出た場合は例外として扱う。
- **参考値**: `out/temp_supply_sweep_1d/20260105-180522__2499a82da__seed111066691/T3000_eps0p5_tau0p5`（$\tau\approx0.5$）では `numerics.dt_init=20 s` に対し、初期ステップの $t_{\rm coll,\,min}\approx7.37\times10^{-7}\,\mathrm{s}$、`smol_dt_eff\approx7.37\times10^{-8}\,\mathrm{s}`、`dt_over_t_blow_median\approx7.75\times10^{-3}` を記録した。
- **$t_{\rm coll}$ の扱い**: Smol 経路ではカーネル由来の最短衝突時間（$t_{\rm coll,\,min}$）を $\Delta t$ 制御に用い、表層 ODE 経路では $\tau_{\perp}$ から $t_{\rm coll}$ を評価する。
- **質量検査**: (E.011) を毎ステップ評価し、|error| ≤ 0.5% を `out/checks/mass_budget.csv` に記録する。`safety` に応じて $\Delta t$ は $0.1\min t_{\rm coll}$ に自動クリップされる。
- **高速ブローアウト**: $\Delta t/t_{\rm blow}$ が 3 を超えると `fast_blowout_flag_gt3`、10 を超えると `fast_blowout_flag_gt10` を立てる。`io.correct_fast_blowout=true` の場合は `fast_blowout_factor` を outflux に乗じ、`io.substep_fast_blowout=true` かつ $\Delta t/t_{\rm blow}>\mathrm{substep\_max\_ratio}$（既定 1.0）の場合は $n_{\rm substeps}=\lceil \Delta t/(\mathrm{substep\_max\_ratio}\,t_{\rm blow})\rceil$ に分割して IMEX 更新を行う。診断列は `dt_over_t_blow`/`fast_blowout_factor`/`fast_blowout_corrected`/`n_substeps` を参照する。
- **精度と安定性**: 一次精度（IMEX Euler）で剛性ロス項の安定性を優先し、$\Delta t$ 制御で収束性を担保する。

IMEX-BDF(1) は剛性ロス項で負の数密度が生じるのを防ぐため、ロス項を陰的に扱う設計とする。$N_k<0$ が検出された場合は $dt_{\rm eff}$ を半減して再評価し、許容誤差内の質量検査（C4）を満たした $dt_{\rm eff}$ が採用される。陽的に扱う生成項は衝突の破片生成と供給注入に限定し、質量保存は C4 の検査で逐次確認する。

S9 の数値更新では、衝突ロス・ブローアウト・追加シンクを陰的側に集約し、衝突生成・供給注入を陽的に与える。$\Delta t$ は $t_{\rm coll}$ と $t_{\rm blow}$ の双方を解像するよう制約され、`dt_over_t_blow` と `smol_dt_eff` が診断列として保存される。$dt_{\rm eff}$ が $dt$ より小さい場合でも外側の時間は $dt$ だけ進むため、質量検査は `smol_dt_eff` を使って評価する。

> **詳細**: analysis/equations.md (E.010)–(E.011)  
> **フロー図**: analysis/physics_flow.md §7 "Smoluchowski 衝突積分"

### 5.2 1D（C5）挿入位置・境界条件・$\Delta t$ 制約

run_sweep 既定では `geometry.mode=1D`（`Nr=32`）で半径方向セルを持つが、`numerics.enable_viscosity` は未指定のため C5 は無効で、セル間の結合は行わない。C5 を有効化する場合は、各ステップの局所更新後に半径方向の粘性拡散 `step_viscous_diffusion_C5` を**演算子分割で挿入**する設計とする。

- **境界条件**: 内外端ともにゼロフラックス（Neumann）境界を採用する。
- **$\Delta t$ 制約**: 粘性拡散は $\theta$ 法（既定 $\theta=0.5$ の Crank–Nicolson）で半陰的に解くため、追加の安定制約は課さず、各セルの $t_{\rm coll}$ および `dt_over_t_blow` 制御に従う（run_sweep 既定と同じ）。
- **適用スイッチ**: `numerics.enable_viscosity=true` で C5 を有効化し、未設定時は無効。

C5 は半径方向の面密度拡散を解くため、1D 実行のセル間結合を担当する。数値的には三重対角系の解として実装され、境界条件により質量フラックスの流出入を抑制する。

---
