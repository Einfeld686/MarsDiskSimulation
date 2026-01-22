<!-- TEX_EXCLUDE_START -->
> **文書種別**: 結果（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

<!--
NOTE: このファイルは analysis/thesis_sections/03_results/*.md の結合で生成する．
編集は分割ファイル側で行い，統合は `python -m analysis.tools.merge_results_sections --write` を使う．
-->

# 結果

本章では，手法章で定義した軸対称 1D（リング分割）モデルに基づく数値結果を整理する．主な関心は，遷移期における放射圧による質量損失の累積量 $M_{\rm loss}$ と，それが温度や光学的厚さにどう依存するかである．粒径分布（PSD）の時間発展は，代表ケースのスナップショットと blow-out 近傍の定性的特徴（“wavy”）に限定し，定量評価は $\tau_{\rm los}(t)$ と $\dot{M}_{\rm out}(t)$，および $M_{\rm loss}$ の時系列・集計値に焦点を当てる．

## 構成

1. 実行条件とデータセット
2. 主要時系列と累積量
3. 粒径分布（PSD）の時間発展
4. 検証：質量保存と停止条件
5. 感度解析
6. 小結
## 1. 実行条件とデータセット

本章の結果は，温度と供給条件を掃引した 1D スイープ計算（計 16 ケース）から得た時系列出力に基づく．本節では，計算条件と主要な評価指標を整理する．

本章では質量を火星質量 $M_{\mathrm{M}}$ で無次元化し，$M_{\rm loss}$ を $M_{\mathrm{M}}$ 単位で示す．

### 1.1 パラメータ掃引（temp\_supply）

温度・初期光学的厚さ・供給混合係数を変えた 16 ケースを計算し，$M_{\rm loss}$ と停止条件の違いを比較する．掃引に用いた主な設定を表\ref{tab:results_sweep_setup}に示す．

\begin{table}[t]
  \centering
  \caption{本章で用いるスイープ計算の主要条件}
  \label{tab:results_sweep_setup}
  \begin{tabular}{ll}
    \hline
    項目 & 値 \\
    \hline
    幾何 & 1D（リング分割），$N_r=32$，$r/R_M \in [1.0,\,2.7]$ \\
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
## 2. 主要時系列と累積量

本節では，代表ケースの主要時系列をまとめる．とくに，視線方向光学的厚さ $\tau_{\rm los}(t)$ の推移と停止条件，放射圧流出率 $\dot{M}_{\rm out}(t)$，および累積損失 $M_{\rm loss}(t)$ を示す．

### 2.1 光学的厚さの推移と停止

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{代表ケースにおける $\tau_{\rm los}(t)$ の推移．}
  \label{fig:results_tau_los_timeseries}
\end{figure}

代表ケース（$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$）では，$\tau_{\rm los}$ は初期の $\tau_{\rm los}\approx 1.0$ から単調に増加し，$\tau_{\rm stop}=2.30$ に到達して $t_{\rm end}\approx 1.27\,\mathrm{yr}$ で早期停止した．一方，$\tau_0=0.5$ の場合は $\tau_{\rm stop}$ に達せず，$T_M=2000\,\mathrm{K}$ 到達まで積分が継続した．

### 2.2 放射圧流出率と累積損失

表層放射圧により除去される質量流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$ を図\ref{fig:results_outflux_and_cumloss}に示す．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{代表ケースにおける放射圧流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$ の時系列．}
  \label{fig:results_outflux_and_cumloss}
\end{figure}

\begin{table}[t]
  \centering
  \caption{代表ケースの終端要約}
  \label{tab:results_representative_summary}
  \begin{tabular}{p{0.50\textwidth} p{0.40\textwidth}}
    \hline
    指標 & 値 \\
    \hline
    停止理由 & $\tau_{\rm los}>\tau_{\rm stop}$（$\tau_{\rm stop}=2.30$） \\
    終端時刻 $t_{\rm end}$ & $1.27\,\mathrm{yr}$ \\
    累積損失 $M_{\rm loss}(t_{\rm end})$ & $1.56\times 10^{-5}\,M_{\mathrm{M}}$ \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \caption{初期光学的厚さ $\tau_0$ の違いによる比較（$T_{M,0}=4000\,\mathrm{K}$）}
  \label{tab:results_tau0_comparison}
  \begin{tabular}{cccc}
    \hline
    $\tau_0$ & 停止理由 & $t_{\rm end}$ [yr] & $M_{\rm loss}$ [$M_{\mathrm{M}}$] \\
    \hline
    0.5 & $T_M=2000\,\mathrm{K}$ 到達 & 6.11 & $7.78\times 10^{-6}$ \\
    1.0 & $\tau_{\rm los}>\tau_{\rm stop}$ & 1.27 & $1.56\times 10^{-5}$ \\
    \hline
  \end{tabular}
\end{table}
## 3. 粒径分布（PSD）の時間発展

本節では，粒径分布（particle size distribution; PSD）の時間発展を示す．とくに，blow-out 近傍での粒子除去が引き起こす PSD の非滑らかな構造（いわゆる “wavy” 構造）が，時間発展の中でどの程度現れるかを確認する．

### 3.1 PSD スナップショット

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{基準ケースにおける PSD の時間発展スナップショット（例：$t=t_0$，$t=t_{\rm mid}$，$t=t_{\rm end}$）．}
  \label{fig:results_psd_snapshots}
\end{figure}

### 3.2 “wavy” 構造の定性的再現

図\ref{fig:results_psd_snapshots}では，$s_{\rm blow}$ 近傍で隣接ビン間の過不足が交互に現れる傾向（wavy）が見られる．本研究では，この振る舞いを blow-out 即時消滅境界がもたらす定性的な特徴として位置づけ，モデル検証の一項目として扱う．

<!-- TEX_EXCLUDE_START -->
開発メモ: “wavy 指標” の数値定義と具体値（例：隣接比の標準偏差など）は，検証節の表にまとめて記載する．
<!-- TEX_EXCLUDE_END -->
## 4. 検証：質量保存と停止条件

本節では，結果の信頼性を担保するために，（i）質量保存，（ii）停止条件の内訳を確認する．

### 3.1 質量保存（質量収支ログ）

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{代表ケースにおける質量保存誤差（相対誤差％）の時系列．}
  \label{fig:results_mass_budget_error}
\end{figure}

スイープ 16 ケースでは，質量保存誤差の最大値は $7\times 10^{-15}\%$ 程度であり，許容誤差 $0.5\%$ を十分に下回る．したがって，本章で報告する $M_{\rm loss}$ は収支誤差によって支配されていない．

\begin{table}[t]
  \centering
  \caption{質量保存誤差の要約（スイープ 16 ケース）}
  \label{tab:results_mass_budget_summary}
  \begin{tabular}{lc}
    \hline
    指標 & 値 \\
    \hline
    最大誤差（16 ケース中） & $6.81\times 10^{-15}\%$ \\
    \hline
  \end{tabular}
\end{table}

### 3.2 停止条件の内訳

本章のスイープでは，停止は二種類に分類された．（i）$T_M=2000\,\mathrm{K}$ 到達（$t_{\rm end}$ 到達），（ii）$\tau_{\rm los}$ が $\tau_{\rm stop}=2.30$ を超過したための早期停止である．停止条件の違いは累積損失の積分区間を変えるため，感度解析の解釈に影響する．

\begin{table}[t]
  \centering
  \caption{停止条件の内訳（スイープ 16 ケース）}
  \label{tab:results_stop_reason_counts}
  \begin{tabular}{lc}
    \hline
    停止理由 & ケース数 \\
    \hline
    $T_M=2000\,\mathrm{K}$ 到達（$t_{\rm end}$） & 8 \\
    $\tau_{\rm los}>\tau_{\rm stop}$（早期停止） & 8 \\
    \hline
  \end{tabular}
\end{table}
## 5. 感度解析

本節では，表\ref{tab:results_sweep_setup}の 16 ケースを用いて，$M_{\rm loss}$ が主要パラメータにどう依存するかを要約する．

### 4.1 累積損失 $M_{\rm loss}$ の温度・$\tau_0$ 依存性

表\ref{tab:results_sweep_massloss_core}に，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ ごとに平均した $M_{\rm loss}$ と停止時刻を示す．本スイープでは，$T_{M,0}=4000\,\mathrm{K}$ のケースで $M_{\rm loss}$ が $10^{-5}$ オーダーに達する一方，$T_{M,0}=3000\,\mathrm{K}$ では $10^{-9}$ オーダーと小さく，温度依存性が卓越する．また，$\tau_0=1.0$ のケースでは $\tau_{\rm los}$ が閾値に到達して早期停止し，積分区間が短いにもかかわらず $M_{\rm loss}$ が増大する傾向が見られる．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/placeholder.pdf}
  \caption{感度解析の要約図（例）：$T_{M,0}$ と $\tau_0$ に対する $M_{\rm loss}$ の比較．}
  \label{fig:results_sensitivity_summary}
\end{figure}

\begin{table}[t]
  \centering
  \caption{温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ に対する $M_{\rm loss}$ の感度（16 ケースの平均）}
  \label{tab:results_sweep_massloss_core}
  \begin{tabular}{ccccc}
    \hline
    $T_{M,0}$ [K] & $\tau_0$ & 停止理由 & $t_{\rm end}$ [yr] & $M_{\rm loss}$ [$M_{\mathrm{M}}$] \\
    \hline
    3000 & 0.5 & $T_M=2000\,\mathrm{K}$ 到達 & 4.92 & $3.14\times 10^{-9}$ \\
    3000 & 1.0 & $\tau_{\rm los}>\tau_{\rm stop}$ & 2.53 & $6.29\times 10^{-9}$ \\
    4000 & 0.5 & $T_M=2000\,\mathrm{K}$ 到達 & 6.11 & $7.78\times 10^{-6}$ \\
    4000 & 1.0 & $\tau_{\rm los}>\tau_{\rm stop}$ & 1.27 & $1.56\times 10^{-5}$ \\
    \hline
  \end{tabular}
\end{table}

### 4.2 $\epsilon_{\rm mix}$ と $i_0$ の影響

同一の $(T_{M,0},\tau_0)$ に対して $\epsilon_{\rm mix}$ と $i_0$ を変えても，$M_{\rm loss}$ の変動幅は相対的に $\lesssim 3\times 10^{-4}$ と小さかった．したがって，本スイープ設定の範囲では，$M_{\rm loss}$ は主に $T_{M,0}$ と $\tau_0$ によって支配される．
## 6. 小結

本章では，軸対称 1D モデルを用いたスイープ計算により，放射圧流出に伴う累積損失 $M_{\rm loss}$ の大きさと依存性を示した．時間の都合上，PSD の詳細な時間発展は扱わず，$\tau_{\rm los}(t)$ と $M_{\rm loss}$ の診断に基づいて整理した．得られた主要結果を以下に要約する．

- 代表ケース（$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$）では，$\tau_{\rm los}$ が $\tau_{\rm stop}=2.30$ に到達して $t_{\rm end}\approx 1.27\,\mathrm{yr}$ で停止し，$M_{\rm loss}\approx 1.56\times 10^{-5}\,M_{\mathrm{M}}$ を得た．
- スイープ全体では，$M_{\rm loss}$ は $3\times 10^{-9}$ から $1.6\times 10^{-5}\,M_{\mathrm{M}}$ の範囲にあり，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ が主要な支配因子である（表\ref{tab:results_sweep_massloss_core}）．
- 質量保存誤差は最大でも $7\times 10^{-15}\%$ 程度であり，本章の $M_{\rm loss}$ は収支誤差により支配されない．

これらの結果を踏まえ，次章では損失の物理的解釈と，長期衛星形成モデルへの接続に対する含意を議論する．
