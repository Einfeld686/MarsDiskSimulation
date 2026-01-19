## 3. 表層への質量供給

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/supply.py, marsdisk/physics/phase.py, marsdisk/physics/shielding.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @CanupSalmon2018_SciAdv4_eaar6887 -> paper/references/CanupSalmon2018_SciAdv4_eaar6887.pdf | 用途: 衝突条件と衝突角の範囲
- @Hyodo2017b_ApJ851_122 -> paper/references/Hyodo2017b_ApJ851_122.pdf | 用途: 非赤道円盤とJ2歳差スケール
- @WyattClarkeBooth2011_CeMDA111_1 -> paper/references/WyattClarkeBooth2011_CeMDA111_1.pdf | 用途: 供給率のパラメータ化
<!-- TEX_EXCLUDE_END -->

---
### 3.1 表層再供給と輸送

表層再供給（supply）は表層への面密度生成率として与え、サイズ分布と深層輸送を通じて PSD に注入する。ここでの表層再供給は外側からの流入を精密に表すものではなく、深部↔表層の入れ替わりを粗く表現するためのパラメータ化である。定常値・べき乗・テーブル・区分定義の各モードを用意し、温度・$\tau$ フィードバック・有限リザーバを組み合わせて非定常性を表現する（[@WyattClarkeBooth2011_CeMDA111_1]）。

先行研究は、Phobos/Deimos を形成しうる衝突条件として、Vesta-Ceres 級の衝突体による斜め衝突が必要であり、成功例が衝突角 30-60$^{\circ}$ に分布することを示している（[@CanupSalmon2018_SciAdv4_eaar6887]）。衝突前の火星が無視できない自転を持ち、その自転軸が衝突で与えられる角運動量ベクトルと一致しない場合、生成円盤の平均軌道面は火星赤道面から傾いた非赤道円盤になりうるため、粒子の軌道傾斜角（inclination, $i$）には平均値とばらつきが生じる（[@Hyodo2017b_ApJ851_122]）。さらに火星の扁平率 $J_2$ による節点歳差を考えると、$a\sim2-10\,R_{\rm Mars}$、$e\sim0.5-0.9$ の範囲では歳差の時間スケールが 1-100 年程度であり、傾斜角に依存する見積もりが与えられている（[@Hyodo2017b_ApJ851_122]）。したがって本研究が対象とする数年-10年の時間範囲では、衝突直後に生じた傾斜角のばらつきが残存し、その鉛直方向の運動が内部の物質を光が比較的通りやすい表層へ運び続ける過程が起こりうると考え、本研究ではこれを表層再供給としてパラメータ化して取り込む。具体的には、光学的厚さ $\tau\simeq1$ に対応する初期表層面密度 $\Sigma_{\tau=1,0}(r)$ を質量スケール、局所公転周期 $T_{\rm orb}(r)$ を時間スケールとして、1 公転あたりに $\Sigma_{\tau=1,0}$ の $f_{\rm orb}$ を補充する規格化を
\[
\dot{\Sigma}_{\rm target}(r)=\mu_{\rm orb} f_{\rm orb}\,\frac{\Sigma_{\tau=1,0}(r)}{T_{\rm orb}(r)}
\]
と置く（$\mu_{\rm orb}$ は強度の不確かさを吸収する無次元パラメータ）。以下では $\Sigma_{\tau=1,0}$ を $\Sigma_{\rm ref}$ として扱い、式\ref{eq:supply_mu_orbit}の実装に接続する。

供給の基礎率は式\ref{eq:prod_rate_definition}で定義する（再掲: E.027）（[@WyattClarkeBooth2011_CeMDA111_1]）。

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\mathrm{prod}}(t,r) = \max\!\left(\epsilon_{\mathrm{mix}}\;R_{\mathrm{base}}(t,r),\,0\right)
\end{equation}

- 供給率は `const` / `powerlaw` / `table` / `piecewise` モードで指定する。
- `const` は `mu_orbit10pct` を基準に、参照光学的厚さ (`mu_reference_tau`) に対応する表層密度の `orbit_fraction_at_mu1` を 1 公転で供給する定義に統一する。
- 旧 μ (E.027a) は診断・ツール用の導出値としてのみ扱う。
- ここでの μ（供給式の指標）は衝突速度外挿の μ と別であり、混同しないよう区別して扱う。

`run_sweep.cmd`（`run_temp_supply_sweep.cmd` 経由）の既定では `supply.mode=const` を採り、`mu_orbit10pct` による正規化で名目供給率を決める。参照光学的厚さ $\mu_{\rm ref}=\texttt{mu_reference_tau}$ を用いて、表層の基準面密度は
\begin{equation}
\label{eq:supply_sigma_ref_mu}
\Sigma_{\rm ref}=\frac{\mu_{\rm ref}}{\kappa_{\rm eff,ref}\,\mathrm{los\_factor}},
\qquad
\kappa_{\rm eff,ref}=\Phi(\mu_{\rm ref})\,\kappa_{\rm surf}
\end{equation}
と置く（$\Phi$ は遮蔽係数、遮蔽無効時は $\Phi=1$）。この $\Sigma_{\rm ref}$ に対して、1 公転あたりの補充率 $f_{\rm orb}=\texttt{orbit_fraction_at_mu1}$ と $\mu_{\rm orbit10pct}$ を掛けた目標供給率は
\begin{equation}
\label{eq:supply_mu_orbit}
\dot{\Sigma}_{\rm target}=\mu_{\rm orbit10pct}\,f_{\rm orb}\,\frac{\Sigma_{\rm ref}}{T_{\rm orb}}
\end{equation}
となる。実装では `supply.const.prod_area_rate_kg_m2_s` を $\dot{\Sigma}_{\rm target}/\epsilon_{\rm mix}$ に設定するため、式\ref{eq:prod_rate_definition}の混合後に $\dot{\Sigma}_{\rm prod}=\dot{\Sigma}_{\rm target}$ が回復する。`EPS_LIST` で与える $\epsilon_{\rm mix}$ はケースごとに上書きされる。

供給は「名目供給→混合（$\\epsilon_{\\mathrm{mix}}$）→温度スケール→$\\tau$ フィードバック→有限リザーバ→深層/表層への配分」の順に評価される。供給が深層へ迂回した場合でも、表層面密度と PSD の更新は同一タイムステップ内で整合的に行われる。
- S8 に対応する供給処理では、`supply_rate_nominal` を基準に `supply_rate_scaled`（温度・$\\tau$ フィードバック後）を評価し、相状態による `allow_supply` ゲートと深層輸送を経て `supply_rate_applied` を表層へ注入する。
- deep mixing が有効な場合は\newline `prod_rate_diverted_to_deep`\newline `deep_to_surf_flux` で深層からの再注入を記録し、\newline 表層面密度への寄与は `prod_rate_applied_to_surf` として診断する。
- これらの列は supply の順序が図 3.2 と一致していることの検算に用いる。

- **詳細**: analysis/equations.md (E.027), (E.027a)  
- **用語**: analysis/glossary.md G.A11 (epsilon_mix)  
- **設定**: analysis/config_guide.md §3.7 "Supply"

#### 3.1.1 フィードバック制御 (Supply Feedback)

`supply.feedback.enabled=true` で $\tau$ 目標に追従する比例制御を有効化する。設定項目は次の表に示す。

\begin{table}[t]
  \centering
  \caption{供給フィードバックの設定}
  \label{tab:supply_feedback_settings}
  \begin{tabular}{p{0.4\textwidth} p{0.36\textwidth} p{0.14\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.feedback.target\_tau} & 目標光学的厚さ & 0.9 \\
    \texttt{supply.feedback.gain} & 比例ゲイン & 1.2 \\
    \texttt{supply.feedback.response}\newline \texttt{\_time\_years} & 応答時定数 [yr] & 0.4 \\
    \texttt{supply.feedback.tau\_field} & $\tau$ 評価フィールド (\texttt{tau\_los}) & \texttt{tau\_los} \\
    \texttt{supply.feedback.min\_scale}\newline \texttt{supply.feedback.max\_scale} & スケール係数の上下限 & 1e-6 / 10.0 \\
    \hline
  \end{tabular}
\end{table}

- `supply_feedback_scale` 列にステップごとのスケール係数を出力する。
- フィードバックは供給ゲートの**上流**で適用され、$\tau_{\rm stop}$ 超過時は停止判定が優先される。

#### 3.1.2 温度カップリング (Supply Temperature)

`supply.temperature.enabled=true` で火星温度に連動した供給スケーリングを有効化する。\newline 温度カップリングの設定項目は次の表にまとめる。

- `mode=scale`: べき乗スケーリング $(T/T_{\rm ref})^{\alpha}$
- `mode=table`: 外部 CSV テーブルから補間

\begin{table}[t]
  \centering
  \caption{温度カップリングの設定}
  \label{tab:supply_temperature_settings}
  \begin{tabular}{p{0.46\textwidth} p{0.44\textwidth}}
    \hline
    設定キー & 意味 \\
    \hline
    \texttt{supply.temperature.reference\_K} & 基準温度 [K] \\
    \texttt{supply.temperature.exponent} & べき指数 $\alpha$ \\
    \texttt{supply.temperature.floor}\newline \texttt{supply.temperature.cap} & スケール係数の下限・上限 \\
    \hline
  \end{tabular}
\end{table}

#### 3.1.3 リザーバと深層ミキシング

`supply.reservoir.enabled=true` で有限質量リザーバを追跡する。\newline `supply.transport.mode=deep_mixing` を選択すると、供給は深層リザーバに蓄積された後、ミキシング時間 `t_mix_orbits` 公転で表層へ放出される。$\tau=1$ 超過は停止判定で扱う。

- `depletion_mode=hard_stop`: リザーバ枯渇で供給ゼロ
- `depletion_mode=taper`: 残量に応じて漸減（`taper_fraction` で制御）

#### 3.1.4 注入パラメータ

注入パラメータは次の表に示す。

\begin{table}[t]
  \centering
  \caption{注入パラメータの設定}
  \label{tab:supply_injection_settings}
  \begin{tabular}{p{0.40\textwidth} p{0.32\textwidth} p{0.18\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.injection.mode} & \texttt{min\_bin}\newline \texttt{powerlaw\_bins} & \texttt{powerlaw\_bins} \\
    \texttt{supply.injection.q} & べき指数（衝突カスケード断片） & 3.5 \\
    \texttt{supply.injection.s\_inj}\newline \texttt{\_min}\newline \texttt{supply.injection.s\_inj}\newline \texttt{\_max} & 注入サイズ範囲 [m] & 自動 \\
    \texttt{supply.injection.velocity}\newline \texttt{.mode} & \texttt{inherit} / \texttt{fixed\_ei}\newline \texttt{/ factor} & \texttt{inherit} \\
    \hline
  \end{tabular}
\end{table}

注入モードは PSD 形状の境界条件として働くため、供給率とビン解像度の整合が重要である。感度試験では注入指数 $q$ と最小注入サイズを変化させ、ブローアウト近傍の wavy 構造や質量収支への影響を評価する。
