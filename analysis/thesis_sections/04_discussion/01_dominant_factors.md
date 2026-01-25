## 1. 放射圧ブローアウトによる質量損失の支配因子

第3章のパラメータ掃引では，累積質量損失 $M_{\rm loss}(t_{\rm end})$ が $2.0\times10^{-8}$ から $1.1\times10^{-4}\,M_{\rm Mars}$ の範囲に広がり，$T_{M,0}$ と $\tau_0$ に強く依存することが示された（表\ref{tab:results_sweep_massloss_cases}）．とくに温度を $T_{M,0}=3000\,\mathrm{K}$ から $5000\,\mathrm{K}$ へ上げると $M_{\rm loss}$ は 3--4 桁増加し，$\tau_0$ を 0.5 から 1.0 に増やすと $M_{\rm loss}$ は概ね 2 倍となる（表\ref{tab:results_sweep_massloss_cases}）．この差は，温度が放射圧パラメータ $\beta$ を $T_M^4$ で増幅するのに対し（式\ref{eq:beta_definition}），$\tau_0$ は初期表層面密度 $\Sigma_{\rm surf,0}$ の規格化をほぼ線形に変える（式\ref{eq:sigma_surf0_from_tau0}）という構造を反映している．

温度依存が強い理由は，$T_M$ が単に放射圧の大きさを増やすだけでなく，実効ブローアウト粒径 $s_{\rm blow}$ を押し上げ，PSD の「どの粒径帯が短時間で消失するか」を変える点にある．本研究では $\beta\ge0.5$ を非束縛条件として $s_{\rm blow}$ を定義し（式\ref{eq:s_blow_definition}），粒径下限 $s_{\min,\rm eff}$ を $s_{\min,\rm eff}=\max(s_{\min,\rm cfg},s_{\rm blow,eff})$ として更新する（式\ref{eq:smin_eff_definition}）．その結果，$s_{\rm blow}$ 近傍の質量分率が大きい場合には，わずかな $T_M$ の違いが「失われる質量の帯域」を大きく変え，$M_{\rm loss}$ の非線形増幅につながり得る．この点は，$s_{\rm blow}$ の $(r,T_M)$ 依存を可視化した図\ref{fig:results_forsterite_phase_heatmap}とも整合的である．

時間発展の観点では，放射圧流出率 $\dot{M}_{\rm out}(t)$ は計算開始直後に最大となり，その後急速に減衰して，多くのケースで $t\simeq0.05$--$1.3\,\mathrm{yr}$ で $10^{-14}\,M_{\rm Mars}\,\mathrm{s^{-1}}$ 以下へ低下する（図\ref{fig:results_moutdot_grid}）．累積量 $M_{\rm loss}(t)$ も $t\lesssim 1\,\mathrm{yr}$ でほぼ飽和し，全ケースで 99\% 到達時刻は $t\simeq0.19$--$0.84\,\mathrm{yr}$ である（図\ref{fig:results_cumloss_grid}）．したがって，本研究で推定される $M_{\rm loss}$ は，長期円盤進化（$10^3$--$10^6\,\mathrm{yr}$）に対しては連続的なシンクというより，「長期計算へ渡す初期条件の修正」として効く可能性が高い．

半径方向の構造は，初期に外側半径ほど流出が強く，時間とともに外側から流出が弱まって活発領域が内側へ縮む（図\ref{fig:results_time_radius_moutdot_tau_tau0p5}，図\ref{fig:results_time_radius_moutdot_tau_tau1p0}）．この傾向は，照射温度（あるいは受熱量）が半径に依存し，冷却とともに外側が先に「ブローアウトが有効な温度閾値」を下回る，という理解と整合的である．言い換えると，ある時刻における流出領域の外縁は「$s_{\rm blow}$ が PSD の損失帯域に入る半径」で定まるため，温度履歴 $T_M(t)$ の扱いは，総損失量だけでなく流出域の時空間構造にも影響する．

本節の要点は，$M_{\rm loss}$ が $(T_{M,0},\tau_0)$ により支配され，とくに $T_{M,0}$ が $s_{\rm blow}$ を通じて損失帯域を変えるため非線形になりやすい点にある．次節では，もう一つの関心である「質量供給フラックスの影響が小さかった理由」を，モデルの定義に立ち返って整理する．
