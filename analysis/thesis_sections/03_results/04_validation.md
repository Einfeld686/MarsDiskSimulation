<!-- TEX_EXCLUDE_START -->
出力結果は out/temp_supply_sweep_1d/20260120-131832__b6a734509__seed955316828/ 内に保存されている．
<!-- TEX_EXCLUDE_END -->

## 4. 検証：質量保存と停止条件

本節では，数値計算結果の信頼性を確認するため，（i）質量保存の精度と，（ii）停止条件の発火状況を整理する．

### 4.1 質量保存（質量収支ログ）

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau0p5.png}
\includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau1p0.png}
\caption{質量保存誤差の最大値 $\max\epsilon_{\rm mass}$（相対誤差，\%）の比較（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．横軸は初期温度 $T_{M,0}$，棒の色は供給混合係数 $\epsilon_{\rm mix}$ を表す．縦軸は $\max\epsilon_{\rm mass}$ を $10^{-14}\%$ 単位で示した．}
\label{fig:results_mass_budget_error_grid}
\end{figure}

図\ref{fig:results_mass_budget_error_grid}は，パラメータスイープした12ケースにおける $\epsilon_{\rm mass}$ の最大値を比較したものである．全ケースで $\max\epsilon_{\rm mass}<10^{-13}\%$ を満たし，最大でも $9\times 10^{-14}\%$ にとどまった（$T_{M,0}=5000,\mathrm{K}$ かつ $\tau_0=1.0$；表\ref{tab:results_mass_budget_summary}）．この値は，時間刻み制御に用いた許容値 $0.5\%$ に比べて十分小さい．したがって，本章で報告する損失質量 $M_{\rm loss}$ の大小関係は，数値的な質量収支誤差によって支配されないとみなせる．

ここでの質量保存誤差 $\epsilon_{\rm mass}$ は，手法章で定義した式\ref{eq:mass_budget_definition}に基づき，各計算サブステップにおける質量収支の相対ずれ（\%）として評価した．時間刻みは，この相対ずれが各サブステップで $0.5\%$ 以下となるよう自動調整している．

\begin{table}[t]
\centering
\caption{質量保存誤差の要約（パラメータスイープ12ケース）}
\label{tab:results_mass_budget_summary}
\begin{tabular}{lc}
\hline
指標 & 値 \\
\hline
最大値（$T_{M,0}=5000,\mathrm{K}$，$\tau_0=1.0$） & $9\times 10^{-14}\%$ \\
中央値（12ケース） & $3\times 10^{-15}\%$ \\
\hline
\end{tabular}
\end{table}

### 4.2 停止条件の内訳

本章のパラメータスイープ（12ケース）では，計算の停止理由は2種類である．一つは所定の終了時刻 $t_{\rm end}$ への到達であり，もう一つは円盤全体の総損失率 $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}$ が閾値 $\dot{M}_{\rm th}$ を下回ったための打ち切りである．

後者は，$t\ge t_{\min}$ の範囲で $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le \dot{M}_{\rm th}$ を満たした時点で発火する．本スイープでは $t_{\min}=2\,\mathrm{yr}$，$\dot{M}_{\rm th}=10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ を採用した（表\ref{tab:results_sweep_setup}）．さらに本章では追加シンクを無効化しているため $\dot{M}_{\rm sinks}=0$ であり，停止条件は実質的に $\dot{M}_{\rm out}\le \dot{M}_{\rm th}$ に一致する．

また，手法章で述べたセル早期停止（$\tau_{\rm los}>\tau_{\rm stop}$）は，照射近似の適用範囲を逸脱したセルを除外するための判定である．本スイープでは当該条件は一度も満たされず，セル早期停止は発生しなかった．

損失率閾値による停止は6ケースで生じ，いずれも $t\simeq2,\mathrm{yr}$（$t_{\min}$ 到達直後）で停止条件を満たした（表\ref{tab:results_stop_reason_counts}）．一方，累積損失質量 $M_{\rm loss}(t)$ は初期に急増した後，早期に飽和する（本章第5節；図\ref{fig:results_cumloss_grid}）．全ケースで $M_{\rm loss}$ の99%は $t\simeq0.19$--$0.84,\mathrm{yr}$ に到達しており，本章で採用した停止判定は $M_{\rm loss}$ の最終値を大きく左右しない．

加えて，停止時刻以降に残り得る追加損失は $\Delta M_{\rm loss}\le \dot{M}_{\rm th}\Delta t$ と上から抑えられる．例えば停止後に $1\,\mathrm{yr}$ 計算を延長しても，$\Delta M_{\rm loss}\le \dot{M}_{\rm th}\times 1\,\mathrm{yr}\simeq 3.2\times 10^{-7}M_{\rm Mars}$ にとどまる．したがって，以降で議論する $M_{\rm loss}$ のケース間比較は，停止判定の違いによって支配されない．

\begin{table}[t]
\centering
\caption{停止理由の内訳（スイープ12ケース）．「損失率閾値到達」は $t\ge t_{\min}$ かつ $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le \dot{M}_{\rm th}$ を満たす場合を指す（$t_{\min}=2\,\mathrm{yr}$，$\dot{M}_{\rm th}=10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$）．}
\label{tab:results_stop_reason_counts}
\begin{tabular}{lc}
\hline
停止理由 & ケース数 \\
\hline
終了時刻到達（$t=t_{\rm end}$） & 6 \\
損失率閾値到達 & 6 \\
\hline
\end{tabular}
\end{table}

以上より，本節では（i）質量収支誤差が許容値を大きく下回ること，および（ii）停止判定の違いが $M_{\rm loss}$ の最終値を実質的に規定しないことを確認した．次節では，$M_{\rm loss}$ の $T_{M,0}$・$\tau_0$・$\epsilon_{\rm mix}$ に対する感度を要約する．
