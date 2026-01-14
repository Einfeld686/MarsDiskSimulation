## 2. 状態変数と定義

### 2.1 粒径分布 (PSD) グリッド

PSD は衝突カスケードの統計的記述に基づき、自己相似分布の枠組み [@Dohnanyi1969_JGR74_2531] と離散化の実装例 [@Krivov2006_AA455_509] を踏まえて対数ビンで表す。ブローアウト近傍の波状構造（wavy）はビン幅に敏感であるため、格子幅の指針 [@Birnstiel2011_AA525_A11] を参照して分解能を選ぶ。
初期 PSD の既定は、衝突直後の溶融滴優勢と微粒子尾を持つ分布 [@Hyodo2017a_ApJ845_125] を反映し、溶融滴由来のべき分布は衝突起源の傾きを [@Jutzi2010_Icarus207_54] に合わせて設定する。

PSD は $n(s)$ を対数等間隔のサイズビンで離散化し、面密度・光学的厚さ・衝突率の評価を一貫したグリッド上で行う。隣接比 $s_{i+1}/s_i \lesssim 1.2$ を推奨し、供給注入と破片分布の双方がビン分解能に依存しないように設計する。PSD グリッドの既定値は表\ref{tab:psd_grid_defaults}に示す。

\begin{table}[t]
  \centering
  \caption{PSD グリッドの既定値}
  \label{tab:psd_grid_defaults}
  \begin{tabular}{p{0.36\textwidth} p{0.2\textwidth} p{0.32\textwidth}}
    \hline
    設定キー & 既定値 & glossary 参照 \\
    \hline
    \texttt{sizes.s\_min} & 1e-6 m & G.A05 (blow-out size) \\
    \texttt{sizes.s\_max} & 3.0 m & — \\
    \texttt{sizes.n\_bins} & 40 & — \\
    \hline
  \end{tabular}
\end{table}

- PSD は正規化分布 $n_k$ を保持し、表層面密度 $\Sigma_{\rm surf}$ を用いて実数の数密度 $N_k$（#/m$^2$）へスケールする。スケーリングは $\sum_k m_k N_k = \Sigma_{\rm surf}$ を満たすように行う。
- Smol 経路の時間積分は $N_k$ を主状態として実行し、`psd_state_to_number_density` → IMEX 更新 → `number_density_to_psd_state` の順に $n_k$ へ戻す。したがって、$n_k$ は形状情報として保持され、時間積分そのものは $N_k$ に対して行われる。
- **有効最小粒径**は (E.008) の $s_{\min,\mathrm{eff}}=\max(s_{\min,\mathrm{cfg}}, s_{\mathrm{blow,eff}})$ を標準とする。昇華境界 $s_{\rm sub}$ は ds/dt のみで扱い、PSD 床はデフォルトでは上げない（動的床を明示的に有効化した場合のみ適用）（[@WyattClarkeBooth2011_CeMDA111_1; @Wyatt2008]）。
- `psd.floor.mode` は (E.008) の $s_{\min,\mathrm{eff}}$ を固定/動的に切り替える。`sizes.evolve_min_size` は昇華 ds/dt などに基づく **診断用** の $s_{\min}$ を追跡し、既定では PSD 床を上書きしない。
- 供給注入は PSD 下限（$s_{\min}$）より大きい最小ビンに集約し、質量保存と面積率の一貫性を保つ（[@WyattClarkeBooth2011_CeMDA111_1; @Krivov2006_AA455_509]）。
- `wavy_strength>0` で blow-out 近傍の波状（wavy）構造を付加し、`tests/integration/test_surface_outflux_wavy.py::test_blowout_driven_wavy_pattern_emerges` で定性的再現を確認する（[@ThebaultAugereau2007_AA472_169]）。
- 既定の 40 ビンでは隣接比が約 1.45 となるため、高解像（$\lesssim 1.2$）が必要な場合は `sizes.n_bins` を増やす。

PSD は形状（$n_k$）と規格化（$\Sigma_{\rm surf}$）を分離して扱うため、衝突解法と供給注入は同一のビン定義を共有しつつ、面密度の時間発展は独立に制御できる。これにより、供給・昇華・ブローアウトによる総質量変化と、衝突による分布形状の再配分を明示的に分離する（[@Krivov2006_AA455_509]）。

> **詳細**: analysis/config_guide.md §3.3 "Sizes"  
> **用語**: analysis/glossary.md "s", "PSD"

### 2.2 光学的厚さ $\tau$ の定義

光学的厚さは用途ごとに以下を使い分ける（[@StrubbeChiang2006_ApJ648_652; @Wyatt2008]）。

- **垂直方向**: $\tau_{\perp}$ は表層 ODE の $t_{\rm coll}=1/(\Omega\tau_{\perp})$ に用いる。実装では $\tau_{\rm los}$ から $\tau_{\perp}=\tau_{\rm los}/\mathrm{los\_factor}$ を逆算して適用する。
- **火星視線方向**: $\tau_{\rm los}=\tau_{\perp}\times\mathrm{los\_factor}$ を遮蔽・温度停止・供給フィードバックに用いる。
- Smol 経路では $t_{\rm coll}$ をカーネル側で評価し、$\tau_{\rm los}$ は遮蔽とゲート判定の診断量として扱う。

$\tau$ に関するゲート・停止・診断量は次のように区別する。

- **$\tau_{\rm gate}$**: ブローアウト有効化のゲート。$\tau_{\rm los}\ge\tau_{\rm gate}$ の場合は放射圧アウトフローを抑制する（停止しない）。
- **$\tau_{\rm stop}$**: 計算停止の閾値。$\tau_{\rm los}>\tau_{\rm stop}$ でシミュレーションを終了する。
- **$\Sigma_{\tau=1}$**: $\kappa_{\rm eff}$ から導出する診断量。初期化や診断の参照に使うが、標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない。
- **$\tau_0=1$**: 初期化のスケーリング目標で、`init_tau1.scale_to_tau1=true` のときに $\tau_{\rm los}$ または $\tau_{\perp}$ を指定して用いる。

$\tau_{\rm los}$ は遮蔽（$\Phi$）の入力として使われるほか、放射圧ゲート（$\tau_{\rm gate}$）や停止条件（$\tau_{\rm stop}$）の判定に用いる。$\Sigma_{\tau=1}$ は診断量として保存し、初期化や診断に参照するが、標準の時間発展では $\Sigma_{\rm surf}$ を直接クリップしない。

> **参照**: analysis/equations.md（$\tau_{\perp}$ と $\tau_{\rm los}$ の定義）, analysis/physics_flow.md §6

---
