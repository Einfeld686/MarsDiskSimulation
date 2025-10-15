> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。

### v_kepler — ケプラー速度 v_K(r)
円盤半径に応じた公転速度を、火星重力パラメータから即時に算出する関数です。
- 用語：ケプラー速度（Keplerian orbital speed）
- 前提：火星標準重力定数 `G` と質量 `M_MARS` を一定とみなし、入力半径 `r>0` を採用する。
- 式と参照：$v_K(r)=\sqrt{G M_{\mathrm{MARS}}/r}$（[marsdisk/grid.py:34]（#L34-L48））
- 入出力と単位：`r` [m] → `v_K` [m s$^{-1}$]
- 数値処理：NumPy の平方根を評価し `float` に変換するのみで、負値入力は未定義として利用者側で防ぐ。

### omega — ケプラー角速度 Ω(r)
0D 半径の局所角速度を、ケプラー解をそのまま返すラッパーです。
- 用語：ケプラー角速度（Keplerian angular frequency）
- 前提：`omega_kepler` の結果をそのまま参照し、火星重力を一定とみなす。
- 式と参照：$\Omega(r)=\sqrt{G M_{\mathrm{MARS}}/r^{3}}$ を別名で返す（[marsdisk/grid.py:90]（#L90-L91））
- 入出力と単位：`r` [m] → `Ω` [rad s$^{-1}$]
- 数値処理：別名関数として委譲するだけで追加の丸めや検証は行わない。

### v_keplerian — ケプラー速度（同義関数）
`v_kepler` と同一計算を別名で公開し、外部 API の記述ゆれに備えます。
- 用語：ケプラー速度別名（Keplerian speed alias）
- 前提：`v_kepler` の実装が正しいと仮定し、その結果を直接返却する。
- 式と参照：$v_K(r)=\sqrt{G M_{\mathrm{MARS}}/r}$ を `v_kepler` に委譲（[marsdisk/grid.py:93]（#L93-L94））
- 入出力と単位：`r` [m] → `v_K` [m s$^{-1}$]
- 数値処理：追加計算は無く、浮動小数変換も呼び先に任せる。

### interp_qpr — Planck平均 ⟨Q_pr⟩ の補間
放射圧効率のテーブルからサイズと温度で二次元補間を行い、欠損時は解析近似へフォールバックします。
- 用語：放射圧効率平均（Planck-averaged radiation pressure efficiency）
- 前提：起動時に読み込んだ `_QPR_TABLE` を保持し、未ロード時のみ `_approx_qpr` に切り替える。
- 式と参照：$⟨Q_{\mathrm{pr}}(s,T_\mathrm{M})⟩ = \mathrm{table.interp}(s,T_\mathrm{M})$（[marsdisk/io/tables.py:253]（#L253-L260））
- 入出力と単位：`s` [m], `T_M` [K] → `⟨Q_pr⟩` [dimensionless]
- 数値処理：NumPy 補間値を `float` 化し、テーブルが無い場合は解析近似へフォールバックする分岐のみ。

### load_qpr_table — ⟨Q_pr⟩表のローダ
外部 CSV/HDF テーブルを読み込み、全体の Planck 平均補間器を更新して戻り値として供給します。
- 用語：放射圧効率テーブルローダ（Planck-mean Q_pr table loader）
- 前提：指定パスの存在を検査し、`QPrTable.from_frame` で正規化されたフレームを生成する。
- 式と参照：$⟨Q_{\mathrm{pr}}⟩_{\mathrm{interp}} = \text{QPrTable.from\_frame}(\text{read}(path))$（[marsdisk/io/tables.py:273]（#L273-L284））
- 入出力と単位：`path` [str or Path] → `callable(s,T_M)` [dimensionless]
- 数値処理：読み込み後にグローバル `_QPR_TABLE` を更新して補間関数を返し、失敗時は例外で通知する。

### marsdisk/physics/surface.py: wyatt_tcoll_S1 (lines 62-73)
```latex
\begin{equation}
 t_{\mathrm{coll}} = \frac{1}{2\,\Omega\,\tau}
\end{equation}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$t_{\mathrm{coll}}$|Wyatt surface-layer collision time|s|Returned value|
|$\Omega$|Keplerian angular frequency|s$^{-1}$|Input, must be positive|
|$\tau$|Vertical optical depth|dimensionless|Input, must be positive|

**Numerics**
- Pure algebraic evaluation with argument validation; raises `MarsDiskError` when $\tau\le0$ or $\Omega\le0$.

### marsdisk/physics/surface.py: step_surface_density_S1 (lines 96-163)
> **適用範囲の注意（既定は無効）**  
> この式群は **光学的に厚いガス円盤の表層**を仮定する Takeuchi & Lin (2003) に基づきます。  
> 当プロジェクトの標準環境（**gas‑poor** な衝突デブリ円盤）では前提が一致しないため、**既定では使用しません**（`ALLOW_TL2003=false`）。  
> ガスが十分に存在すると仮定する対照実験に限り、利用者が明示的に有効化してください。
```latex
\begin{aligned}
 t_{\mathrm{blow}} &= \frac{1}{\Omega},\\
 \lambda &= \frac{1}{t_{\mathrm{blow}}} + I_{\mathrm{coll}}\frac{1}{t_{\mathrm{coll}}} + I_{\mathrm{sink}}\frac{1}{t_{\mathrm{sink}}},\\
 \Sigma^{n+1} &= \min\!\left(\frac{\Sigma^{n} + \Delta t\,\dot{\Sigma}_{\mathrm{prod}}}{1 + \Delta t\,\lambda},\,\Sigma_{\tau=1}\right),\\
 \dot{M}_{\mathrm{out}} &= \Sigma^{n+1} \Omega,\\
\Phi_{\mathrm{sink}} &=
\begin{cases}
\dfrac{\Sigma^{n+1}}{t_{\mathrm{sink}}}, & t_{\mathrm{sink}} > 0,\\[6pt]
0, & \text{otherwise.}
\end{cases}
\end{aligned}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$\Sigma^{n}$|Surface density at start of step|kg m$^{-2}$|Input `sigma_surf`|
|$\Sigma^{n+1}$|Surface density after update|kg m$^{-2}$|Clipped to $\Sigma_{\tau=1}$ when provided|
|$\Delta t$|Time step|s|Input `dt`|
|$\dot{\Sigma}_{\mathrm{prod}}$|Sub-blow-out production rate|kg m$^{-2}$ s$^{-1}$|Input `prod_subblow_area_rate`|
|$t_{\mathrm{blow}}$|Blow-out residence time|s|Equal to $1/\Omega$|
|$t_{\mathrm{coll}}$|Optional collisional loss time|s|Ignored when `None` or non-positive|
|$t_{\mathrm{sink}}$|Optional extra sink time|s|Ignored when `None` or non-positive|
|$I_{\mathrm{coll}}$|Indicator for active collision sink|dimensionless|1 if $t_{\mathrm{coll}}$ supplied and positive, else 0|
|$I_{\mathrm{sink}}$|Indicator for active additional sink|dimensionless|1 if $t_{\mathrm{sink}}$ supplied and positive, else 0|
|$\Sigma_{\tau=1}$|Optical-depth clipping lid|kg m$^{-2}$|Input `sigma_tau1`; if absent no clipping|
|$\dot{M}_{\mathrm{out}}$|Surface outflux|kg m$^{-2}$ s$^{-1}$|Returned as `outflux`|
|$\Phi_{\mathrm{sink}}$|Additional sink flux|kg m$^{-2}$ s$^{-1}$|Returned as `sink_flux`|

**Numerics**
- Implicit Euler for loss terms (IMEX-BDF1 style); production handled explicitly.
- Applies optional optical-depth cap via `min` before flux evaluation.
- Returns outflux and sink flux after clipping; logs step parameters.

When `t_{\mathrm{sink}}` is `None` or non-positive (for example, the CLI passes `cfg.sinks.mode == "none"` through `sinks.total_sink_timescale` which returns `None`; see `marsdisk/run.py#run_zero_d [L273–L1005]` and `marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]`), `step_surface_density_S1` drops the sink indicator so the IMEX loss term consists solely of the blow-out contribution and any active Wyatt collision sink (`marsdisk/physics/surface.py#step_surface_density_S1 [L96–L163]`). In that configuration `sink_flux` evaluates to zero for every step.

**参考**: [無効: gas‑poor 既定] Takeuchi & Lin (2003); Hyodo et al. (2017); Hyodo et al. (2018); Canup & Salmon (2018); Strubbe & Chiang (2006); Kuramoto (2024)

### marsdisk/run.py: effective minimum grain size and beta diagnostics (lines 229-488)
```latex
\begin{equation}
 s_{\min,\mathrm{eff}} = \max\!\left(s_{\min,\mathrm{cfg}},\, s_{\mathrm{blow}},\, s_{\mathrm{sub}}\right)
\end{equation}
```
with the component sizes assembled as `s_min_components = {"config": s_{\min,\mathrm{cfg}}, "blowout": s_{\mathrm{blow}}, "sublimation": s_{\mathrm{sub}}, "effective": s_{\min,\mathrm{eff}}}` (`marsdisk/run.py#_gather_git_info [L242–L266]`). The sublimation term satisfies
```latex
s_{\mathrm{sub}} =
\begin{cases}
\texttt{s\_sub\_boundary}(T_{\mathrm{M}}, T_{\mathrm{sub}}, t_{\mathrm{ref}}=1/\Omega, \rho, \texttt{sub\_params}), & \text{when } \texttt{cfg.sinks.mode} \ne \texttt{\"none\"} \text{ and } \texttt{enable_sublimation}=True,\\
\text{n/a}, & \text{otherwise.}
\end{cases}
```
That is, `fragments.s_sub_boundary` (`marsdisk/physics/fragments.py#s_sub_boundary [L102–L165]`) supplies a sublimation-limited size only when the YAML enables the sink; the runtime dictionary records the placeholder `0.0` to denote “not applicable” when the sink is disabled.

The reported beta diagnostics are computed in two places:
```latex
\beta_{\mathrm{cfg}} = \beta\!\left(s_{\min,\mathrm{cfg}}\right),\qquad
\beta_{\mathrm{eff}} = \beta\!\left(s_{\min,\mathrm{eff}}\right),
```
where `radiation.beta` implements the Stefan–Boltzmann expression and takes the Planck mean `⟨Q_{\mathrm{pr}}⟩` from the current run (`marsdisk/physics/radiation.py#beta [L221–L242]`). Both fields are written to the time series and summary as `beta_at_smin_config` and `beta_at_smin_effective` (`marsdisk/run.py#run_zero_d [L273–L1005]`, `marsdisk/run.py#run_zero_d [L273–L1005]`). The blow-out threshold `beta_threshold` is sourced from the module constant `BLOWOUT_BETA_THRESHOLD` (`marsdisk/physics/radiation.py#BLOWOUT_BETA_THRESHOLD [L32]`) and recorded alongside the betas (`marsdisk/run.py#run_zero_d [L273–L1005]`, `marsdisk/run.py#run_zero_d [L273–L1005]`). The closed-form expression for β is persisted verbatim in `run_config.json["beta_formula"]` as part of the provenance record (`marsdisk/run.py#run_zero_d [L273–L1005]`).

Case classification follows the configuration beta: `case_status = "blowout"` when `beta_at_smin_config >= beta_threshold`, otherwise `"ok"`; exceptional mass-budget failures are escalated separately (`marsdisk/run.py#run_zero_d [L273–L1005]`). This logic matches the recorded summaries used by downstream validation.

**Recorded quantities**

| Quantity (units) | Summary key(s) | Provenance | Notes |
| --- | --- | --- | --- |
| Effective minimum grain size (m) | `s_min_effective`, `s_min_components["effective"]` | `marsdisk/run.py#_gather_git_info [L242–L266]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | Max of config, blow-out, sublimation components |
| Configured minimum grain size (m) | `s_min_config`, `s_min_components["config"]` | `marsdisk/run.py#_gather_git_info [L242–L266]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | YAML `sizes.s_min` from `schema.Sizes` |
| Blow-out limit (m) | `s_blow_m`, `s_min_components["blowout"]` | `marsdisk/run.py#_gather_git_info [L242–L266]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | Uses `radiation.blowout_radius` |
| Sublimation bound (m) | `s_min_components["sublimation"]` | `marsdisk/run.py#_gather_git_info [L242–L266]`, `marsdisk/physics/fragments.py#s_sub_boundary [L102–L165]` | Non-zero only when sublimation sink enabled |
| Beta at config size (dimensionless) | `beta_at_smin_config` | `marsdisk/run.py#run_zero_d [L273–L1005]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | Evaluated with `radiation.beta` |
| Beta at effective size (dimensionless) | `beta_at_smin_effective` | `marsdisk/run.py#run_zero_d [L273–L1005]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | Uses same β function at `s_min_effective` |
| Beta threshold (dimensionless) | `beta_threshold` | `marsdisk/physics/radiation.py#BLOWOUT_BETA_THRESHOLD [L32]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | Constant 0.5 defined in radiation module |
| Mars-facing temperature (K) | `T_M_used`, `T_M_source` | `marsdisk/run.py#load_config [L231–L239]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | CLI or YAML `radiation.TM_K` overrides `temps.T_M` |
| Radiation efficiency (dimensionless) | `Q_pr_used` | `marsdisk/run.py#run_zero_d [L273–L1005]`, `marsdisk/run.py#run_zero_d [L273–L1005]` | Planck mean stored for reference |


### marsdisk/physics/surface.py: compute_surface_outflux (lines 166-175)
```latex
\begin{equation}
 \dot{M}_{\mathrm{out}} = \Sigma_{\mathrm{surf}}\,\Omega
\end{equation}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$\dot{M}_{\mathrm{out}}$|Instantaneous surface outflux|kg m$^{-2}$ s$^{-1}$|Return value|
|$\Sigma_{\mathrm{surf}}$|Current surface density|kg m$^{-2}$|Input `sigma_surf`|
|$\Omega$|Keplerian angular frequency|s$^{-1}$|Input; must be positive|

**Numerics**
- Direct multiplication with argument validation; raises `MarsDiskError` when $\Omega\le0$.

### marsdisk/physics/smol.py: step_imex_bdf1_C3 (lines 18-101)
```latex
\begin{aligned}
 \Lambda_i &= \sum_j C_{ij}, & t_{\mathrm{coll},i} &= \frac{1}{\max(\Lambda_i, 10^{-30})},\\
 \Delta t_{\max} &= \mathrm{safety}\times\min_i t_{\mathrm{coll},i}, & \Delta t_{\mathrm{eff}} &= \min(\Delta t, \Delta t_{\max}),\\
 G_k &= \tfrac{1}{2}\sum_{i,j} C_{ij}\,Y_{kij},\\
 N_i^{n+1} &= \frac{N_i^{n} + \Delta t_{\mathrm{eff}}\left(G_i - S_i\right)}{1 + \Delta t_{\mathrm{eff}}\,\Lambda_i}.
\end{aligned}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$N_i^{n}$|Number surface density in bin $i$ at step start|m$^{-2}$|Input array `N`|
|$N_i^{n+1}$|Updated number surface density|m$^{-2}$|Returned array|
|$C_{ij}$|Collision kernel between bins $i$ and $j$|s$^{-1}$|Input matrix `C`|
|$Y_{kij}$|Fragment mass fraction to bin $k$ from $(i,j)$ collision|dimensionless|Input tensor `Y`|
|$S_i$|Explicit sink term for bin $i$|m$^{-2}$ s$^{-1}$|Input array `S`|
|$G_i$|Gain term from fragment production|m$^{-2}$ s$^{-1}$|Computed internally|
|$\Lambda_i$|Total loss rate for bin $i$|s$^{-1}$|Row sum of `C`|
|$t_{\mathrm{coll},i}$|Collision time per bin|s|Lower bounded via $10^{-30}$ in denominator|
|$\Delta t$|Requested step size|s|Input `dt`|
|$\Delta t_{\max}$|Safety-limited step size|s|`safety` parameter defaults to $0.1$|
|$\Delta t_{\mathrm{eff}}$|Actual step after adaptivity|s|Halved iteratively when constraints violated|
|$\mathrm{safety}$|Fraction of minimum collision time|dimensionless|Default $0.1$|
|$\mathrm{mass\_tol}$|Allowed relative mass error|dimensionless|Default $5\times10^{-3}$|
|$\dot{m}_{<a_{\mathrm{blow}}}$|Sub-blow-out mass production rate|kg m$^{-2}$ s$^{-1}$|Input `prod_subblow_mass_rate` used in mass check|

**Numerics**
- IMEX-BDF1 update: implicit handling of loss via denominator, explicit gain and sink.
- Enforces positivity: halves $\Delta t_{\mathrm{eff}}$ until all $N_i^{n+1}\ge0$.
- Evaluates mass budget error (function C4); adaptively halves $\Delta t_{\mathrm{eff}}$ until error $\le$ `mass_tol`.
- Caps step size relative to minimum collision time using `safety` multiplier.

### marsdisk/physics/smol.py: compute_mass_budget_error_C4 (lines 104-131)
```latex
\begin{aligned}
 M^{n} &= \sum_k m_k N_k^{n}, & M^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta M &= M^{n+1} + \Delta t\,\dot{m}_{<a_{\mathrm{blow}}} - M^{n},\\
 \epsilon_{\mathrm{mass}} &= \frac{|\Delta M|}{M^{n}}.
\end{aligned}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$m_k$|Particle mass for bin $k$|kg|Input array `m`|
|$N_k^{n}$|Pre-step number surface density|m$^{-2}$|Input `N_old`|
|$N_k^{n+1}$|Post-step number surface density|m$^{-2}$|Input `N_new`|
|$\dot{m}_{<a_{\mathrm{blow}}}$|Mass production below blow-out|kg m$^{-2}$ s$^{-1}$|Input `prod_subblow_mass_rate`|
|$\Delta t$|Time interval|s|Input `dt`|
|$M^{n}, M^{n+1}$|Surface mass before/after step|kg m$^{-2}$|Computed internally|
|$\epsilon_{\mathrm{mass}}$|Relative mass budget error|dimensionless|Return value|

**Numerics**
- Validates matching shapes and positivity of $M^{n}$.
- Absolute error used to avoid cancellation sign issues; logs diagnostic values.

### marsdisk/physics/radiation.py: planck_mean_qpr (lines 207-218)
```latex
\langle Q_{\mathrm{pr}}\rangle =
\begin{cases}
 Q_{\mathrm{pr}}, & \text{if an explicit override is supplied},\\
 \mathcal{I}(s, T_{\mathrm{M}}), & \text{if a lookup table or interpolator is available},\\
 1, & \text{otherwise (grey-body default)}.
\end{cases}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$\langle Q_{\mathrm{pr}}\rangle$|Planck-mean radiation-pressure efficiency|dimensionless|Return value|
|$Q_{\mathrm{pr}}$|User-supplied efficiency override|dimensionless|Optional input|
|$\mathcal{I}(s, T_{\mathrm{M}})$|Table interpolation at $(s,T_{\mathrm{M}})$|dimensionless|Uses provided `table` or `interp`, otherwise module cache|
|$s$|Grain size|m|Validated to be positive and finite|
|$T_{\mathrm{M}}$|Mars-facing grain temperature|K|Validated within $[1000, 6000]$; defaults to $2000$ K if `None`|

**Numerics**
- Checks size and temperature bounds; logs when defaults used.
- Lookup arguments clamped to tabulated ranges within `qpr_lookup`; fallback to unity when no table available.

### marsdisk/physics/radiation.py: beta (lines 221-242)
```latex
\begin{equation}
 \beta = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{4\,G\,M_{\mathrm{M}}\,c\,\rho\,s}
\end{equation}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$\beta$|Radiation-pressure to gravity ratio|dimensionless|Return value|
|$\sigma_{\mathrm{SB}}$|Stefan–Boltzmann constant|W m$^{-2}$ K$^{-4}$|`constants.SIGMA_SB`|
|$T_{\mathrm{M}}$|Mars surface temperature|K|Default $2000$ K when `None`|
|$R_{\mathrm{M}}$|Mars radius|m|`constants.R_MARS`|
|$G$|Gravitational constant|m$^{3}$ kg$^{-1}$ s$^{-2}$|`constants.G`|
|$M_{\mathrm{M}}$|Mars mass|kg|`constants.M_MARS`|
|$c$|Speed of light|m s$^{-1}$|`constants.C`|
|$\rho$|Grain material density|kg m$^{-3}$|Defaults to $3000$ when `None`|
|$s$|Grain size|m|Validated positive|
|$\langle Q_{\mathrm{pr}}\rangle$|Planck-mean efficiency|dimensionless|Resolved via `planck_mean_qpr` logic|

**Numerics**
- Relies on validation helpers; reuses planck-mean lookup with optional overrides.
- No additional clamps beyond those in the helper routines.

### marsdisk/physics/radiation.py: blowout_radius (lines 245-259)
```latex
\begin{equation}
 s_{\mathrm{blow}} = \frac{3\,\sigma_{\mathrm{SB}}\,T_{\mathrm{M}}^{4}\,R_{\mathrm{M}}^{2}\,\langle Q_{\mathrm{pr}}\rangle}{2\,G\,M_{\mathrm{M}}\,c\,\rho}
\end{equation}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$s_{\mathrm{blow}}$|Blow-out grain radius|m|Return value|
|$\sigma_{\mathrm{SB}}$|Stefan–Boltzmann constant|W m$^{-2}$ K$^{-4}$|`constants.SIGMA_SB`|
|$T_{\mathrm{M}}$|Mars surface temperature|K|Defaults to $2000$ K when `None`|
|$R_{\mathrm{M}}$|Mars radius|m|`constants.R_MARS`|
|$G$|Gravitational constant|m$^{3}$ kg$^{-1}$ s$^{-2}$|`constants.G`|
|$M_{\mathrm{M}}$|Mars mass|kg|`constants.M_MARS`|
|$c$|Speed of light|m s$^{-1}$|`constants.C`|
|$\rho$|Grain density|kg m$^{-3}$|Defaults to $3000$ when `None`|
|$\langle Q_{\mathrm{pr}}\rangle$|Planck-mean efficiency|dimensionless|Resolved via `_resolve_qpr` at $s=1\,$m if not provided|

**Numerics**
- Uses same validation and lookup as `beta`; clamps from table may apply through shared helper.
- No iteration; direct algebraic evaluation for $\beta=0.5$ threshold.

### marsdisk/physics/shielding.py: effective_kappa (lines 81-120)
```latex
\begin{equation}
 \kappa_{\mathrm{eff}} = \Phi(\tau)\,\kappa_{\mathrm{surf}}
\end{equation}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$\kappa_{\mathrm{eff}}$|Effective surface opacity|m$^{2}$ kg$^{-1}$|Return value|
|$\kappa_{\mathrm{surf}}$|Unshielded surface opacity|m$^{2}$ kg$^{-1}$|Input `kappa`|
|$\Phi(\tau)$|Self-shielding factor|dimensionless|Evaluated via `phi_fn`; defaults to 1 when `phi_fn` is `None`|
|$\tau$|Optical depth used for lookup|dimensionless|Input `tau`|

**Numerics**
- Validates inputs; requires finite values.
- Clamps $\Phi$ to $[0,1]$ after lookup and logs when clipping occurs.

### marsdisk/physics/shielding.py: sigma_tau1 (lines 123-130)
```latex
\Sigma_{\tau=1} =
\begin{cases}
 \kappa_{\mathrm{eff}}^{-1}, & \kappa_{\mathrm{eff}} > 0,\\
 \infty, & \kappa_{\mathrm{eff}} \le 0.
\end{cases}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$\Sigma_{\tau=1}$|Surface density yielding optical depth unity|kg m$^{-2}$|Return value|
|$\kappa_{\mathrm{eff}}$|Effective opacity|m$^{2}$ kg$^{-1}$|Input|

**Numerics**
- Returns infinity when the opacity is non-positive to signal no optical-depth limit; type validation ensures real input.

### marsdisk/physics/shielding.py: apply_shielding (lines 133-216)
```latex
\begin{aligned}
 \Phi &= \Phi(\tau, w_0, g),\\
 \kappa_{\mathrm{eff}} &= \Phi\,\kappa_{\mathrm{surf}},\\
 \Sigma_{\tau=1} &=
 \begin{cases}
 \kappa_{\mathrm{eff}}^{-1}, & \kappa_{\mathrm{eff}} > 0,\\
 \infty, & \kappa_{\mathrm{eff}} \le 0.
 \end{cases}
\end{aligned}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$\kappa_{\mathrm{surf}}$|Unshielded surface opacity|m$^{2}$ kg$^{-1}$|Input|
|$\tau$|Optical depth for the skin|dimensionless|Input|
|$w_0$|Single-scattering albedo|dimensionless|Input|
|$g$|Asymmetry parameter|dimensionless|Input|
|$\Phi(\tau,w_0,g)$|Self-shielding factor|dimensionless|Evaluated via supplied or cached interpolator|
|$\kappa_{\mathrm{eff}}$|Effective opacity|m$^{2}$ kg$^{-1}$|Return value|
|$\Sigma_{\tau=1}$|Optical-depth unity surface density|kg m$^{-2}$|Return value|

**Numerics**
- Validates and, when table metadata available, clamps $\tau$, $w_0$, and $g$ to tabulated ranges before evaluation, logging any adjustments.
- Wraps the interpolator to reuse `effective_kappa` clamping of $\Phi$ to $[0,1]$.

### marsdisk/physics/sublimation.py: mass_flux (implemented by mass_flux_hkl, lines 85-113)
```latex
J(T) =
\begin{cases}
 \alpha_{\mathrm{evap}}\bigl(P_{\mathrm{sat}}(T) - P_{\mathrm{gas}}\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}, &
 \text{if mode}\in\{\text{``hkl'', ``hkl\_timescale''}\} \text{ and HKL activated},\\[10pt]
 \exp\!\left(\dfrac{T - T_{\mathrm{sub}}}{\max(dT, 1)}\right), & \text{otherwise.}
\end{cases}
```
where the saturation vapour pressure is supplied via
```latex
P_{\mathrm{sat}}(T) =
\begin{cases}
 10^{A - B/T}, & \text{if }\texttt{psat\_model} = \text{``clausius''},\\[6pt]
 10^{\mathrm{PCHIP}_{\log_{10}P}(T)}, & \text{if }\texttt{psat\_model} = \text{``tabulated''}.
\end{cases}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$J(T)$|Sublimation mass flux|kg m$^{-2}$ s$^{-1}$|Return value|
|$\alpha_{\mathrm{evap}}$|Evaporation coefficient|dimensionless|`params.alpha_evap`; default 0.007 (Ferguson & Nuth 2012)|
|$P_{\mathrm{sat}}$|Saturation vapour pressure|Pa|Clausius (Kubaschewski 1974) or tabulated (Visscher & Fegley 2013)|
|$P_{\mathrm{gas}}$|Ambient vapour pressure|Pa|`params.P_gas`; default 0 (gas-poor disk; Hyodo et al. 2017, Canup & Salmon 2018)|
|$\mu$|Molar mass|kg mol$^{-1}$|`params.mu`; default 0.0440849 (NIST WebBook, SiO)|
|$R$|Universal gas constant|J mol$^{-1}$ K$^{-1}$|Fixed $8.314462618$|
|$T$|Grain temperature|K|Function argument|
|$T_{\mathrm{sub}}$|Logistic midpoint temperature|K|`params.T_sub`; default 1300|
|$dT$|Logistic width parameter|K|`params.dT`; floored at 1 K|
|$A,B$|Clausius–Clapeyron coefficients|dimensionless / K|Defaults $(13.613, 17850)$ valid for $1270$–$1600$ K (Kubaschewski 1974)|
|$[T_{\min},T_{\max}]$|HKL validity window|K|`params.valid_K`; warning if $T$ outside|
|table|Tabulated $\log_{10}P$ source|—|CSV/JSON with columns `T[K]`, `log10P[Pa]`; monotone PCHIP interpolation|

**Numerics**
- Defaults to a silicon-monoxide HKL branch (SiO dominates the vapour over silicate melts; Melosh 2007) with Clausius coefficients $A=13.613$, $B=17850$ and validity $1270$–$1600$ K; values outside that interval trigger a warning but proceed.
- Enables alternative `psat_model="tabulated"` sourced from CSV/JSON; the loader expects monotonically increasing temperatures and uses a shape-preserving cubic (`scipy.interpolate.PchipInterpolator`) to ensure a smooth, non-oscillatory $\log_{10}P$.
- Chooses HKL branch when the selected `psat_model` is available; otherwise falls back to the logistic placeholder.
- In HKL branch, negative $(P_{\mathrm{sat}}-P_{\mathrm{gas}})$ is clamped to zero before evaluation.
- Logistic branch guards against $dT\to0$ via `max(dT, 1.0)`.
- Stores provenance in `run_config.json` under `sublimation_provenance`, capturing {`sublimation_formula`, `psat_model`, `A`, `B`, `mu`, `alpha_evap`, `P_gas`, `valid_K`, optional `psat_table_path`} for reproducibility.

### marsdisk/physics/sublimation.py: sink_timescale (implemented by s_sink_from_timescale, lines 116-129)
```latex
\begin{aligned}
 J(T) &= \text{mass flux from }\texttt{mass\_flux\_hkl}(T, \text{params}),\\
 s_{\mathrm{sink}} &= \frac{\eta_{\mathrm{instant}}\,t_{\mathrm{ref}}\,J(T)}{\rho}.
\end{aligned}
```
**Symbols**

|Symbol|Meaning|Units|Defaults/Notes|
|---|---|---|---|
|$s_{\mathrm{sink}}$|Instantaneous sink size threshold|m|Return value|
|$\eta_{\mathrm{instant}}$|Fraction defining instant criterion|dimensionless|`params.eta_instant`; default 0.1|
|$t_{\mathrm{ref}}$|Reference timescale|s|Input `t_ref`; typically $1/\Omega$|
|$J(T)$|Sublimation mass flux|kg m$^{-2}$ s$^{-1}$|Computed via `mass_flux_hkl` with same parameters|
|$\rho$|Particle material density|kg m$^{-3}$|Input `rho`; must be positive|
|$T$|Grain temperature|K|Function argument|

**Numerics**
- Validates positivity of $\rho$ and $t_{\mathrm{ref}}$.
- Delegates to `mass_flux_hkl`; inherits its branch selection (HKL versus logistic).
- No additional clamping beyond inherited flux behaviour; linear scaling in $t_{\mathrm{ref}}$.
