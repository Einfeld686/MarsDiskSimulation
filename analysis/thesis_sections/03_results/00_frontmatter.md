<!-- TEX_EXCLUDE_START -->
> **文書種別**: 結果（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

本章の主結果を先に述べる．放射圧ブローアウトによる累積損失 $M_{\rm loss}$ は，12 ケースの掃引で $2.0\times10^{-8}$--$1.1\times10^{-4}\,M_{\rm Mars}$ に分布する．また，$M_{\rm loss}$ の 99\% は $t\lesssim1\,\mathrm{yr}$ で確定し，流出は遷移期のごく初期に集中する．

これらは累積曲線（図\ref{fig:results_cumloss_grid}）と最終値一覧（表\ref{tab:results_sweep_massloss_cases}）で確認できる．パラメータ依存として，$M_{\rm loss}$ の支配因子は温度 $T_{M,0}$ と初期光学的厚さ $\tau_0$ であり，$3000\to4000\,\mathrm{K}$ で $M_{\rm loss}$ は約 3 桁増大し，$\tau_0$ を 2 倍にすると $M_{\rm loss}$ も概ね 2 倍となる．一方，供給混合係数 $\epsilon_{\rm mix}$ は本範囲では $M_{\rm loss}$ をほとんど変えない（5 節）．

序論で述べたように，$\Delta M_{\rm in}$ の系統差は (i) $\tau_{\rm los}$ の評価と (ii) $T_M(t)$ の有効期間に支配され得る．本章ではこれらを代表するパラメータとして $(T_{M,0},\tau_0)$ の感度として結果を整理する．

本章では，手法章で定義した軸対称 1D（リング分割）モデルに基づく数値結果を整理する．主な関心は，遷移期における放射圧による不可逆損失の累積量 $M_{\rm loss}$（序論の $\Delta M_{\rm in}$；式\ref{eq:delta_min_def}）と，それが温度や光学的厚さにどう依存するかである．この $M_{\rm loss}(t_{\rm end})$ は，長期モデルへ渡す内側円盤質量の更新量（式\ref{eq:min0_update}）に直接入る．本章では放射圧による寄与を分離するため追加シンクを無効化し（放射圧ブローアウトのみ；下限評価），$M_{\rm loss}=M_{\rm out,cum}$ として評価する．以降では，全円盤の $\dot{M}_{\rm out}(t)$（式\ref{eq:mdot_out_definition}）と $M_{\rm loss}(t)$（式\ref{eq:mass_loss_update}），および半径依存を含む $\dot{M}_{\rm out}(r,t)$ に焦点を当て，併せて質量保存と停止条件の内訳を検証する．

以下では，まずスイープ計算の条件とデータセットを整理し（1 節），全円盤積分量 $\dot{M}_{\rm out}(t)$ と $M_{\rm loss}(t)$ の代表的な時間発展を示す（2 節）．続いて，半径方向に分解した $\dot{M}_{\rm out}(r,t)$ の構造を可視化し（3 節），質量保存と停止条件の内訳を検証する（4 節）．最後に $M_{\rm loss}$ の主要パラメータ依存性を要約し（5 節），本章の小結を述べる（6 節）．

本章の結論として長期モデルへ渡す量は $M_{\rm loss}(t_{\rm end})$ であり（式\ref{eq:mass_loss_update}），以降の構成も「瞬時流出の時間発展（2 節；図\ref{fig:results_moutdot_grid}）→ 半径構造（3 節）→ 検証（4 節）→ 最終的な $M_{\rm loss}$ の回収（5 節；図\ref{fig:results_cumloss_grid}，表\ref{tab:results_sweep_massloss_cases}）」の順に読めるよう整理する．
