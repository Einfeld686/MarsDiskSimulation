
## 1. 実行条件とデータセット

本章の結果は，温度・初期光学的厚さ・供給混合係数を掃引した 1D スイープ計算（計 12 ケース）から得た時系列出力に基づく．本節では，計算条件と主要な評価指標を整理する．

本章では質量を火星質量 $M_{\rm Mars}$ で無次元化し，$M_{\rm loss}$ を $M_{\rm Mars}$ 単位で示す．

### 1.1 パラメータ掃引（温度・供給）

序論では，遷移期の損失評価に対して，(i) 視線方向光学的厚さ $\tau_{\rm los}$ の推定誤差と，(ii) 火星冷却曲線 $T_M(t)$ の形状および有効期間が系統差を与え得ることを指摘した．本章では，これらを代表するパラメータとして初期光学的厚さ $\tau_0$ と初期温度 $T_{M,0}$ を掃引し，$M_{\rm loss}(t_{\rm end})$ の感度として整理する．

温度・初期光学的厚さ・供給混合係数を変えた 12 ケースを計算し，$M_{\rm loss}$ と停止条件の違いを比較する．掃引に用いた主な設定を表\ref{tab:results_sweep_setup}に示す．

\begin{table}[t]
  \centering
  \caption{本章で用いるスイープ計算の主要条件}
  \label{tab:results_sweep_setup}
  \begin{tabular}{ll}
    \hline
    項目 & 値 \\
    \hline
    幾何 & 1D（リング分割），$N_r=32$，$r/R_{\rm Mars} \in [1.0,\,2.7]$ \\
    温度 & 初期 $T_{M,0}\in\{3000,\,4000,\,5000\}\,\mathrm{K}$（温度ドライバに従い時間変化）\\
    初期光学的厚さ & $\tau_0\in\{0.5,\,1.0\}$（$\tau_{\rm los}$：式\ref{eq:tau_los_definition} による初期規格化）\\
    供給混合 & $\epsilon_{\rm mix}\in\{1.0,\,1.5\}$ \\
    速度分散初期値 & $i_0=0.05$ \\
    積分終端 & $t_{\rm end}$：$T_M(t)$ が $T_{\rm end}=2000\,\mathrm{K}$ に到達する時刻（設定：\texttt{numerics.t\_end\_until\_temperature\_K}） \\
    セル早期停止 & $\tau_{\rm los}>\tau_{\rm stop}=\ln 10$（設定：\texttt{optical\_depth.tau\_stop}；本スイープでは未発火） \\
    補助打ち切り（一部） & $t\ge t_{\min}=2\,\mathrm{yr}$ で $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le \dot{M}_{\rm th}=10^{-14}M_{\rm Mars}\,\mathrm{s^{-1}}$（設定：\texttt{numerics.min\_duration\_years}, \texttt{numerics.mass\_loss\_rate\_stop\_Mmars\_s}） \\
    追加シンク & 本章のスイープでは無効（$M_{\rm loss}=M_{\rm out,cum}$） \\
    \hline
  \end{tabular}
\end{table}

### 1.2 代表ケースと主要な評価指標

時系列の代表例として，$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$ のケース（$\epsilon_{\rm mix}=1.0$，$i_0=0.05$）を用いる．本章で主に参照する量は以下である．

- 視線方向光学的厚さ $\tau_{\rm los}(t)$ と停止条件（$t_{\rm end}$，停止理由）
- 放射圧流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$（本章では追加シンクが無効のため $M_{\rm loss}=M_{\rm out,cum}$）
- 収支検査：質量保存誤差（相対誤差％）
