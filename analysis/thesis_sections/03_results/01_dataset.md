<!-- TEX_EXCLUDE_START -->
出力結果は out/temp_supply_sweep_1d/20260120-131832__b6a734509__seed955316828/ 内に保存されている．
<!-- TEX_EXCLUDE_END -->

## 1. 実行条件とデータセット

1D モデルに対して温度条件（初期火星表面温度 $T_{M,0}$），視線方向光学的厚さの初期規格化 $\tau_0$，および表層への質量再供給を規定する供給混合係数 $\epsilon_{\rm mix}$ を掃引した計 12 ケースのスイープ計算を行った．これらの時系列出力に基づき，放射圧による表層質量損失の時間発展を評価する．

また各温度条件において，火星放射冷却に基づいて計算したフォルステライトダスト温度 $T_{\rm dust}(r,t)$ の 2 年間マップを図\ref{fig:results_forsterite_phase_heatmap}に示す（灰色は手法章で定義した融解温度以上の領域）．

\begin{figure}[t]
  \centering
  \includegraphics[width=\linewidth]{figures/thesis/forsterite_phase_heatmap_T0stack_2yr.png}
  \caption{火星放射冷却に基づくフォルステライトダスト温度 $T_{\rm dust}(r,t)$ の 2 年間マップと融解温度境界．初期火星表面温度 $T_{M,0}=3000/4000/5000\,\mathrm{K}$ の 3 ケースを比較した（灰色は融解温度以上）．}
  \label{fig:results_forsterite_phase_heatmap}
\end{figure}

$T_{M,0}\in\{3000,4000,5000\}\,\mathrm{K}$，$\tau_0\in\{0.5,1.0\}$，および $\epsilon_{\rm mix}\in\{1.0,1.5\}$ を組み合わせた計 $3\times2\times2=12$ ケースを計算し，$M_{\rm loss}(t)$ の終端値と停止条件の挙動を比較した．掃引に用いた主要設定を表\ref{tab:results_sweep_setup}に示す．なお，本章では $t_{\rm end}$ を $T_M(t)=T_{\rm end}$ に到達する時刻として定義するため，積分時間はケースごとに一致しない．一方で，温度が同一の段階まで冷却した時点の $M_{\rm loss}$ を比較する目的から，本章ではこの定義を採用する．

ここで，$\tau_0$ は式\ref{eq:tau_los_definition}で定義した $\tau_{\rm los}$ の初期値を与える無次元パラメータであり，照射を受け得る表層面密度の初期スケールを規格化する．また，温度ドライバ $T_M(t)$ の時間依存形は固定し，$T_{M,0}$ のみを変えることで巨大衝突直後の火星放射条件の不確実性を代表させる．例えば，巨大衝突後には火星表面温度が局所的に $5000$--$6000\,\mathrm{K}$ 程度まで上昇し，$3000$--$4000\,\mathrm{K}$ 程度の領域も広がることが報告されている\citep{Hyodo2018_ApJ860_150}．本章ではこれを踏まえ，$T_{M,0}=3000$--$5000\,\mathrm{K}$ を代表範囲として採用する．再現実行に必要な数値設定と物理量の対応は付録 B に整理する．

\begin{table}[t]
\centering
\caption{本章で用いるパラメータ掃引計算の主要条件}
\label{tab:results_sweep_setup}
\begin{tabular}{lll p{0.46\linewidth}}
\hline
区分 & 記号 & 設定値 & 備考 \\
\hline
モデル次元 & --- & 1D & リング分割による半径一次元モデル \\
空間分割 & $N_r$ & $32$ & $r/R_{\rm Mars}\in[1.0,2.7]$ \\
温度条件 & $T_{M,0}$ & $\{3000,4000,5000\}\,\mathrm{K}$ & $T_M(t)$ の形状は固定し，初期温度のみを変更 \\
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
