<!-- TEX_EXCLUDE_START -->
> **文書種別**: 結果（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

本章の主結果を先に述べる．放射圧ブローアウトによる累積損失 $M_{\rm loss}$ は，12 ケースの掃引で $2.0\times10^{-8}$--$1.1\times10^{-4}\,M_{\rm Mars}$ に分布する．また，$M_{\rm loss}$ の 99\% は $t\lesssim1\,\mathrm{yr}$ で確定し，流出は遷移期のごく初期に集中する．

パラメータ依存として，$M_{\rm loss}$ の支配因子は温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ であり，$3000\to4000\,\mathrm{K}$ で $M_{\rm loss}$ は約 3 桁増大し，$\tau_0$ を 2 倍にすると $M_{\rm loss}$ も概ね 2 倍となる．一方，供給混合係数 $\epsilon_{\rm mix}$ は本範囲では $M_{\rm loss}$ をほとんど変えない（5 節）．

序論で述べたように，$\Delta M_{\rm in}$ の系統差は (i) $\tau_{\rm los}$ の評価と (ii) $T_M(t)$ の有効期間に支配され得る．本章ではこれらを代表するパラメータとして $(T_{M,0},\tau_0)$ の感度として結果を整理する．

本章では，手法章で定義した軸対称 1D（リング分割）モデルに基づく数値結果を整理する．主な関心は，遷移期における放射圧による不可逆損失の累積量 $M_{\rm loss}$（序論の $\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）と，それが温度や光学的厚さにどう依存するかである．この $M_{\rm loss}(t_{\rm end})$ は，長期モデルへ渡す内側円盤質量の更新量（式\ref{eq:min0_update}）に直接入る．本章では放射圧による寄与を分離するため追加シンクを無効化し（放射圧ブローアウトのみ；下限評価），$M_{\rm loss}=M_{\rm out,cum}$ として評価する．以降では，全円盤の $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}），および半径依存を含む $\dot{M}_{\rm out}(r,t)$ に焦点を当て，併せて質量保存と停止条件の内訳を検証する．

以下では，まずスイープ計算の条件とデータセットを整理し（1 節），全円盤積分量 $\dot{M}_{\rm out}(t)$ と $M_{\rm loss}(t)$ の代表的な時間発展を示す（2 節）．続いて，半径方向に分解した $\dot{M}_{\rm out}(r,t)$ の構造を可視化し（3 節），質量保存と停止条件の内訳を検証する（4 節）．最後に $M_{\rm loss}$ の主要パラメータ依存性を要約し（5 節），本章の小結を述べる（6 節）．

## 1. 実行条件とデータセット

本章の結果は，温度・初期光学的厚さ・供給混合係数を掃引した 1D スイープ計算（計 12 ケース）から得た時系列出力に基づく．本節では，計算条件と主要な評価指標を整理する．

本章では質量を火星質量 $M_{\rm Mars}$ で無次元化し，$M_{\rm loss}$ を $M_{\rm Mars}$ 単位で示す．放射圧ブローアウトの寄与を分離する目的で追加シンクを無効化しており，本章の $M_{\rm loss}$ は $M_{\rm out,cum}$ に一致する（追加シンクを含めた総損失は，本章の値に追加の損失分が加わる）．
また，$\tau_{\rm los}>\tau_{\rm stop}$ によるセル早期停止は，手法章で述べた照射近似の適用範囲判定であり，物理的にブローアウトが停止することを意味しない．

温度条件（$T_{M,0}$）の違いを直観的に示すため，火星放射冷却に基づいて計算したフォルステライトダスト温度 $T_{\rm dust}(r,t)$ の 2 年間マップを図\ref{fig:results_forsterite_phase_heatmap}に示す（灰色は融点以上の領域）．本章の以降の結果は，この温度ドライバ $T_M(t)$ の系統差が放射圧ブローアウトを通じて $M_{\rm loss}$ をどう変えるかとして整理する．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/thesis/forsterite_phase_heatmap_T0stack_2yr.png}
  \caption{火星放射冷却に基づくフォルステライトダスト温度マップ（2 年間）と融点境界．初期火星表面温度 $T_{M,0}$ を 3000/4000/5000 K で変えた 3 ケースを比較する（灰色は融点以上）．}
  \label{fig:results_forsterite_phase_heatmap}
\end{figure}

### 1.1 パラメータ掃引（温度・供給）

序論では，遷移期の損失評価に対して，(i) 視線方向光学的厚さ $\tau_{\rm los}$ の推定誤差と，(ii) 火星冷却曲線 $T_M(t)$ の形状および有効期間が系統差を与え得ることを指摘した．本章では，これらを代表するパラメータとして初期光学的厚さ $\tau_0$ と初期温度 $T_{M,0}$ を掃引し，$M_{\rm loss}(t_{\rm end})$ の感度として整理する．

温度・初期光学的厚さ・供給混合係数を変えた 12 ケースを計算し，$M_{\rm loss}$ と停止条件の違いを比較する．掃引に用いた主な設定を表\ref{tab:results_sweep_setup}に示す．

ここで，$\tau_0$ は手法章で定義した $\tau_{\rm los}$ の初期規格化に相当し，照射され得る表層面密度のスケールを与える．温度については，本章では温度ドライバ $T_M(t)$ の形状は固定し，初期温度 $T_{M,0}$ を変えることで照射条件の系統差を代表させる．再現実行に必要な設定→物理対応の一覧は付録 B にまとめ，本節では物理量として記述する．

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
    積分終端 & $t_{\rm end}$：$T_M(t)$ が $T_{\rm end}=2000\,\mathrm{K}$ に到達する時刻 \\
    セル早期停止 & $\tau_{\rm los}>\tau_{\rm stop}=\ln 10$（本スイープでは未発火） \\
    補助打ち切り & $t\ge t_{\min}=2\,\mathrm{yr}$ で $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le \dot{M}_{\rm th}=10^{-14}M_{\rm Mars}\,\mathrm{s^{-1}}$ \\
    追加シンク & 本章のスイープでは無効（$M_{\rm loss}=M_{\rm out,cum}$） \\
    \hline
  \end{tabular}
\end{table}

### 1.2 代表ケースと主要な評価指標

時系列の代表例として，$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$ のケース（$\epsilon_{\rm mix}=1.0$，$i_0=0.05$）を用いる．本章で主に参照する量は以下である．

- 視線方向光学的厚さ $\tau_{\rm los}(t)$ と停止条件（$t_{\rm end}$，停止理由）
- 放射圧流出率 $\dot{M}_{\rm out}(t)$ と累積損失 $M_{\rm loss}(t)$（本章では追加シンクが無効のため $M_{\rm loss}=M_{\rm out,cum}$）
- 収支検査：質量保存誤差（相対誤差％）

小括として，本節ではスイープ計算の条件と，本章で参照する指標を整理した．次節では，代表ケースを起点に，$\dot{M}_{\rm out}(t)$ と $M_{\rm loss}(t)$ の典型的な時間発展を示す．
## 2. 主要時系列と累積量

本節では，全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と累積損失 $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}）の代表的な時間発展を示す．序論で定義した不可逆損失 $\Delta M_{\rm in}(t)$（式\ref{eq:delta_min_def}）は，本論文では $M_{\rm loss}(t)$ と同義である．本章のスイープでは追加シンクを無効化しているため，$M_{\rm loss}$ は $\dot{M}_{\rm out}$ の時間積分（区分一定近似）に一致し，数値出力では $M_{\rm out,cum}$ として記録される．

積分終端 $t_{\rm end}$ は $T_M(t_{\rm end})=T_{\rm end}$（$T_{\rm end}=2000\,\mathrm{K}$）によって定義される（表\ref{tab:results_sweep_setup}）．

まず代表ケース（$T_{M,0}=4000\,\mathrm{K}$，$\tau_0=1.0$，$\epsilon_{\rm mix}=1.0$）の時系列を図\ref{fig:results_outflow_tau_cumloss_representative}に示す．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/outflow_tau_cumloss_representative/T4000_eps1p0_tau1p0_i00p05_mu1p0.png}
  \caption{代表ケースの時系列．上段：全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$]（対数軸）．中段：視線方向光学的厚さ $\tau_{\rm los}(t)$（線形軸，破線は停止判定 $\tau_{\rm stop}=\ln 10$）．下段：累積損失 $M_{\rm loss}(t)$ [$M_{\rm Mars}$]（対数軸）．}
  \label{fig:results_outflow_tau_cumloss_representative}
\end{figure}

図\ref{fig:results_outflow_tau_cumloss_representative}より，$\dot{M}_{\rm out}(t)$ は計算開始直後に $\sim10^{-11}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ のピークをとり，$\sim1\,\mathrm{yr}$ で $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 以下へ低下する．このため $M_{\rm loss}(t)$ は $t\simeq0.65\,\mathrm{yr}$ で最終値の 99\% に達し，それ以降の増分は小さい．また，$\tau_{\rm los}(t)$ は本ケースで $|\Delta\tau_{\rm los}|\sim3\times10^{-5}$ とほぼ一定であり，本スイープ全体でも $|\Delta\tau_{\rm los}|<1.4\times10^{-4}$ と小さい．以降では，この挙動がパラメータによりどう変化するかをグリッド図で示す．

なお，代表ケースの積分終端は $t_{\rm end}=6.11\,\mathrm{yr}$（表\ref{tab:results_sweep_massloss_cases}）であるが，$M_{\rm loss}$ の大半が $t\lesssim1\,\mathrm{yr}$ で確定することから，温度ドライバ $T_M(t)$ の系統差が結果へ入るとしても，主に初期の高温期（$t\lesssim1\,\mathrm{yr}$）の取り扱いが支配的になる．

### 2.1 放射圧流出率 $\dot{M}_{\rm out}(t)$

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau0p5.png}
  \includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau1p0.png}
  \caption{全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．縦軸は $\dot{M}_{\rm out}$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] の対数，横軸は時間 $t$ [yr] である．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表し，線が途中で終わるのは停止条件（4 節）による．}
  \label{fig:results_moutdot_grid}
\end{figure}

図\ref{fig:results_moutdot_grid}より，$\dot{M}_{\rm out}(t)$ は計算開始直後に最大となり，多くのケースでは $t\simeq0.05$--$1.3\,\mathrm{yr}$ で $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 以下へ低下する（$T_{M,0}=3000\,\mathrm{K}$ の一部ケースでは開始直後から $10^{-14}$ 以下）．ピーク流出率は $T_{M,0}=3000\,\mathrm{K}$ で $7\times10^{-15}$--$1.4\times10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ であるのに対し，$T_{M,0}=4000$--$5000\,\mathrm{K}$ では $6\times10^{-12}$--$2.4\times10^{-11}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ と 3--4 桁大きい．また，同じ $(T_{M,0},\epsilon_{\rm mix})$ で比較すると $\tau_0=1.0$ は $\tau_0=0.5$ に比べて $\dot{M}_{\rm out}(t)$ の規模が概ね 2 倍となり，累積損失の差（次節）へ反映される．

### 2.2 累積損失 $M_{\rm loss}(t)$

図\ref{fig:results_cumloss_grid}に累積損失 $M_{\rm loss}(t)$ を示す（縦軸は $10^{-5}M_{\rm Mars}$ で規格化）．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau0p5.png}
  \includegraphics[width=\linewidth]{figures/results/cumloss_grid/cumloss_grid_tau1p0.png}
  \caption{累積損失 $M_{\rm loss}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．縦軸は $M_{\rm loss}/(10^{-5}M_{\rm Mars})$ の対数，横軸は時間 $t$ [yr] である．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表し，線が途中で終わるのは停止条件（4 節）による．}
  \label{fig:results_cumloss_grid}
\end{figure}

図\ref{fig:results_cumloss_grid}より，$M_{\rm loss}(t)$ は $t\lesssim1\,\mathrm{yr}$ でほぼ飽和し，最終値は $2.0\times10^{-8}$--$1.1\times10^{-4}\,M_{\rm Mars}$ の範囲に分布する．したがって，$M_{\rm loss}$ の大小は初期の $\dot{M}_{\rm out}$ の規模で概ね決まり，温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ が主要な支配因子となる．本スイープで得られた $M_{\rm loss}$ の範囲とパラメータ依存性は 5 節で定量的に要約する．

小括として，本節では $\dot{M}_{\rm out}(t)$ が遷移期の初期に集中し，$M_{\rm loss}$ が 1 年以内にほぼ確定することを示した．次節では，この流出が半径方向にどのように分布するかを示す．
## 3. 半径依存：半径×時間の流出構造

本節では，半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ の半径×時間マップを示す．横軸は時間 $t$ [yr]，縦軸は半径 $r/R_{\rm Mars}$ である．色は各セルの $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数カラースケールで示し，白はカラースケール下限（$10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$）以下を表す．本モデルは基準ケースとしてセル間輸送を含めないため，ここで見える半径依存は各セルの局所条件の違いとして解釈する．本スイープでは $\tau_{\rm los}$ の時間変化が小さい（2 節）ため，ここでは流出構造の差に焦点を当てて $\dot{M}_{\rm out}(r,t)$ のみを可視化する．比較のため横軸は $t\le 2\,\mathrm{yr}$ の範囲を表示する．

### 3.1 $\tau_0=0.5$ の場合

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}に $\tau_0=0.5$ の半径×時間マップを示す．以降では $\tau_0=1.0$ の場合（図\ref{fig:results_time_radius_moutdot_tau_tau1p0}）と比較し，流出の時間集中と半径方向の縮退を議論する．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_0p5.png}
  \caption{半径×時間の流出構造（$\tau_0=0.5$）．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$]（対数カラースケール）を示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満である．パネルは (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_time_radius_moutdot_tau_tau0p5}
\end{figure}

### 3.2 $\tau_0=1.0$ の場合

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_1p0.png}
  \caption{半径×時間の流出構造（$\tau_0=1.0$）．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$]（対数カラースケール）を示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満である．パネルは (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_time_radius_moutdot_tau_tau1p0}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}より，流出は初期（$t\lesssim 1\,\mathrm{yr}$）に集中し，時間とともに外側半径から流出が弱まることで，流出が生じる領域は内側へ縮退していく．また，同じ温度 $T_{M,0}$ では $\tau_0$ が大きい方が $\dot{M}_{\rm out}(r,t)$ の規模が大きく，累積損失の差（図\ref{fig:results_cumloss_grid}）へ反映される．

小括として，本節では全円盤積分量 $\dot{M}_{\rm out}(t)$ の背後にある半径方向の流出構造を可視化し，流出が初期に外側から先に弱まる様子を示した．次節では，得られた $M_{\rm loss}$ が数値誤差や停止判定に支配されていないことを検証する．
## 4. 検証：質量保存と停止条件

本節では，結果の信頼性を担保するために，（i）質量保存，（ii）停止条件の内訳を確認する．

### 4.1 質量保存（質量収支ログ）

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau0p5.png}
  \includegraphics[width=\linewidth]{figures/results/mass_budget_error/mass_budget_error_grid_tau1p0.png}
  \caption{質量保存誤差 $\epsilon_{\rm mass}(t)$（相対誤差％）の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．縦軸は相対誤差[\%]（線形）であり，表示範囲は $10^{-13}\%$ 程度である．各パネルは $(T_{M,0},\epsilon_{\rm mix})$ の組に対応し，$i_0=0.05$，$\mu=1.0$ は共通である．}
  \label{fig:results_mass_budget_error_grid}
\end{figure}

スイープ 12 ケースでは，質量保存誤差の最大値は $9\times 10^{-14}\%$（$<10^{-13}\%$）であり，許容誤差 $0.5\%$ を十分に下回る．最大値は $T_{M,0}=5000\,\mathrm{K}$ かつ $\tau_0=1.0$ のケースで生じた．したがって，本章で報告する $M_{\rm loss}$ は収支誤差によって支配されていない．

ここでいう質量保存誤差は，手法章で定義した $\epsilon_{\rm mass}$（式\ref{eq:mass_budget_definition}）に対応するものであり，各内部ステップでの収支ずれが $0.5\%$ 以内となるよう時間刻みを制御している．

\begin{table}[t]
  \centering
  \caption{質量保存誤差の要約（スイープ 12 ケース）}
  \label{tab:results_mass_budget_summary}
  \begin{tabular}{lc}
    \hline
    指標 & 値 \\
    \hline
    最大誤差（$T_{M,0}=5000\,\mathrm{K}$，$\tau_0=1.0$） & $<10^{-13}\%$ \\
    中央値（12 ケース） & $\sim 3\times 10^{-15}\%$ \\
    \hline
  \end{tabular}
\end{table}

### 4.2 停止条件の内訳

本章のスイープでは，停止理由は二種類である．すなわち，所定の終了時刻 $t_{\rm end}$ への到達と，全円盤の総損失率 $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}$ が閾値 $\dot{M}_{\rm th}$ を下回ったための打ち切りである．後者は $t\ge t_{\min}$ の範囲で $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le \dot{M}_{\rm th}$ を満たした時点で発火し，本スイープでは $t_{\min}=2\,\mathrm{yr}$ と $\dot{M}_{\rm th}=10^{-14}M_{\rm Mars}\,\mathrm{s^{-1}}$ を用いた（表\ref{tab:results_sweep_setup}）．本章では追加シンクを無効化しているため，この条件は実質的に $\dot{M}_{\rm out}\le \dot{M}_{\rm th}$ に一致する．

なお，手法章で述べた $\tau_{\rm los}>\tau_{\rm stop}$ によるセル早期停止は，照射近似の適用範囲判定であり，本スイープでは発生しなかった．

本スイープでは後者はいずれも $t\simeq 2\,\mathrm{yr}$ で停止したが，$M_{\rm loss}(t)$ は初期に飽和する（図\ref{fig:results_cumloss_grid}）．全ケースで $M_{\rm loss}$ の 99\% は $t\simeq0.19$--$0.84\,\mathrm{yr}$ に達するため，$t\simeq2\,\mathrm{yr}$ 以降の区間を延長しても $M_{\rm loss}$ の増分は小さい．したがって，この打ち切りは $M_{\rm loss}$ の最終値に対する影響が小さい（5節）．

\begin{table}[t]
  \centering
  \caption{停止条件の内訳（スイープ 12 ケース）}
  \label{tab:results_stop_reason_counts}
  \begin{tabular}{lc}
    \hline
    停止理由 & ケース数 \\
    \hline
    終了時刻到達（$t=t_{\rm end}$） & 6 \\
    損失率閾値以下（$t\ge 2\,\mathrm{yr}$ かつ $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le 10^{-14}M_{\rm Mars}\,\mathrm{s^{-1}}$） & 6 \\
    \hline
  \end{tabular}
\end{table}

小括として，本節では質量収支誤差が許容差を大きく下回り，停止判定も $M_{\rm loss}$ の最終値を規定しないことを確認した．次節では，$M_{\rm loss}$ の温度・$\tau_0$・$\epsilon_{\rm mix}$ に対する感度を要約する．
## 5. 感度解析

本節では，表\ref{tab:results_sweep_setup}の 12 ケースを用いて，$M_{\rm loss}$ が主要パラメータにどう依存するかを要約する．

### 5.1 累積損失 $M_{\rm loss}$ の温度・$\tau_0$ 依存性

表\ref{tab:results_sweep_massloss_cases}に，全 12 ケースの $M_{\rm loss}$ を示す．本スイープでは，$T_{M,0}$ の上昇に伴って $M_{\rm loss}$ が増大し，$3000\to4000\,\mathrm{K}$ で約 $10^3$ 倍，$4000\to5000\,\mathrm{K}$ で約 2.5 倍となる．また，同一の $T_{M,0}$ で比較すると，$\tau_0=1.0$ の $M_{\rm loss}$ は $\tau_0=0.5$ の概ね 2 倍となる．

温度依存性は，放射圧比 $\beta(s)$ とブローアウト粒径 $s_{\rm blow}$ を通じて一次シンク（ブローアウト）を規定することに由来する（手法章 2.1節，式\ref{eq:surface_outflux}）．また，$\tau_0$ は初期の $\tau_{\rm los}$ 規格化（式\ref{eq:tau_los_definition}）を通じて表層面密度のスケールを与えるため，$\tau_0$ を 2 倍にすると $M_{\rm loss}$ も概ね 2 倍となる．

\begin{table}[t]
  \centering
  \caption{スイープ 12 ケースにおける累積損失 $M_{\rm loss}$ と停止条件}
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

### 5.2 $\epsilon_{\rm mix}$ の影響

表\ref{tab:results_sweep_massloss_cases}より，同一の $(T_{M,0},\tau_0)$ に対して $\epsilon_{\rm mix}=1.0$ と $1.5$ を比較すると，停止時刻は異なる一方で $M_{\rm loss}$ は一致する．これは，本研究の基準供給率の定義（式\ref{eq:R_base_definition}）により，表層への注入率 $\dot{\Sigma}_{\rm in}$ が $\epsilon_{\rm mix}$ に依存しないよう規格化されていることと整合する．すなわち，本章で掃引している $\epsilon_{\rm mix}$ は，供給量の大小ではなく「混合係数をどう定義するか」という感度であり，放射圧損失の積算量 $M_{\rm loss}$ は主に $T_{M,0}$ と $\tau_0$ により決まる．また，$M_{\rm loss}$ は $t\lesssim1\,\mathrm{yr}$ でほぼ確定する（2 節）ため，$t\simeq2\,\mathrm{yr}$ での補助打ち切りの有無は最終値にほとんど影響しない．

小括として，本節では $M_{\rm loss}$ の主要依存性が $T_{M,0}$ と $\tau_0$ によって説明でき，$\epsilon_{\rm mix}$ は供給率の規格化の取り方に関する感度として現れることを示した．次節で本章の結論をまとめる．
## 6. 小結

本章では，軸対称 1D モデルの 12 ケース掃引により，放射圧ブローアウト（追加シンク無効）に伴う累積損失 $M_{\rm loss}$ の大きさと依存性を定量化した．$\dot{M}_{\rm out}(t)$ は計算開始直後に最大となり，その後急速に減衰するため，$M_{\rm loss}(t)$ は 1 年以内にほぼ確定する（全ケースで 99\% 到達時刻は $t\simeq0.19$--$0.84\,\mathrm{yr}$；図\ref{fig:results_moutdot_grid}，図\ref{fig:results_cumloss_grid}）．

最終的な $M_{\rm loss}$ は $2.0\times 10^{-8}$--$1.09\times 10^{-4}\,M_{\rm Mars}$ に分布し，温度 $T_{M,0}$ が最も強い支配因子である（$3000\to4000\,\mathrm{K}$ で約 $10^3$ 倍；表\ref{tab:results_sweep_massloss_cases}）．初期光学的厚さ $\tau_0$ はほぼ線形に効いて $M_{\rm loss}$ を概ね 2 倍変える．一方，供給混合係数 $\epsilon_{\rm mix}$ は供給率の規格化の取り方に関する感度であり（手法章 2.3節），停止時刻の違いを除けば $M_{\rm loss}$ は一致する（表\ref{tab:results_sweep_massloss_cases}）．

半径方向には，流出は初期に外側から先に終息し，半径×時間マップでその構造が確認できる（図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}）．また，本スイープでは $\tau_{\rm los}>\tau_{\rm stop}$ の早期停止は発生せず，照射近似が成立する範囲で評価できている．質量保存誤差は最大でも $10^{-13}\%$ 未満であり，収支ずれが結果を支配しない（表\ref{tab:results_mass_budget_summary}）．

以上の $M_{\rm loss}(t_{\rm end})$（$\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）は，遷移期の放射圧損失（下限評価）として，長期モデルへ渡す内側円盤質量の更新（式\ref{eq:min0_update}）に直接用いられる．序論で指摘した二つの系統差要因は，結果として $T_{M,0}$（温度条件）と $\tau_0$（照射され得る表層量）の感度として現れ，本章の範囲では温度依存性が卓越する．

これらの結果を踏まえ，次章では損失の物理的解釈と長期衛星形成モデルへの接続に対する含意を議論する．
