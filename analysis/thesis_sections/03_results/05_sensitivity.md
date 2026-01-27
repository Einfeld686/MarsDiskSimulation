<!-- TEX_EXCLUDE_START -->
出力結果は out/temp_supply_sweep_1d/20260120-131832__b6a734509__seed955316828/ 内に保存されている．
<!-- TEX_EXCLUDE_END -->

## 5. 累積損失の最終値と依存性

### 5.1 累積損失の時間発展と飽和

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau0p5.png}
  \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau1p0.png}
  \caption{累積損失 $M_{\rm loss}(t)$ の時間発展．上段は $\tau_0=0.5$，下段は $\tau_0=1.0$ を示す．縦軸は $M_{\rm loss}/(10^{-5}M_{\rm Mars})$ を対数表示し，横軸は時間 $t\,[\mathrm{yr}]$ である．各曲線は $(T_{M,0},\epsilon_{\rm mix})$ の組に対応する．曲線が途中で途切れる場合は，停止条件（第4.2節）により計算を終了したことを表す．}
  \label{fig:results_cumloss_grid}
\end{figure}

図\ref{fig:results_cumloss_grid}に，各ケースの $M_{\rm loss}(t)$ を示す．いずれのケースでも $M_{\rm loss}(t)$ は初期に急増し，その後は増加が鈍って $t\lesssim 1\,\mathrm{yr}$ でほぼ頭打ちとなる．計算終了時刻 $t_{\rm end}$ における最終値は $2.0\times10^{-8}$--$1.1\times10^{-4}\,M_{\rm Mars}$ の範囲に分布した．
収束の速さを定量化するため，$M_{\rm loss}(t)$ が $0.99\,M_{\rm loss}(t_{\rm end})$ に到達する時刻を $t_{99}$ と定義すると，$t_{99}=0.19$--$0.84\,\mathrm{yr}$ であった．したがって，停止判定により $t_{\rm end}\simeq 2\,\mathrm{yr}$ で終了するケースでも，その時点までに $M_{\rm loss}(t)$ は十分に飽和している．

### 5.2 最終値一覧と温度・$\tau_0$ 依存性

表\ref{tab:results_sweep_massloss_cases}に，$T_{M,0}$，$\tau_0$，$\epsilon_{\rm mix}$ を掃引した 12 ケースについて，終了時刻 $t_{\rm end}$，停止理由，および累積損失の最終値 $M_{\rm loss}(t_{\rm end})$ をまとめる．以下では，$M_{\rm loss}\equiv M_{\rm loss}(t_{\rm end})$ とする．
まず温度 $T_{M,0}$ に対して $M_{\rm loss}$ は強く依存する．$T_{M,0}$ を $3000\to 4000\,\mathrm{K}$ と増加させると $M_{\rm loss}$ は約 $1.1\times10^{3}$ 倍増大し，さらに $4000\to 5000\,\mathrm{K}$ では約 2.5 倍増大する．一方，同一の $T_{M,0}$ および $\epsilon_{\rm mix}$ で比較すると，$\tau_0=1.0$ の $M_{\rm loss}$ は $\tau_0=0.5$ のほぼ 2 倍である．本シミュレーションの範囲では，最終値は主として $T_{M,0}$ と $\tau_0$ が影響する．
この温度依存性は，放射圧比 $\beta(s)$ を介してブローアウト限界粒径 $s_{\rm blow}$ が変化し，表層からの一次的な除去項が実質的に定まることに対応する（式\ref{eq:surface_outflux}）．また，$\tau_0$ は初期の $\tau_{\rm los}$ の規格化パラメータであり（式\ref{eq:tau_los_definition}），初期表層面密度のスケールを与える．そのため，$\tau_0$ を 2 倍にすると損失対象となる質量も同程度に増え，$M_{\rm loss}$ も概ね比例して増加する．

\begin{table}[t]
\centering
\caption{スイープ12ケースにおける累積損失 $M_{\rm loss}(t_{\rm end})$ と停止条件}
\label{tab:results_sweep_massloss_cases}
\begin{tabular}{cccccc}
\hline
$T_{M,0}$ [K] & $\tau_0$ & $\epsilon_{\rm mix}$ & 停止理由 & $t_{\rm end}$ [yr] & $M_{\rm loss}$ [$M_{\rm Mars}$] \\
\hline
3000 & 0.5 & 1.0 & 終了時刻到達 & 4.92 & $2.04\times 10^{-8}$ \\
3000 & 0.5 & 1.5 & 損失率閾値以下 & 2.00 & $2.04\times 10^{-8}$ \\
3000 & 1.0 & 1.0 & 終了時刻到達 & 4.92 & $4.09\times 10^{-8}$ \\
3000 & 1.0 & 1.5 & 損失率閾値以下 & 2.00 & $4.09\times 10^{-8}$ \\
4000 & 0.5 & 1.0 & 終了時刻到達 & 6.11 & $2.20\times 10^{-5}$ \\
4000 & 0.5 & 1.5 & 損失率閾値以下 & 2.00 & $2.20\times 10^{-5}$ \\
4000 & 1.0 & 1.0 & 終了時刻到達 & 6.11 & $4.41\times 10^{-5}$ \\
4000 & 1.0 & 1.5 & 損失率閾値以下 & 2.00 & $4.41\times 10^{-5}$ \\
5000 & 0.5 & 1.0 & 終了時刻到達 & 6.54 & $5.44\times 10^{-5}$ \\
5000 & 0.5 & 1.5 & 損失率閾値以下 & 2.00 & $5.44\times 10^{-5}$ \\
5000 & 1.0 & 1.0 & 終了時刻到達 & 6.54 & $1.09\times 10^{-4}$ \\
5000 & 1.0 & 1.5 & 損失率閾値以下 & 2.00 & $1.09\times 10^{-4}$ \\
\hline
\end{tabular}
\end{table}

### 5.3 $\epsilon_{\rm mix}$ の影響

表\ref{tab:results_sweep_massloss_cases}より，同一の $(T_{M,0},\tau_0)$ に対して $\epsilon_{\rm mix}=1.0$ と $1.5$ を比較すると，停止時刻 $t_{\rm end}$ は異なる一方で，最終的な累積損失 $M_{\rm loss}$ は一致する．この結果は，基準供給率の定義（式\ref{eq:R_base_definition}）により，表層への注入率 $\dot{\Sigma}_{\rm in}$ が $\epsilon_{\rm mix}$ に依存しないよう規格化されていることと整合する．
したがって，本節で掃引している $\epsilon_{\rm mix}$ は，供給量の大小を直接変えるパラメータではなく，混合係数の定義の取り方に対する感度として解釈される．この設定範囲では，$M_{\rm loss}$ の主要な変動は $T_{M,0}$ と $\tau_0$ により支配され，$\epsilon_{\rm mix}$ の影響は主として過渡的な時間発展や停止判定の違いとして現れるにとどまる．
