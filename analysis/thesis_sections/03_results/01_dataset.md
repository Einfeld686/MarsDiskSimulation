## 1. 実行条件とデータセット

本章の結果は，温度と供給条件を掃引した 1D スイープ計算（計 16 ケース）から得た時系列出力に基づく．本節では，計算条件と主要な評価指標を整理する．

本章では質量を火星質量 $M_{\rm Mars}$ で無次元化し，$M_{\rm loss}$ を $M_{\rm Mars}$ 単位で示す．

### 1.1 パラメータ掃引（temp supply）

温度・初期光学的厚さ・供給混合係数を変えた 16 ケースを計算し，$M_{\rm loss}$ と停止条件の違いを比較する．掃引に用いた主な設定を表\ref{tab:results_sweep_setup}に示す．

\begin{table}[t]
  \centering
  \caption{本章で用いるスイープ計算の主要条件}
  \label{tab:results_sweep_setup}
  \begin{tabular}{ll}
    \hline
    項目 & 値 \\
    \hline
    幾何 & 1D（リング分割），$N_r=32$，$r/R_{\rm Mars} \in [1.0,\,2.7]$ \\
    温度 & 初期 $T_{M,0}\in\{3000,\,4000\}\,\mathrm{K}$，$T_M=2000\,\mathrm{K}$ 到達で停止 \\
    初期光学的厚さ & $\tau_0\in\{0.5,\,1.0\}$（LOS），$\tau_{\rm stop}=2.30$ を超えると早期停止 \\
    供給混合 & $\epsilon_{\rm mix}\in\{0.5,\,1.0\}$ \\
    速度分散初期値 & $i_0\in\{0.05,\,0.10\}$ \\
    追加シンク & 本章のスイープでは無効（$M_{\rm loss}=M_{\rm out,cum}$） \\
    \hline
  \end{tabular}
\end{table}

### 1.2 代表ケースと主要な評価指標

時系列の代表例として，$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$ のケース（$\epsilon_{\rm mix}=1.0$，$i_0=0.05$）を用いる．本章で主に参照する量は以下である．

- 視線方向光学的厚さ $\tau_{\rm los}(t)$ と停止条件（$t_{\rm end}$，停止理由）
- 放射圧流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$
- 収支検査：質量保存誤差（相対誤差％）

<!-- TEX_EXCLUDE_START -->
開発メモ: 数値の転記元は temp_supply スイープ出力（summary.json と series/run.parquet）．
参照 run: out/temp_supply_sweep_1d/20260113-162712__6031b1edd__seed1709094340
<!-- TEX_EXCLUDE_END -->
