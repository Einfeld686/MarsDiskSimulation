<!-- TEX_EXCLUDE_START -->
> **文書種別**: 結果（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

# 結果

本章では，手法章で定義した軸対称 1D（リング分割）モデルに基づく数値結果を整理する．主な関心は，遷移期における放射圧による不可逆損失の累積量 $M_{\rm loss}$（序論の $\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）と，それが温度や光学的厚さにどう依存するかである．この $M_{\rm loss}(t_{\rm end})$ は，長期モデルへ渡す内側円盤質量の更新量（式\ref{eq:min0_update}）に直接入る．本章では，全円盤の $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}），および半径依存を含む $\dot{M}_{\rm out}(r,t)$ と $\tau_{\rm los}(r,t)$（式\ref{eq:tau_los_definition}）に焦点を当て，併せて質量保存と停止条件の内訳を検証する．

## 構成

1. 実行条件とデータセット
2. 全円盤の流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$
3. 半径依存：半径×時間の流出構造
4. 検証：質量保存と停止条件
5. 感度解析（温度・$\tau_0$・$\epsilon_{\rm mix}$）
6. 小結

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
## 2. 主要時系列と累積量

本節では，全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と累積損失 $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}）の代表的な時間発展を示す．序論で定義した不可逆損失 $\Delta M_{\rm in}(t)$（式\ref{eq:delta_min_def}）は，本論文では $M_{\rm loss}(t)$ と同義である．本章のスイープでは追加シンクを無効化しているため，$M_{\rm loss}$ は $\dot{M}_{\rm out}$ の時間積分（区分一定近似）に一致し，数値出力では $M_{\rm out,cum}$ として記録される．

ここで温度ドライバとは，火星冷却曲線として $T_M(t)$ を与える外部入力であり，積分終端 $t_{\rm end}$ は $T_M(t_{\rm end})=T_{\rm end}$（$T_{\rm end}=2000\,\mathrm{K}$）によって定義される（表\ref{tab:results_sweep_setup}）．また，追加シンクとは放射圧流出以外の一次損失（昇華など）を表し，本章のスイープでは無効化している．

また，$\tau_{\rm los}$ の時間変化は小さいため，半径依存を含む形で 3 節にまとめて示す．

### 2.1 放射圧流出率 $\dot{M}_{\rm out}(t)$

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau0p5.png}
  % \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau1p0.png}
  \caption{全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表す．}
  \label{fig:results_moutdot_grid}
\end{figure}

図\ref{fig:results_moutdot_grid}より，$\dot{M}_{\rm out}(t)$ は初期に大きく，短時間で急減して準定常値（ほぼゼロ）へ向かう．温度 $T_{M,0}$ に対する依存性が顕著であり，$T_{M,0}=3000\,\mathrm{K}$ では流出が小さい一方，$T_{M,0}\ge 4000\,\mathrm{K}$ では $\dot{M}_{\rm out}$ のピークが桁違いに大きい．また，同じ $(T_{M,0},\epsilon_{\rm mix})$ で比較すると $\tau_0=1.0$ は $\tau_0=0.5$ に比べて流出率が概ね大きく，累積損失の差（次節）へ反映される．

### 2.2 累積損失 $M_{\rm loss}(t)$

図\ref{fig:results_cumloss_grid}に累積損失 $M_{\rm loss}(t)$ を示す（縦軸は $10^{-5}M_{\rm Mars}$ で規格化）．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau0p5.png}
  % \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau1p0.png}
  \caption{累積損失 $M_{\rm loss}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．曲線の割り当ては図\ref{fig:results_moutdot_grid}と同一である．}
  \label{fig:results_cumloss_grid}
\end{figure}

図\ref{fig:results_cumloss_grid}より，$M_{\rm loss}(t)$ は初期に急増し，その後はほぼ一定値へ飽和する．したがって，$M_{\rm loss}$ の大小は初期の $\dot{M}_{\rm out}$ の規模で概ね決まり，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ が支配因子となる．本スイープで得られた $M_{\rm loss}$ の範囲とパラメータ依存性は 5 節で定量的に要約する．
## 3. 半径依存：半径×時間の流出構造

本節では，半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ の半径×時間マップを示す．図の色は各セルの $\dot{M}_{\rm out}(r,t)$ を表し，等高線として視線方向光学的厚さ $\tau_{\rm los}(r,t)$（式\ref{eq:tau_los_definition}）を重ねる．比較のため横軸は $t\le 2\,\mathrm{yr}$ の範囲を表示する（以降は流出率がほぼゼロとなる）．

### 3.1 $\tau_0=0.5$ の場合

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_0p5.png}
  \caption{半径×時間の流出構造（$\tau_0=0.5$）．色は半径セルごとの $\dot{M}_{\rm out}(r,t)$，等高線は $\tau_{\rm los}(r,t)$ を示す．各パネルは $(T_{M,0},\epsilon_{\rm mix})$ の組に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_time_radius_moutdot_tau_tau0p5}
\end{figure}

### 3.2 $\tau_0=1.0$ の場合

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_1p0.png}
  \caption{半径×時間の流出構造（$\tau_0=1.0$）．表記は図\ref{fig:results_time_radius_moutdot_tau_tau0p5}と同一である．}
  \label{fig:results_time_radius_moutdot_tau_tau1p0}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}より，流出は初期（$t\lesssim 1\,\mathrm{yr}$）に集中し，時間とともに外側半径から流出が急速に弱まる．また，同じ温度 $T_{M,0}$ では $\tau_0$ が大きい方が $\dot{M}_{\rm out}(r,t)$ の規模が大きく，累積損失の差（図\ref{fig:results_cumloss_grid}）へ反映される．
## 4. 検証：質量保存と停止条件

本節では，結果の信頼性を担保するために，（i）質量保存，（ii）停止条件の内訳を確認する．

### 4.1 質量保存（質量収支ログ）

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau0p5.png}
  % \includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau1p0.png}
  \caption{質量保存誤差（相対誤差％）の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．各パネルは $(T_{M,0},\epsilon_{\rm mix})$ の組に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_mass_budget_error_grid}
\end{figure}

スイープ 12 ケースでは，質量保存誤差の最大値は $8.72\times 10^{-14}\%$ 程度であり，許容誤差 $0.5\%$ を十分に下回る．したがって，本章で報告する $M_{\rm loss}$ は収支誤差によって支配されていない．

ここでいう質量保存誤差は，手法章で定義した $\epsilon_{\rm mass}$（式\ref{eq:mass_budget_definition}）に対応するものであり，各内部ステップでの収支ずれが $0.5\%$ 以内となるよう時間刻みを制御している．

\begin{table}[t]
  \centering
  \caption{質量保存誤差の要約（スイープ 12 ケース）}
  \label{tab:results_mass_budget_summary}
  \begin{tabular}{lc}
    \hline
    指標 & 値 \\
    \hline
    最大誤差（12 ケース中） & $8.72\times 10^{-14}\%$ \\
    \hline
  \end{tabular}
\end{table}

### 4.2 停止条件の内訳

本章のスイープでは，停止理由は二種類である．すなわち，所定の終了時刻 $t_{\rm end}$ への到達（\texttt{t\_end\_reached}）と，全円盤の総損失率 $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}$ が閾値 $\dot{M}_{\rm th}$ を下回ったための打ち切り（\texttt{loss\_rate\_below\_threshold}）である．後者は $t\ge t_{\min}$ の範囲で $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le \dot{M}_{\rm th}$ を満たした時点で発火し，本スイープでは $t_{\min}=2\,\mathrm{yr}$ と $\dot{M}_{\rm th}=10^{-14}M_{\rm Mars}\,\mathrm{s^{-1}}$ を用いた（表\ref{tab:results_sweep_setup}）．

なお，手法章で述べた $\tau_{\rm los}>\tau_{\rm stop}$ によるセル早期停止は，本スイープでは発生しなかった．

本スイープでは後者はいずれも $t\simeq 2\,\mathrm{yr}$ で停止したが，図\ref{fig:results_cumloss_grid}に示したとおり $M_{\rm loss}(t)$ は初期に飽和する．また，$M_{\rm loss}$ は式\ref{eq:mass_loss_update}で $\dot{M}_{\rm out}$ を積分して更新するため，$\dot{M}_{\rm out}\approx 0$ の区間を延長しても $M_{\rm loss}$ の増分は無視できる．したがって，この打ち切りは $M_{\rm loss}$ の最終値に対する影響が小さい（5節）．

\begin{table}[t]
  \centering
  \caption{停止条件の内訳（スイープ 12 ケース）}
  \label{tab:results_stop_reason_counts}
  \begin{tabular}{lc}
    \hline
    停止理由 & ケース数 \\
    \hline
    \texttt{t\_end\_reached}（終了時刻到達） & 6 \\
    \texttt{loss\_rate\_below\_threshold}（流出率閾値以下） & 6 \\
    \hline
  \end{tabular}
\end{table}
## 5. 感度解析

本節では，表\ref{tab:results_sweep_setup}の 12 ケースを用いて，$M_{\rm loss}$ が主要パラメータにどう依存するかを要約する．

### 5.1 累積損失 $M_{\rm loss}$ の温度・$\tau_0$ 依存性

表\ref{tab:results_sweep_massloss_cases}に，全 12 ケースの $M_{\rm loss}$ を示す．本スイープでは，$T_{M,0}$ の上昇に伴って $M_{\rm loss}$ が急増し，温度依存性が卓越する．また，同一の $T_{M,0}$ で比較すると，$\tau_0=1.0$ の $M_{\rm loss}$ は $\tau_0=0.5$ の概ね 2 倍となる．

温度依存性は，放射圧比 $\beta(s)$ とブローアウト粒径 $s_{\rm blow}$ を通じて一次シンク（ブローアウト）を規定することに由来する（手法章 2.1節，式\ref{eq:surface_outflux}）．また，$\tau_0$ は初期の $\tau_{\rm los}$ 規格化（式\ref{eq:tau_los_definition}）を通じて表層面密度のスケールを与えるため，$\tau_0$ を 2 倍にすると $M_{\rm loss}$ も概ね 2 倍となる．

\begin{table}[t]
  \centering
  \caption{スイープ 12 ケースにおける累積損失 $M_{\rm loss}$ と停止条件}
  \label{tab:results_sweep_massloss_cases}
  \begin{tabular}{cccccc}
    \hline
    $T_{M,0}$ [K] & $\tau_0$ & $\epsilon_{\rm mix}$ & 停止理由 & $t_{\rm end}$ [yr] & $M_{\rm loss}$ [$M_{\rm Mars}$] \\
    \hline
    3000 & 0.5 & 1.0 & \texttt{t\_end\_reached} & 4.92 & $2.04\times 10^{-8}$ \\
    3000 & 0.5 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $2.04\times 10^{-8}$ \\
    3000 & 1.0 & 1.0 & \texttt{t\_end\_reached} & 4.92 & $4.09\times 10^{-8}$ \\
    3000 & 1.0 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $4.09\times 10^{-8}$ \\
    4000 & 0.5 & 1.0 & \texttt{t\_end\_reached} & 6.11 & $2.20\times 10^{-5}$ \\
    4000 & 0.5 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $2.20\times 10^{-5}$ \\
    4000 & 1.0 & 1.0 & \texttt{t\_end\_reached} & 6.11 & $4.41\times 10^{-5}$ \\
    4000 & 1.0 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $4.41\times 10^{-5}$ \\
    5000 & 0.5 & 1.0 & \texttt{t\_end\_reached} & 6.54 & $5.44\times 10^{-5}$ \\
    5000 & 0.5 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $5.44\times 10^{-5}$ \\
    5000 & 1.0 & 1.0 & \texttt{t\_end\_reached} & 6.54 & $1.09\times 10^{-4}$ \\
    5000 & 1.0 & 1.5 & \texttt{loss\_rate\_below\_threshold} & 2.00 & $1.09\times 10^{-4}$ \\
    \hline
  \end{tabular}
\end{table}

### 5.2 $\epsilon_{\rm mix}$ の影響

表\ref{tab:results_sweep_massloss_cases}より，同一の $(T_{M,0},\tau_0)$ に対して $\epsilon_{\rm mix}=1.0$ と $1.5$ を比較すると，停止時刻は異なる一方で $M_{\rm loss}$ は一致する．供給モデルでは $\epsilon_{\rm mix}$ が供給率のスケールに入るが（手法章 2.3節，式\ref{eq:R_base_definition}），本スイープの範囲では $M_{\rm loss}$ は主に $T_{M,0}$ と $\tau_0$ によって支配される．したがって，$\epsilon_{\rm mix}$ は停止条件（\texttt{loss\_rate\_below\_threshold} の発生）を通じて終了時刻に影響するが，累積損失の値自体にはほとんど影響しない．
## 6. 小結

本章では，軸対称 1D モデルを用いたスイープ計算により，放射圧流出に伴う累積損失 $M_{\rm loss}$ の大きさと依存性を示した．得られた主要結果を以下に要約する．

- 全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ は初期に大きく，短時間で急減して準定常値（ほぼゼロ）へ向かう（図\ref{fig:results_moutdot_grid}）．
- 累積損失 $M_{\rm loss}(t)$ は初期に急増し，その後はほぼ一定値へ飽和する（図\ref{fig:results_cumloss_grid}）．
- 半径依存を含む $\dot{M}_{\rm out}(r,t)$ は初期に集中し，時間とともに外側半径から流出が急速に弱まる（図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}）．
- スイープ全体では，$M_{\rm loss}$ は $2.0\times 10^{-8}$ から $1.09\times 10^{-4}\,M_{\rm Mars}$ の範囲にあり，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ が主要な支配因子である（表\ref{tab:results_sweep_massloss_cases}）．
- 基準の内側円盤質量 $M_{\rm in}(t_0)=3\times10^{-5}M_{\rm Mars}$（表\ref{tab:method-param}）で規格化すると，$M_{\rm loss}(t_{\rm end})/M_{\rm in}(t_0)=6.8\times10^{-4}$--$3.6$（$0.07\%$--$360\%$）に相当する．
- 質量保存誤差は最大でも $8.72\times 10^{-14}\%$ 程度であり，本章の $M_{\rm loss}$ は収支誤差により支配されない（表\ref{tab:results_mass_budget_summary}）．
- 以上で得た $M_{\rm loss}(t_{\rm end})$（$\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）は，長期モデルへ渡す内側円盤質量 $M_{\rm in,0}$ の更新（式\ref{eq:min0_update}）に直接用いられる．

これらの結果を踏まえ，次章では損失の物理的解釈と長期衛星形成モデルへの接続に対する含意を議論する．
