<!-- TEX_EXCLUDE_START -->
出力結果は out/temp_supply_sweep_1d/20260120-131832__b6a734509__seed955316828/ 内に保存されている．
<!-- TEX_EXCLUDE_END -->

## 1. 実行条件とデータセット

1D モデルに対して初期火星表面温度 $T_{M,0}$，視線方向光学的厚さの初期規格化 $\tau_0$，および表層への質量再供給を規定する供給混合係数 $\epsilon_{\rm mix}$ を掃引した計 12 ケースのスイープ計算を行った．これらの時系列出力に基づき，放射圧による表層質量損失の時間発展を評価する．
また各温度条件において，火星放射冷却に基づいて計算したフォルステライトダスト温度 $T_{\rm dust}(r,t)$ の 2 年間マップを図\ref{fig:results_forsterite_phase_heatmap}に示す．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/thesis/forsterite_phase_heatmap_T0stack_2yr.png}
  \caption{火星放射冷却に基づくフォルステライトダスト温度 $T_{\rm dust}(r,t)$ の 2 年間マップと融解温度境界．初期火星表面温度 $T_{M,0}=3000/4000/5000\,\mathrm{K}$ の 3 ケースを比較した（灰色は融解温度以上）．}
  \label{fig:results_forsterite_phase_heatmap}
\end{figure}

$T_{M,0}\in\{3000,\allowbreak 4000,\allowbreak 5000\}\,\mathrm{K}$，$\tau_0\in\{0.5,1.0\}$，および $\epsilon_{\rm mix}\in\{1.0,1.5\}$ を組み合わせた計 $3\times2\times2=12$ ケースを計算し，$M_{\rm loss}(t)$ の終端値と停止条件の挙動を比較した．掃引に用いた主要設定を表\ref{tab:results_sweep_setup}に示す．なお，終端時刻を $T_M(t)=T_{\rm end}$ に到達する時刻として定義するため，積分時間はケースごとに一致しない．
ここで，$\tau_0$ は式\ref{eq:tau_los_definition}で定義した $\tau_{\rm los}$ の初期値を与える無次元パラメータであり，照射を受け得る表層面密度の初期スケールを規格化する．また，温度ドライバ $T_M(t)$ の時間変化は固定し，$T_{M,0}$ のみを変えることで巨大衝突直後の火星放射条件の不確実性を表す．先行研究では，巨大衝突後には火星表面温度が局所的に $5000$--$6000\,\mathrm{K}$ 程度まで上昇し，$3000$--$4000\,\mathrm{K}$ 程度の領域も広がる\citep{Hyodo2018_ApJ860_150}．本章ではこれを踏まえ，$T_{M,0}=3000$--$5000\,\mathrm{K}$ を代表範囲として採用する．

\begin{table}[t]
\centering
\small
\setlength{\tabcolsep}{3pt}
\caption{本章で用いるパラメータ掃引計算の主要条件}
\label{tab:results_sweep_setup}
\begin{tabular}{@{}L{0.14\linewidth} L{0.10\linewidth} L{0.18\linewidth} L{0.50\linewidth}@{}}
\hline
区分 & 記号 & 設定値 & 備考 \\
\hline
モデル次元 & --- & 1D & リング分割による半径一次元モデル \\
空間分割 & $N_r$ & $32$ & $r/R_{\rm Mars}\in[1.0,2.7]$ \\
温度条件 & $T_{M,0}$ & $\{3000,\allowbreak 4000,\allowbreak 5000\}\,\mathrm{K}$ & $T_M(t)$ の形状は固定し，初期温度のみを変更 \\
初期光学的厚さ & $\tau_0$ & $\{0.5,1.0\}$ & $\tau_{\rm los}(t=0)$（式\ref{eq:tau_los_definition}） \\
表層供給 & $\epsilon_{\rm mix}$ & $\{1.0,1.5\}$ & 手法章で定義した表層供給モデルの無次元係数 \\
速度分散初期値 & $i_0$ & $0.05$ & 全ケース共通 \\
積分終端 & $t_{\rm end}$ & $T_M(t)=T_{\rm end}$ & $T_{\rm end}=2000,\mathrm{K}$ に到達する時刻 \\
セル早期停止 & $\tau_{\rm stop}$ & $\ln 10$ & $\tau_{\rm los}>\tau_{\rm stop}$ で照射近似が破綻するとみなす（本スイープでは条件を満たさなかった） \\
補助停止（最短時刻） & $t_{\min}$ & $2\,\mathrm{yr}$ & 補助停止判定を開始する最短時刻 \\
補助停止（閾値） & $\dot{M}_{\rm th}$ & $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ & $t\ge t_{\min}$ かつ $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le\dot{M}_{\rm th}$ で打ち切り（本章では $\dot{M}_{\rm sinks}=0$） \\
追加シンク & --- & 無効 & 本章では $M_{\rm loss}=M_{\rm out,cum}$ \\
\hline
\end{tabular}
\end{table}
## 2. 放射圧流出率 $\dot{M}_{\rm out}(t)$

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau0p5.png}
\includegraphics[width=\linewidth]{figures/results/moutdot_grid/moutdot_grid_tau1p0.png}
\caption{全円盤の放射圧流出率 $\dot{M}_{\rm out}(t)$ の時系列（上：$\tau_0=0.5$，下：$\tau_0=1.0$）．縦軸は $\dot{M}_{\rm out}$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] の対数，横軸は時間 $t$ [yr] である．各曲線は温度 $T_{M,0}$ と供給混合係数 $\epsilon_{\rm mix}$ の組を表し，線が途中で終わるのは数値停止条件（4.2 節）による．}
\label{fig:results_moutdot_grid}
\end{figure}

図\ref{fig:results_moutdot_grid}に示すように，$\dot{M}_{\rm out}(t)$ は計算開始直後に最大となり，その後に急速に減衰する．多くのケースでは $t\simeq0.05$--$1.3\,\mathrm{yr}$ で $\dot{M}_{\rm out}<10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ となる．また，$T_{M,0}=3000\,\mathrm{K}$ の一部ケースでは，開始直後から $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ を下回る．

ピーク流出率は $T_{M,0}=3000\,\mathrm{K}$ で $7\times10^{-15}$--$1.4\times10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ であるのに対し，$T_{M,0}=4000$--$5000\,\mathrm{K}$ では $6\times10^{-12}$--$2.4\times10^{-11}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ と3桁程度大きい．また，同一の $(T_{M,0},\epsilon_{\rm mix})$ に対して比較すると，$\tau_0=1.0$ は $\tau_0=0.5$ に比べて $\dot{M}_{\rm out}(t)$ の規模が概ね2倍となり，累積損失の差（5 節）としても現れる．
したがって，$\dot{M}_{\rm out}(t)$ が初期過渡期に集中し，その結果として累積損失 $M_{\rm loss}$ が短時間でほぼ確定していることがわかる．
<!-- TEX_EXCLUDE_START -->
出力結果は out/temp_supply_sweep_1d/20260120-131832__b6a734509__seed955316828/ 内に保存されている．
<!-- TEX_EXCLUDE_END -->

## 3. 半径依存：半径×時間の流出構造

半径セルごとの放射圧起因の質量流出率 $\dot{M}_{\rm out}(r,t)$ を半径–時間マップとして示し，全円盤で定義した流出率 $\dot{M}_{\rm out}(t)$ が初期に急減する要因を，寄与する半径帯の時間発展として可視化する（図\ref{fig:results_time_radius_moutdot_tau_tau0p5}，図\ref{fig:results_time_radius_moutdot_tau_tau1p0}）．横軸は時間 $t\,[\mathrm{yr}]$，縦軸は半径 $r/R_{\rm Mars}$ である．色は各セルの $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数スケールで表し，白はカラースケールの下限値 $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満を示す．基準ケースでは半径方向のセル間輸送を考慮しないため，図に現れる半径依存性は，各セルの局所条件の違いによるものであると考えることができる．表示範囲は $t\le 2\,\mathrm{yr}$ である．

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}に，$\tau_0=0.5$ における放射圧流出率 $\dot{M}_{\rm out}(r,t)$ の半径–時間分布（$t\le 2\,\mathrm{yr}$）を示す．
図\ref{fig:results_time_radius_moutdot_tau_tau0p5}では，流出が卓越する時間帯が初期に偏り，時間とともに流出が生じる半径帯が内側へ縮小する傾向が見て取れる

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_0p5.png}
\caption{半径–時間の流出構造（$\tau_0=0.5$）．横軸は時間 $t$ [$\mathrm{yr}$]（表示範囲 $t\le 2\,\mathrm{yr}$），縦軸は半径 $r/R_{\rm Mars}$ である．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数カラースケールで示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満を表す．パネル (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応する．$i_0=0.05$，$\mu=1.0$ は共通である．}
\label{fig:results_time_radius_moutdot_tau_tau0p5}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau1p0}に，$\tau_0=1.0$ の半径–時間分布を示す．図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}によると，質量流出が初期に集中し，流出の寄与が時間とともに内側へ限られていくことがわかる．

\begin{figure}[t]
\centering
\includegraphics[width=\linewidth]{figures/results/result-radius-time-flux/time_radius_M_out_dot_tau_grid_1p0.png}
\caption{半径–時間の流出構造（$\tau_0=1.0$）．横軸は時間 $t$ [$\mathrm{yr}$]（表示範囲 $t\le 2\,\mathrm{yr}$），縦軸は半径 $r/R_{\rm Mars}$ である．色は半径セルごとの放射圧流出率 $\dot{M}_{\rm out}(r,t)$ [$M_{\rm Mars}\,\mathrm{s^{-1}}$] を対数カラースケールで示し，白は $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 未満を表す．パネル (a) $(T_{M,0},\epsilon_{\rm mix})=(3000\,\mathrm{K},1.0)$，(b) $(3000\,\mathrm{K},1.5)$，(c) $(4000\,\mathrm{K},1.0)$，(d) $(4000\,\mathrm{K},1.5)$，(e) $(5000\,\mathrm{K},1.0)$，(f) $(5000\,\mathrm{K},1.5)$ に対応する．$i_0=0.05$，$\mu=1.0$ は共通である．}
\label{fig:results_time_radius_moutdot_tau_tau1p0}
\end{figure}

図\ref{fig:results_time_radius_moutdot_tau_tau0p5}--\ref{fig:results_time_radius_moutdot_tau_tau1p0}より，$\dot{M}_{\rm out}(r,t)$ は初期（$t\lesssim 1\,\mathrm{yr}$）に大きく，その後は急速に弱まることが分かる．半径方向の時間発展に着目すると，外側半径側から順に $\dot{M}_{\rm out}(r,t)$ が低下し，流出に寄与する半径帯が時間とともに内側へ縮小していく．以降では可視化の閾値に合わせ，$\dot{M}_{\rm out}(r,t)\ge 10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ を満たす領域を流出寄与領域と呼ぶ．
この流出寄与領域が外側から失われることで，全円盤積分量 $\dot{M}_{\rm out}(t)$ は短時間で急減し（図\ref{fig:results_moutdot_grid}），累積損失量 $M_{\rm loss}$ が $t\lesssim 1\,\mathrm{yr}$ でほぼ確定するという振る舞いが，半径方向の寄与として理解できる．また，同一の $T_{M,0}$ の下では，$\tau_0$ が大きいほど $\dot{M}_{\rm out}(r,t)$ の規模が全体に大きく，その差は累積損失量の差（図\ref{fig:results_cumloss_grid}）として現れる．
<!-- TEX_EXCLUDE_START -->
出力結果は out/temp_supply_sweep_1d/20260120-131832__b6a734509__seed955316828/ 内に保存されている．
<!-- TEX_EXCLUDE_END -->

## 4. 検証：質量保存と停止条件

### 4.1 質量保存

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

12ケースのシミュレーションにおいて，計算の停止理由は2種類である．一つは所定の終了時刻 $t_{\rm end}$ への到達であり，もう一つは円盤全体の総損失率 $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}$ が閾値 $\dot{M}_{\rm th}$ を下回ったための打ち切りである．
後者は，$t\ge t_{\min}$ の範囲で $\dot{M}_{\rm out}+\dot{M}_{\rm sinks}\le \dot{M}_{\rm th}$ を満たした時点で発火する．本スイープでは $t_{\min}=2\,\mathrm{yr}$，$\dot{M}_{\rm th}=10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ を採用した（表\ref{tab:results_sweep_setup}）．さらに本章では追加シンクを無効化しているため $\dot{M}_{\rm sinks}=0$ であり，停止条件は実質的に $\dot{M}_{\rm out}\le \dot{M}_{\rm th}$ に一致する．
また，手法章で述べたセル早期停止（$\tau_{\rm los}>\tau_{\rm stop}$）は，照射近似の適用範囲を逸脱したセルを除外するための判定である．本シミュレーションでは当該条件は一度も満たされず，セル早期停止は発生しなかった．
損失率閾値による停止は6ケースで生じ，いずれも $t\simeq2,\mathrm{yr}$（$t_{\min}$ 到達直後）で停止条件を満たした（表\ref{tab:results_stop_reason_counts}）．一方，累積損失質量 $M_{\rm loss}(t)$ は初期に急増した後，早期に飽和する（本章第5節；図\ref{fig:results_cumloss_grid}）．全ケースで $M_{\rm loss}$ の99%は $t\simeq0.19$--$0.84,\mathrm{yr}$ に到達しており，本章で採用した停止判定は $M_{\rm loss}$ の最終値を大きく左右しない．
また，停止時刻以降に残り得る追加損失は $\Delta M_{\rm loss}\le \dot{M}_{\rm th}\Delta t$ と上から抑えられる．例えば停止後に $1\,\mathrm{yr}$ 計算を延長しても，$\Delta M_{\rm loss}\le \dot{M}_{\rm th}\times 1\,\mathrm{yr}\simeq 3.2\times 10^{-7}M_{\rm Mars}$ にとどまる．したがって，以降で議論する $M_{\rm loss}$ のケース間比較は，停止判定の違いによって支配されない．

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
\small
\setlength{\tabcolsep}{3pt}
\caption{スイープ12ケースにおける累積損失 $M_{\rm loss}(t_{\rm end})$ と停止条件}
\label{tab:results_sweep_massloss_cases}
\begin{tabular}{@{}L{0.11\linewidth} L{0.10\linewidth} L{0.12\linewidth} L{0.20\linewidth} L{0.14\linewidth} L{0.22\linewidth}@{}}
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
