<!-- TEX_EXCLUDE_START -->
> **文書種別**: 手法（Diátaxis: Explanation）
<!-- TEX_EXCLUDE_END -->

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py
-->

# シミュレーション手法

本章では遷移期モデルの再現性を担保するため，状態変数・支配方程式・数値解法・出力・検証を再現手順に必要な範囲で定義する．

## 1. 状態変数と記号定義

粒径分布は対数ビンに離散化し，ビン $k$ の数面密度を $N_k(t)$ として扱う．粒子質量と表層面密度は式\ref{eq:mk_definition}–\ref{eq:sigma_surf_definition}で定義し，必要に応じて質量分率 $n_k$ を用いて分布形状と規格化を分離する．記号と単位の一覧は付録Eにまとめる．

\begin{equation}
\label{eq:mk_definition}
m_k=\frac{4\pi}{3}\rho s_k^3
\end{equation}

\begin{equation}
\label{eq:sigma_surf_definition}
\Sigma_{\rm surf}(t)=\sum_k m_k N_k(t)
\end{equation}

\begin{equation}
\label{eq:nk_massfrac_definition}
n_k(t)=\frac{m_k N_k(t)}{\Sigma_{\rm surf}(t)}
\end{equation}

PSD 下限は有効最小粒径 $s_{\min,\rm eff}$ により与え，設定下限とブローアウト境界の最大値で定める．$s_{\min,\rm eff}$ は供給注入とサイズ境界条件の下限として用い，時刻ごとに更新する．

\begin{equation}
\label{eq:smin_eff_definition}
s_{\min,\rm eff}=\max\!\left(s_{\min,\rm cfg},\,s_{\rm blow,eff}\right)
\end{equation}

光学的厚さは衝突頻度の評価に用いる垂直方向 $\tau_{\perp}$ と，放射遮蔽に用いる視線方向 $\tau_{\rm los}$ を区別する．表層不透明度 $\kappa_{\rm surf}$ から $\tau_{\perp}$ を定義し，$\tau_{\rm los}$ は幾何補正因子 $f_{\rm los}$ により与える．参照面密度 $\Sigma_{\tau_{\rm los}=1}$ は診断量として記録する．

\begin{equation}
\label{eq:kappa_surf_definition}
\kappa_{\rm surf}
=\frac{1}{\Sigma_{\rm surf}}\sum_k \pi s_k^2\,N_k
\end{equation}

\begin{equation}
\label{eq:tau_perp_definition}
\tau_{\perp}=\kappa_{\rm surf}\Sigma_{\rm surf}
\end{equation}

\begin{equation}
\label{eq:tau_los_definition}
\tau_{\rm los}=f_{\rm los}\tau_{\perp}
\end{equation}

\begin{equation}
\label{eq:sigma_tau_los1_definition}
\Sigma_{\tau_{\rm los}=1}=\left(f_{\rm los}\kappa_{\rm surf}\right)^{-1}
\end{equation}
<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/grid.py, marsdisk/io/tables.py, marsdisk/physics/psd.py, marsdisk/physics/sizes.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/initfields.py
-->

## 2. 支配方程式と適用範囲

本モデルは gas-poor 条件の軸対称ダスト円盤を対象とし，放射圧と衝突カスケードを同一時間発展で結合する．$\tau_{\rm los}>\tau_{\rm stop}$ に達した場合は適用範囲外として計算を停止する．gas-rich 表層 ODE に基づく流出は扱わない．

軌道力学量は代表半径 $r$ で評価し，ケプラー速度 $v_K$ と角速度 $\Omega$ は式\ref{eq:vK_definition}–\ref{eq:omega_definition}で与える．0D では $r_{\rm in}$–$r_{\rm out}$ を平均化した代表半径を用いる．

\begin{equation}
\label{eq:vK_definition}
v_K(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r}}
\end{equation}

\begin{equation}
\label{eq:omega_definition}
\Omega(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r^{3}}}
\end{equation}

### 2.1 放射圧とブローアウト

放射圧と重力の比 $\beta(s)$ は式\ref{eq:beta_definition}で定義し，Planck 平均の $\langle Q_{\rm pr}\rangle$ は外部テーブルから補間する（付録C）．$\beta\ge0.5$ を非束縛条件とし，ブローアウト境界粒径 $s_{\rm blow}$ は式\ref{eq:s_blow_definition}で与える．ブローアウト滞在時間は式\ref{eq:t_blow_definition}とし，既定値は $\chi_{\rm blow}=1$ とする．

\begin{equation}
\label{eq:beta_definition}
\beta(s) = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}(s)\rangle}{4\,G\,M_{\rm Mars}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\label{eq:s_blow_definition}
s_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle}{2\,G\,M_{\rm Mars}\,c\,\rho}
\end{equation}

\begin{equation}
\label{eq:t_blow_definition}
t_{\rm blow}=\chi_{\rm blow}\Omega^{-1}
\end{equation}

表層流出は Smol 経路の一次シンクとして式\ref{eq:surface_outflux}で与え，ブローアウト対象ビンでは $S_{{\rm blow},k}=1/t_{\rm blow}$ とする．円盤全体の流出率は式\ref{eq:mdot_out_definition}で定義し，0Dでは領域面積 $A$ を用いて近似する．

\begin{equation}
\label{eq:surface_outflux}
\dot{\Sigma}_{\rm out} = \sum_k m_k S_{{\rm blow},k} N_k
\end{equation}

\begin{equation}
\label{eq:mdot_out_definition}
\dot{M}_{\rm out}(t)=\int_{r_{\rm in}}^{r_{\rm out}}2\pi r\,\dot{\Sigma}_{\rm out}(r,t)\,dr
\end{equation}

### 2.2 遮蔽

遮蔽係数 $\Phi$ は $\tau_{\rm los}$ の関数として与え，本研究では吸収減衰近似 $\Phi=\exp(-\tau_{\rm los})$ を用いる．$\Phi$ から有効不透明度 $\kappa_{\rm eff}$ を定義し，診断量 $\Sigma_{\tau_{\rm eff}=1}$ を式\ref{eq:sigma_tau1_definition}で評価する．

\begin{equation}
\label{eq:phi_definition}
\Phi=\exp(-\tau_{\rm los})
\end{equation}

\begin{equation}
\label{eq:kappa_eff_definition}
\kappa_{\rm eff} = \Phi\,\kappa_{\rm surf}
\end{equation}

\begin{equation}
\label{eq:sigma_tau1_definition}
\Sigma_{\tau_{\rm eff}=1} =
\begin{cases}
 \kappa_{\rm eff}^{-1}, & \kappa_{\rm eff} > 0,\\
 \infty, & \kappa_{\rm eff} \le 0
\end{cases}
\end{equation}

### 2.3 表層への質量供給

表層への供給は面密度生成率として与え，混合係数 $\epsilon_{\rm mix}$ と入力関数 $R_{\rm base}$ から式\ref{eq:prod_rate_definition}で定義する．供給率は PSD のソース項 $F_k$ として式\ref{eq:supply_injection_definition}で注入し，質量保存条件 $\sum_k m_k F_k=\dot{\Sigma}_{\rm in}$ を満たすよう重み $w_k$ を正規化する．標準計算では注入分布を $dN/ds\propto s^{-q}$ とし，$w_k$ は式\ref{eq:supply_injection_powerlaw_bins}で与える．下限は $s_{\min,\rm eff}$ でクリップする．

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\rm prod}(t,r) = \max\!\left(\epsilon_{\rm mix}\;R_{\rm base}(t,r),\,0\right)
\end{equation}

\begin{equation}
\label{eq:supply_injection_definition}
F_k=\frac{\dot{\Sigma}_{\rm in}\,w_k}{m_k},\qquad \sum_k m_k F_k=\dot{\Sigma}_{\rm in}
\end{equation}

\begin{equation}
\label{eq:supply_injection_powerlaw_bins}
\tilde{w}_k=\int_{\max(s_{k-},s_{\rm floor})}^{\min(s_{k+},s_{\rm ceil})} s^{-q}\,ds,\qquad
F_k=\frac{\dot{\Sigma}_{\rm in}\,\tilde{w}_k}{\sum_j m_j\tilde{w}_j}
\end{equation}

### 2.4 衝突カスケード

PSD の時間発展は Smoluchowski 方程式（式\ref{eq:smoluchowski}）で与え，注入 $F_k$ と一次シンク $S_k$（ブローアウト・昇華）を含める．破片生成テンソル $Y_{kij}$ は質量保存条件 $\sum_k Y_{kij}=1$ を満たすよう定義する．

\begin{equation}
\label{eq:smoluchowski}
\dot{N}_k = \sum_{i\le j} C_{ij}\,\frac{m_i+m_j}{m_k}\,Y_{kij} - \left(\sum_j C_{kj} + C_{kk}\right) + F_k - S_k N_k
\end{equation}

\begin{equation}
\label{eq:fragment_yield_normalization}
\sum_k Y_{kij}=1
\end{equation}

衝突イベント率 $C_{ij}$ は式\ref{eq:collision_kernel}で与え，相対速度 $v_{ij}$ は入力の $e,i$ と $v_K$ から式\ref{eq:vrel_pericenter_definition}で評価する．ビンの衝突寿命は式\ref{eq:t_coll_definition}とし，時間刻みの上限に用いる．破壊閾値 $Q_D^*$ は式\ref{eq:qdstar_definition}の速度補間を用い，最大残存率 $F_{LF}$ と破片分布 $w^{\rm frag}_k$ を通じて式\ref{eq:fragment_tensor_definition}で $Y_{kij}$ を構成する．

\begin{equation}
\label{eq:collision_kernel}
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,
\frac{\pi\,(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}},
\qquad H_{ij} = \sqrt{H_i^{2}+H_j^{2}}
\end{equation}

\begin{equation}
\label{eq:vrel_pericenter_definition}
v_{ij}=v_K\,\sqrt{\frac{1+e}{1-e}}
\end{equation}

\begin{equation}
\label{eq:t_coll_definition}
t_{{\rm coll},k}=\left(\frac{\sum_j C_{kj}+C_{kk}}{N_k}\right)^{-1}
\end{equation}

\begin{equation}
\label{eq:qdstar_definition}
Q_{D}^{*}(s,\rho,v)=Q_s(v)\,s^{-a_s(v)}+B(v)\,\rho\,s^{b_g(v)}
\end{equation}

\begin{equation}
\label{eq:fragment_weights}
w^{\rm frag}_k(k_{\rm LR})=\frac{\int_{s_{k-}}^{s_{k+}} s^{-\alpha_{\rm frag}}\,ds}{\sum_{\ell\le k_{\rm LR}}\int_{s_{\ell-}}^{s_{\ell+}} s^{-\alpha_{\rm frag}}\,ds}
\end{equation}

\begin{equation}
\label{eq:fragment_tensor_definition}
Y_{kij}=F_{LF}\delta_{k k_{\rm LR}}+(1-F_{LF})\,w^{\rm frag}_k(k_{\rm LR})
\end{equation}

### 2.5 昇華と追加シンク

昇華は HKL フラックス $J(T)$ を用い，粒径縮小を式\ref{eq:dsdt_definition}で与える．昇華で用いる粒子温度は灰色体近似で式\ref{eq:grain_temperature_definition}とする．飽和蒸気圧は Clausius 形またはテーブル補間を用い（式\ref{eq:psat_definition}），基準ケースの係数は付録Aに示す．

\begin{equation}
\label{eq:grain_temperature_definition}
T_p = T_M\,\langle Q_{\rm abs}\rangle^{1/4}\sqrt{\frac{R_{\rm Mars}}{2r}}
\end{equation}

\begin{equation}
\label{eq:hkl_flux}
J(T) =
 \alpha_{\rm evap}\max\!\bigl(P_{\rm sat}(T) - P_{\rm gas},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}
\end{equation}

\begin{equation}
\label{eq:psat_definition}
P_{\rm sat}(T) =
\begin{cases}
 10^{A - B/T}, & \text{Clausius 型},\\
  10^{{\rm PCHIP}_{\log_{10}P}(T)}, & \text{テーブル補間}.
\end{cases}
\end{equation}

\begin{equation}
\label{eq:dsdt_definition}
\frac{ds}{dt}=-\frac{J(T)}{\rho}
\end{equation}
## 3. 初期条件・境界条件・パラメータ採用値

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/supply.py, marsdisk/physics/phase.py, marsdisk/physics/shielding.py
-->

初期条件は $t=t_0$ における PSD $N_k(t_0)$ と内側円盤質量 $M_{\rm in}(t_0)$ で与える．初期 PSD は総質量または光学的厚さ $\tau_0$ により規格化し，標準では $\tau_{\rm los}=1$ を満たすように一様スケーリングする．

火星温度 $T_M(t)$ は外部ドライバとして与え，$\langle Q_{\rm pr}\rangle$ と $\Phi$ のテーブルは付録Cの外部入力を用いる．物性値（$\rho$，$\langle Q_{\rm pr}\rangle$ テーブル，HKL 係数など）と基準ケースの採用値は表\ref{tab:methods_baseline_params}と付録Aに整理する．感度掃引に用いる追加パラメータは付録Aにまとめる．

サイズ境界は $s\in[s_{\min},s_{\max}]$ とし，$s_{\min,\rm eff}$ 未満は存在しない（ブローアウトで即時除去）．0D では計算領域 $[r_{\rm in},r_{\rm out}]$ を面積 $A$ の環状領域として扱い，半径方向拡散は標準計算では無効とする．

\begin{equation}
\label{eq:annulus_area_definition}
A=\pi\left(r_{\rm out}^2-r_{\rm in}^2\right)
\end{equation}

\begin{table}[t]
  \centering
  \caption{基準計算の採用値（主要パラメータ）}
  \label{tab:methods_baseline_params}
  \begin{tabular}{p{0.28\textwidth} p{0.2\textwidth} p{0.16\textwidth} p{0.26\textwidth}}
    \hline
    記号 & 値 & 単位 & 備考 \\
    \hline
    $s_{\min}$ & $1.0\times10^{-7}$ & m & PSD 下限（付録B） \\
    $s_{\max}$ & $3.0$ & m & PSD 上限（付録B） \\
    $n_{\rm bins}$ & 40 & -- & サイズビン数（付録B） \\
    $\tau_0$ & 1.0 & -- & 初期規格化（本研究） \\
    $\chi_{\rm blow}$ & 1.0 & -- & $t_{\rm blow}$ 係数（本研究） \\
    $t_{\rm end}$ & 2.0 & yr & 積分期間（本研究） \\
    $q$ & 3.5 & -- & 注入べき指数（本研究） \\
    $\epsilon_{\rm mix}$ & 1.0 & -- & 混合係数（本研究） \\
    $\rho$ & 3270 & kg\,m$^{-3}$ & フォルステライト \cite{VanLieshoutMinDominik2014_AA572_A76} \\
    \hline
  \end{tabular}
\end{table}
## 4. 離散化と時間積分法

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

サイズ空間は対数等間隔のグリッドで離散化し，各ビン中心 $s_k$ に対応する $N_k$ を状態量として進める．注入・損失・再配分はビン上で行い，境界は $s_{\min,\rm eff}$ と $s_{\max}$ で定義する．

時間積分は IMEX-BDF(1) を用い，衝突ロス項のみ陰的，破片生成・供給・一次シンクは陽的に扱う．更新式は式\ref{eq:imex_bdf1_update}で与え，内部ステップ幅 $dt_{\rm eff}$ は外側ステップ幅 $\Delta t$ 以下とする．$dt_{\rm eff}$ は $\min(\Delta t,\,0.1\min_k t_{{\rm coll},k})$ を初期値とし，必要に応じて縮小して非負性と質量保存を確保する．

\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}
\end{equation}

質量保存は式\ref{eq:mass_budget_definition}で定義し，各ステップで相対誤差 $\epsilon_{\rm mass}$ を評価する．$\Delta t$ は $t_{\rm blow}$ と $t_{{\rm coll},k}$ をともに解像するよう制約し，収束判定は検証節の基準に従う．

\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
 \Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta\Sigma &= \Sigma^{n+1} + \Delta t\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + \Delta t\,\dot{\Sigma}_{\rm prod}^{(<s_{\rm blow})}\right),\\
 \epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}
## 5. 出力

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, marsdisk/io/checkpoint.py, marsdisk/io/archive.py, marsdisk/archive.py
-->

各ステップの主要診断量（$t,\,\Delta t,\,\tau_{\rm los},\,s_{\rm blow},\,s_{\min},\,\Sigma_{\rm surf},\,\dot{M}_{\rm out}$ など）を時系列として保存し，PSD 履歴 $N_k(t)$ を別途保存する．終端要約には 2 年累積損失 $M_{\rm loss}$ と主要スカラーを含め，質量検査ログは別ファイルに記録する．出力ファイルと主要カラムの一覧は付録Aに示す．

累積損失は式\ref{eq:mass_loss_update}で更新し，$\dot{M}_{\rm out}$ と追加シンクの寄与を区分一定近似で積算する．質量や流出率は $M_{\rm Mars}$ で規格化した値も併記する．

\begin{equation}
\label{eq:mass_loss_update}
M_{\rm loss}^{n+1}=M_{\rm loss}^{n}+\Delta t\left(\dot{M}_{\rm out}^{n}+\dot{M}_{\rm sinks}^{n}\right)
\end{equation}

## 6. 検証

検証は質量保存，衝突寿命スケーリング，wavy PSD の定性，IMEX 収束の4項目で行う．合格基準は表\ref{tab:validation_criteria}に示し，本文で示す結果は全て基準を満たした計算に限定する．質量保存は式\ref{eq:mass_budget_definition}の $\epsilon_{\rm mass}$ が $0.5\%$ 以下であることを要求する．

衝突寿命スケーリングは推定値 $t_{\rm coll}^{\rm est}=T_{\rm orb}/(2\pi\tau_{\perp})$ とモデル内 $t_{\rm coll}$ の比が $0.1$–$10$ に入ることを確認する \cite{StrubbeChiang2006_ApJ648_652}．wavy PSD は $s_{\rm blow}$ 近傍の $\log N_k$ の二階差分が符号反転することを指標とし \cite{ThebaultAugereau2007_AA472_169}，IMEX 収束は $\Delta t$ と $\Delta t/2$ の結果差が $1\%$ 以下であることを求める \cite{Krivov2006_AA455_509}．収束判定と PSD 解像度の比較は同一基準で行う．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{3pt}
  \caption{検証項目と合格基準}
  \label{tab:validation_criteria}
  \begin{tabular}{p{0.27\textwidth} p{0.69\textwidth}}
    \hline
    検証項目 & 合格基準（許容誤差） \\
    \hline
    質量保存 & 相対質量誤差 $|\epsilon_{\rm mass}(t)|$ の最大値が $0.5\%$ 以下 \\
    衝突寿命スケーリング & $t_{\rm coll}^{\rm est}=T_{\rm orb}/(2\pi\tau_{\perp})$ に対する比が $0.1$–$10$ \\
    wavy PSD & $s_{\rm blow}$ 近傍で $\Delta^2 \log N_k$ の符号が交互に反転 \\
    IMEX 収束 & $\Delta t$ と $\Delta t/2$ の主要時系列差が $1\%$ 以下 \\
    \hline
  \end{tabular}
\end{table}
### 付録 A. 再現実行と保存情報

<!--
実装(.py): scripts/runsets/windows/preflight_checks.py, scripts/runsets/common/read_overrides_cmd.py, scripts/runsets/common/read_study_overrides.py, scripts/runsets/common/write_base_overrides.py, scripts/runsets/common/write_sweep_list.py, scripts/runsets/common/build_overrides.py, scripts/runsets/common/next_seed.py, scripts/runsets/common/calc_parallel_jobs.py, scripts/runsets/common/calc_cell_jobs.py, scripts/runsets/common/calc_cpu_target_jobs.py, scripts/runsets/common/calc_thread_limit.py, scripts/tests/measure_case_output_size.py, scripts/runsets/common/run_one.py, scripts/runsets/common/run_sweep_worker.py, scripts/runsets/common/hooks/plot_sweep_run.py, scripts/runsets/common/hooks/evaluate_tau_supply.py, scripts/runsets/common/hooks/archive_run.py, scripts/runsets/common/hooks/preflight_streaming.py, marsdisk/run.py
-->

本研究の再現性は，(i) 入力（設定ファイルとテーブル）を固定し，(ii) 実行時に採用された値と条件を保存し，(iii) 時系列・要約・検証ログを保存することで担保する．本付録では，論文として最低限必要な「保存すべき情報」をまとめる．

#### A.1 固定する入力（再現の前提）

- **設定（YAML）**: 物理スイッチ，初期条件，時間刻み，停止条件，感度掃引の対象パラメータ．
- **テーブル（CSV/NPZ）**: $\langle Q_{\rm pr}\rangle$ や遮蔽係数 $\Phi$ などの外部テーブル．
- **乱数シード**: 乱数を用いる過程がある場合はシードを固定する．

#### A.2 保存する出力（再解析の最小セット）

本論文で示す結果は，以下の情報を保存して再解析できる形で管理した．

- **実行条件の記録**: `run_card.md`（実行コマンド，環境，主要パラメータ，生成物ハッシュ）．
- **採用値の記録**: `run_config.json`（$\rho$，$\langle Q_{\rm pr}\rangle$ テーブル，物理トグル，$s_{\rm blow}$ など，実行時に採用した値と出典）．
- **時系列**: `series/run.parquet`（主要スカラー量の時系列）．
- **PSD 履歴**: `series/psd_hist.parquet`（$N_k(t)$ と $\Sigma_{\rm surf}(t)$ の履歴）．
- **要約**: `summary.json`（2 年累積量などの集約）．
- **検証ログ**: `checks/mass_budget.csv`（式\ref{eq:mass_budget_definition} に基づく質量検査）．

保存ファイルでは数値の桁を揃えるため，質量と質量流出率を火星質量 $M_{\rm Mars}$ で規格化した値（例：$\dot{M}_{\rm out}/M_{\rm Mars}$）を併記する．定義は付録E（記号表）を参照する．

\begin{table}[t]
  \centering
  \caption{主要出力量と本文の参照先}
  \label{tab:app_outputs_map}
  \begin{tabular}{p{0.24\textwidth} p{0.36\textwidth} p{0.30\textwidth}}
    \hline
    量 & 本文での定義 & 保存先 \\
	    \hline
	    $s_{\rm blow}$ & 式\ref{eq:s_blow_definition} & \texttt{series/run.parquet} \\
		    $s_{\min,\rm eff}$ & 式\ref{eq:smin_eff_definition} & \texttt{series/run.parquet} \\
	    $\dot{\Sigma}_{\rm out}$ & 式\ref{eq:surface_outflux} & \texttt{series/run.parquet} \\
	    $\dot{M}_{\rm out}$ & 式\ref{eq:mdot_out_definition} & \texttt{series/run.parquet} \\
	    $M_{\rm loss}$ & 式\ref{eq:mass_loss_update} & \texttt{summary.json} \\
	    $\epsilon_{\rm mass}$ & 式\ref{eq:mass_budget_definition} & \texttt{checks/mass\_budget.csv} \\
	    $N_k(t)$ & 1節 & \texttt{series/psd\_hist.parquet} \\
	    \hline
  \end{tabular}
\end{table}

#### A.3 感度掃引で用いる代表パラメータ（例）

\begin{table}[t]
  \centering
  \caption{感度掃引で用いる代表パラメータ（例）}
  \label{tab:app_methods_sweep_defaults}
  \begin{tabular}{p{0.24\textwidth} p{0.2\textwidth} p{0.46\textwidth}}
    \hline
    変数 & 代表値 & 意味 \\
    \hline
    $T_M$ & 4000, 3000 & 火星温度 [K] \\
    $\epsilon_{\rm mix}$ & 1.0, 0.5 & 混合係数（供給の有効度） \\
    $\tau_0$ & 1.0, 0.5 & 初期光学的厚さ \\
    $i_0$ & 0.05, 0.10 & 初期傾斜角 \\
    $f_{Q^*}$ & 0.3, 1, 3（$\times$基準値） & $Q_D^*$ の係数スケール（proxy の不確かさの感度） \\
    \hline
  \end{tabular}
\end{table}

#### A.4 検証結果の提示（代表ケース）

本論文では，表\ref{tab:validation_criteria}の合格基準に基づく検証を全ケースで実施し，合格した結果のみを採用する．代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列例を図\ref{fig:app_validation_mass_budget_example}に示す．

\begin{figure}[t]
  \centering
  % \includegraphics[width=\linewidth]{figures/thesis/validation_mass_budget_example.pdf}
  \caption{代表ケースにおける質量検査 $\epsilon_{\rm mass}(t)$ の時系列（例）}
  \label{fig:app_validation_mass_budget_example}
\end{figure}

#### A.5 基準ケースで用いる物性値

本研究の基準ケースで採用する物性値（フォルステライト基準）を表\ref{tab:run_sweep_material_properties}にまとめる．密度・放射圧効率・昇華係数はフォルステライト値を採用し，$Q_D^*$ は peridot projectile 実験の $Q^*$ を参照して BA99 係数をスケーリングした proxy を用いる．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{3pt}
  \caption{基準ケースで用いる物性値（フォルステライト基準）}
  \label{tab:run_sweep_material_properties}
  \begin{tabular}{p{0.18\textwidth} p{0.38\textwidth} p{0.22\textwidth} p{0.16\textwidth}}
    \hline
    記号 & 意味 & 値 & 出典 \\
    \hline
	    $\rho$ &
	    粒子密度 [kg\,m$^{-3}$] &
	    3270 &
	    \cite{VanLieshoutMinDominik2014_AA572_A76} \\
    $\langle Q_{\rm pr}\rangle$ &
    Planck平均放射圧効率（テーブル） &
    \path{data/}\newline\path{qpr_planck_forsterite_mie.csv} &
    \cite{BohrenHuffman1983_Wiley,Zeidler2015_ApJ798_125} \\
	    $\alpha$ &
	    HKL 蒸発係数 &
	    0.1 &
	    \cite{VanLieshoutMinDominik2014_AA572_A76} \\
	    $\mu$ &
	    分子量 [kg\,mol$^{-1}$] &
	    0.140694 &
	    \cite{VanLieshoutMinDominik2014_AA572_A76} \\
	    $A_{\rm solid}$ &
	    固相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm solid}-B_{\rm solid}/T$ &
	    13.809441833 &
	    \cite{VanLieshoutMinDominik2014_AA572_A76} \\
	    $B_{\rm solid}$ &
	    同上（$T$ は K） &
	    28362.904024 &
	    \cite{VanLieshoutMinDominik2014_AA572_A76} \\
	    $T_{\rm solid}^{\rm valid}$ &
	    固相フィットの適用温度範囲 [K] &
	    1673--2133 &
	    \cite{VanLieshoutMinDominik2014_AA572_A76} \\
    $A_{\rm liq}$ &
    液相飽和蒸気圧フィット $\log_{10}P(\mathrm{Pa})=A_{\rm liq}-B_{\rm liq}/T$ &
    11.08 &
    \cite{FegleySchaefer2012_arXiv} \\
    $B_{\rm liq}$ &
    同上（$T$ は K） &
    22409.0 &
    \cite{FegleySchaefer2012_arXiv} \\
    $T_{\rm liq}^{\rm valid}$ &
    液相フィットの適用温度範囲 [K] &
    2163--3690 &
    \cite{FegleySchaefer2012_arXiv} \\
    $T_{\rm switch}$ &
    固相$\to$液相フィット切替温度 [K] &
    2163 &
    \cite{FegleySchaefer2012_arXiv} \\
    $T_{\rm condense}$, $T_{\rm vaporize}$ &
    相判定のヒステリシス閾値 [K]（運用値） &
    2162, 2163 &
    本研究（スキーマ要件）, 基準: \cite{FegleySchaefer2012_arXiv} \\
    $f_{Q^*}$ &
    $Q_D^*$ 係数スケール（peridot proxy） &
    5.574 &
    \cite{Avdellidou2016_MNRAS464_734,BenzAsphaug1999_Icarus142_5} \\
    \hline
  \end{tabular}
\end{table}

<!-- TEX_EXCLUDE_START -->
以下は運用スクリプトや OS 依存の実行方法，リポジトリ内部の詳細（環境変数・hook・ファイル一覧）であり，論文PDFでは除外する．

代表的な実行コマンドとシナリオは analysis/run-recipes.md に集約する．運用スイープは `scripts/runsets/windows/run_sweep.cmd` を正とし，既定の `CONFIG_PATH`/`OVERRIDES_PATH` と引数の扱いは同スクリプトに従う．  
- **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEFAULT_PATHS`\newline `::REF:CLI_ARGS`

```cmd
rem Windows: sweep
scripts\runsets\windows\run_sweep.cmd ^
  --config scripts\runsets\common\base.yml ^
  --overrides scripts\runsets\windows\overrides.txt ^
  --out-root out
```

- `--no-preflight` は拒否される．既定では `SKIP_PREFLIGHT=1` でスキップされるため，事前チェックを走らせる場合は `SKIP_PREFLIGHT=0` を指定する．\newline `--preflight-only` で事前チェックのみ実行．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PREFLIGHT_ARGS`\newline `::REF:PREFLIGHT`
- `--no-plot` と `--no-eval` は hook を抑制し，`HOOKS_ENABLE` のフィルタに反映される．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CLI_ARGS` / `::REF:HOOKS`
- 依存関係は `requirements.txt` から自動導入され，\newline `SKIP_PIP=1` または `REQUIREMENTS_INSTALLED=1` で無効化できる．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:DEPENDENCIES`
- `OUT_ROOT` は内部/外部の自動選択が働き，\newline `io.archive.dir` が未設定/無効なら `OUT_ROOT\\archive` を付加した overrides を生成する．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:OUT_ROOT`\newline `::REF:ARCHIVE_CHECKS`
- `io.archive.*` の要件を満たさない場合は実行中断．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:ARCHIVE_CHECKS`
- 実行本体は `run_temp_supply_sweep.cmd` を子として起動する．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:CHILD_RUN`
- スイープ並列は既定で有効 (`SWEEP_PARALLEL=1`) で，\newline ネスト回避のため `MARSDISK_CELL_PARALLEL=0` によりセル並列は無効化される．\newline サイズプローブで `PARALLEL_JOBS` が調整される場合がある．\newline **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:PARALLEL`

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{run\_sweep 既定の $Q_D^*$ 係数テーブル（\texttt{qstar.coeff\_table}）}
  \label{tab:run_sweep_qdstar_coeff_table}
  \begin{tabular}{p{0.14\textwidth} p{0.20\textwidth} p{0.14\textwidth} p{0.20\textwidth} p{0.14\textwidth}}
    \hline
    $v_{\rm ref}$ [km/s] & $Q_s$ & $a_s$ & $B$ & $b_g$ \\
    \hline
    1 & 1.9509e8 & 0.38 & 0.8187652527440811 & 1.36 \\
    2 & 1.9509e8 & 0.38 & 1.28478039442684 & 1.36 \\
    3 & 1.9509e8 & 0.38 & 1.6722 & 1.36 \\
    4 & 2.92635e8 & 0.38 & 2.2296 & 1.36 \\
    5 & 3.9018e8 & 0.38 & 2.787 & 1.36 \\
    6 & 3.9018e8 & 0.38 & 3.137652034251613 & 1.36 \\
    7 & 3.9018e8 & 0.38 & 3.4683282387928047 & 1.36 \\
    \hline
  \end{tabular}
\end{table}

表\ref{tab:run_sweep_qdstar_coeff_table} の係数は BA99 の基準テーブル \cite{BenzAsphaug1999_Icarus142_5} を基準に，$f_{Q^*}=5.574$（表\ref{tab:run_sweep_material_properties}）で $Q_s,B$ のみをスケーリングして作成している（peridot proxy: \cite{Avdellidou2016_MNRAS464_734}）．

#### run_sweep.cmd の主要環境変数

既定値は `run_sweep.cmd` のデフォルト設定に従う．主要環境変数は次の表に示す．  
- **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:SWEEP_DEFAULTS`

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{run\_sweep.cmd の主要環境変数}
  \label{tab:run_sweep_env}
  \begin{tabular}{p{0.28\textwidth} p{0.42\textwidth} p{0.18\textwidth}}
    \hline
    変数 & 意味 & 既定値 \\
    \hline
    \texttt{SWEEP\_TAG} & 出力タグ & \texttt{temp\_supply}\newline \texttt{\_sweep}\newline \texttt{\_1d} \\
    \texttt{GEOMETRY\_MODE} & 形状モード & \texttt{1D} \\
    \texttt{GEOMETRY\_NR} & 半径セル数 & 32 \\
    \texttt{SHIELDING\_MODE} & 遮蔽モード & \texttt{off} \\
    \texttt{SUPPLY\_MU}\newline \texttt{\_REFERENCE\_TAU} & 供給基準$\tau$ & 1.0 \\
    \texttt{SUPPLY\_FEEDBACK\_ENABLED} & $\tau$フィードバック & 0 \\
    \texttt{SUPPLY\_TRANSPORT\_MODE} & 供給トランスポート & \texttt{direct} \\
    \texttt{SUPPLY\_TRANSPORT}\newline \texttt{\_TMIX\_ORBITS} & ミキシング時間 [orbits] & \texttt{off} \\
    \texttt{COOL\_TO\_K} & 温度停止閾値 [K] & 1000 \\
    \texttt{PARALLEL\_MODE} & 並列モード\newline （\texttt{SWEEP\_PARALLEL=1} ではセル並列は無効化） & \texttt{cell} \\
    \texttt{SWEEP\_PARALLEL} & スイープ並列 & 1 \\
    \texttt{PARALLEL\_JOBS} & sweep job 数 & 6 \\
    \hline
  \end{tabular}
\end{table}

- 固定地平で動かす場合は `COOL_TO_K=none` と `T_END_YEARS` を指定する．\newline
  **参照**: `scripts/runsets/windows/run_sweep.cmd` の `::REF:TEMPERATURE_STOP`

#### run_sweep のスイープ定義（run_temp_supply_sweep.cmd 経由）

`run_sweep.cmd` は `run_temp_supply_sweep.cmd` を呼び出し，**ベース設定 + 追加 overrides + ケース overrides** の 3 層をマージして各ケースを実行する．優先順位は「base defaults < overrides file < per-case overrides」で，各ケースの設定は一時ファイルに出力して `marsdisk.run` に渡される．

- **ベース設定**: `scripts/runsets/common/base.yml` を基準とし，\newline Windows 既定の `scripts/runsets/windows/overrides.txt` を追加する．
- **ケース生成**: `T_LIST`, `EPS_LIST`, `TAU_LIST`, `I0_LIST` の直積でスイープを作る．\newline `--study` を指定した場合は，`read_study_overrides.py` でリストや環境変数を上書きできる．
- **既定のスイープ値**（run_sweep 既定値）:

  \begin{table}[t]
    \centering
    \caption{run\_sweep 既定のスイープパラメータ}
    \label{tab:run_sweep_defaults}
    \begin{tabular}{p{0.24\textwidth} p{0.2\textwidth} p{0.46\textwidth}}
      \hline
      変数 & 既定値 & 意味 \\
      \hline
      \texttt{T\_LIST} & 4000, 3000 & 火星温度 $T_M$ [K] \\
      \texttt{EPS\_LIST} & 1.0, 0.5 & 混合係数 $\epsilon_{\rm mix}$ \\
      \texttt{TAU\_LIST} & 1.0, 0.5 & 初期光学的厚さ $\tau_0$ \\
      \texttt{I0\_LIST} & 0.05, 0.10 & 初期傾斜角 $i_0$ \\
      \hline
    \end{tabular}
  \end{table}

- **ケースごとの overrides**:
  - `io.outdir`: 出力先（後述のケースディレクトリ）
  - `dynamics.rng_seed`: 乱数シード
  - `radiation.TM_K`: 火星温度（`T_LIST`）
  - `supply.mixing.epsilon_mix`: 混合係数（`EPS_LIST`）
  - `optical_depth.tau0_target`: 初期光学的厚さ（`TAU_LIST`）
  - `dynamics.i0`: 初期傾斜角（`I0_LIST`）
  - `radiation.mars_temperature_driver.table`\newline `.path`: `COOL_MODE!=hyodo` のとき `data/mars_temperature_T{T}p0K.csv` を使用
  - `numerics.t_end_*` と `scope.analysis_years`:\newline `END_MODE` に応じて温度停止または固定年数に切り替え

- **出力ディレクトリ構造**（run_sweep 既定）:\newline
  `out/<SWEEP_TAG>/<RUN_TS>__<GIT_SHA>__seed<BATCH_SEED>/<TITLE>/`\newline
  ここで `TITLE` は `T{T}_eps{EPS}_tau{TAU}_i0{I0}` の形式（小数点は `p` 置換）．


---
<!-- TEX_EXCLUDE_END -->
### 付録 B. 設定→物理対応クイックリファレンス

<!--
実装(.py): marsdisk/schema.py, marsdisk/config_utils.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/phase.py, marsdisk/physics/psd.py, marsdisk/physics/viscosity.py
-->

設定と物理の対応を次の表にまとめる．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{設定キーと物理の対応}
  \label{tab:app_config_physics_map}
  \begin{tabular}{p{0.38\textwidth} p{0.26\textwidth} p{0.22\textwidth}}
    \hline
    設定キー & 物理 & 本文参照 \\
    \hline
    \texttt{radiation.TM\_K} & 火星温度 & 3節 \\
    \texttt{radiation.mars\_temperature}\newline \texttt{\_driver}\newline \texttt{.*} & 冷却ドライバ & 3節 \\
	    \texttt{shielding.mode} & 遮蔽 $\Phi$ & 2.2節 \\
	    \texttt{shielding.los\_geometry}\newline \texttt{.*} & 視線補正係数 $f_{\rm los}$ & 1節 \\
	    \texttt{sinks.mode} & 昇華/ガス抗力 & 2.5節 \\
	    \texttt{blowout.enabled} & ブローアウト損失 & 2.1節 \\
	    \texttt{supply.mode} & 表層再供給 & 2.3節 \\
    \texttt{supply.feedback}\newline \texttt{.*} & $\tau$フィードバック制御 & 2.3節 \\
    \texttt{supply.temperature}\newline \texttt{.*} & 温度カップリング & 2.3節 \\
    \texttt{supply.reservoir}\newline \texttt{.*} & 有限質量リザーバ & 2.3節 \\
    \texttt{supply.transport}\newline \texttt{.*} & 深層ミキシング & 2.3節 \\
    \texttt{init\_tau1.*} & 初期$\tau=1$スケーリング & 3節 \\
    \texttt{phase.*} & 相判定 & 本文では扱わない \\
    \texttt{phase.q\_abs\_mean} & $\langle Q_{\rm abs}\rangle$（粒子温度） & 本文では扱わない \\
    \texttt{numerics.checkpoint.*} & チェックポイント & 本文では扱わない \\
    \texttt{numerics.t\_end\_until}\newline \texttt{\_temperature}\newline \texttt{\_K} & 温度停止条件 & 本文では扱わない \\
    \texttt{ALLOW\_TL2003} & gas-rich 表層 ODE トグル & 本文では扱わない \\
    \texttt{psd.wavy\_strength} & "wavy" 強度（0 で無効） & 6節 \\
    \hline
  \end{tabular}
\end{table}

#### B.1 粒径グリッド（既定値）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{PSD グリッドの既定値}
  \label{tab:app_psd_grid_defaults}
  \begin{tabular}{p{0.36\textwidth} p{0.2\textwidth} p{0.32\textwidth}}
    \hline
    設定キー & 既定値 & 意味 \\
    \hline
    \texttt{sizes.s\_min} & 1e-7 m & 最小粒径 $s_{\min,\rm cfg}$ \\
    \texttt{sizes.s\_max} & 3.0 m & 最大粒径 \\
    \texttt{sizes.n\_bins} & 40 & サイズビン数 \\
    \hline
  \end{tabular}
\end{table}

表\ref{tab:app_psd_grid_defaults}の既定値では $s$ 範囲が広いため，対数等間隔の隣接比 $s_{k+1}/s_k$ は $O(1.5)$ となる．$s_{\rm blow}$ 近傍の解像度が必要な場合は $n_{\rm bins}$ を増やすか，対象とする $s_{\max}$ を再検討する（1節，6節）．

#### B.2 初期化（$\tau=1$ スケーリング）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{初期 $\tau=1$ スケーリングの設定}
  \label{tab:app_init_tau1_settings}
  \begin{tabular}{p{0.42\textwidth} p{0.3\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{init\_tau1.scale\_to\_tau1} & 有効化フラグ & \texttt{false} \\
    \texttt{init\_tau1.tau\_field} & \texttt{vertical} / \texttt{los} & \texttt{los} \\
    \texttt{init\_tau1.target\_tau} & 目標光学的厚さ & 1.0 \\
    \hline
  \end{tabular}
\end{table}

#### B.3 供給（フィードバック・温度カップリング・注入）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{供給フィードバックの設定}
  \label{tab:app_supply_feedback_settings}
  \begin{tabular}{p{0.4\textwidth} p{0.36\textwidth} p{0.14\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.feedback.target\_tau} & 目標光学的厚さ & 0.9 \\
    \texttt{supply.feedback.gain} & 比例ゲイン & 1.2 \\
    \texttt{supply.feedback.response}\newline \texttt{\_time\_years} & 応答時定数 [yr] & 0.4 \\
    \texttt{supply.feedback.tau\_field} & $\tau$ 評価フィールド (\texttt{tau\_los}) & \texttt{tau\_los} \\
    \texttt{supply.feedback.min\_scale}\newline \texttt{supply.feedback.max\_scale} & スケール係数の上下限 & 1e-6 / 10.0 \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{温度カップリングの設定}
  \label{tab:app_supply_temperature_settings}
  \begin{tabular}{p{0.46\textwidth} p{0.44\textwidth}}
    \hline
    設定キー & 意味 \\
    \hline
    \path{supply.temperature.reference_K} & 基準温度 [K] \\
    \texttt{supply.temperature.exponent} & べき指数 $\alpha$ \\
    \texttt{supply.temperature.floor}\newline \texttt{supply.temperature.cap} & スケール係数の下限・上限 \\
    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{注入パラメータの設定}
  \label{tab:app_supply_injection_settings}
  \begin{tabular}{p{0.40\textwidth} p{0.32\textwidth} p{0.18\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \texttt{supply.injection.mode} & \texttt{min\_bin}\newline \texttt{powerlaw\_bins} & \texttt{powerlaw\_bins} \\
    \texttt{supply.injection.q} & べき指数（衝突カスケード断片） & 3.5 \\
    \texttt{supply.injection.s\_inj}\newline \texttt{\_min}\newline \texttt{supply.injection.s\_inj}\newline \texttt{\_max} & 注入サイズ範囲 [m] & 自動 \\
    \texttt{supply.injection.velocity}\newline \texttt{.mode} & \texttt{inherit} / \texttt{fixed\_ei}\newline \texttt{/ factor} & \texttt{inherit} \\
    \hline
  \end{tabular}
\end{table}

#### B.4 診断（エネルギー簿記）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{エネルギー簿記に関連する設定キー}
  \label{tab:app_energy_settings}
  \begin{tabular}{p{0.36\textwidth} p{0.38\textwidth} l}
	    \hline
	    設定キー & 意味 & 既定値 \\
	    \hline
	    \texttt{dynamics.eps\_restitution} & 反発係数（$f_{ke,\rm frag}$ のデフォルトに使用） & 0.5 \\
	    \texttt{dynamics.f\_ke\_cratering} & 侵食時の非散逸率 & 0.1 \\
    \path{dynamics.f_ke_fragmentation} & 破砕時の非散逸率 & None（$\varepsilon^2$ 使用） \\
	    \texttt{diagnostics.energy}\newline \texttt{\_bookkeeping}\newline \texttt{.stream} & energy 系列/簿記をストリーム出力 & true \\
	    \hline
	  \end{tabular}
		\end{table}

#### B.5 視線幾何（$f_{\rm los}$）

$f_{\rm los}$ は垂直光学厚 $\tau_{\perp}$ から火星視線方向光学厚 $\tau_{\rm los}=f_{\rm los}\tau_{\perp}$ を近似する補正係数である（1節）．実装では次の設定により
\[
f_{\rm los}=
\begin{cases}
\max\!\left(1,\dfrac{{\rm path\_multiplier}}{H/r}\right), & {\rm mode}=\texttt{aspect\_ratio\_factor},\\
1, & {\rm mode}=\texttt{none}
\end{cases}
\]
として与える．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{視線補正係数 $f_{\rm los}$ の設定（\texttt{shielding.los\_geometry}）}
  \label{tab:los_geometry_settings}
  \begin{tabular}{p{0.42\textwidth} p{0.34\textwidth} p{0.16\textwidth}}
    \hline
    設定キー & 意味 & 既定値 \\
    \hline
    \path{shielding.los_geometry.mode} & \texttt{aspect\_ratio}\newline\texttt{\_factor} / \texttt{none} & \texttt{aspect\_ratio}\newline\texttt{\_factor} \\
    \path{shielding.los_geometry.h_over_r} & アスペクト比 $H/r$ & 1.0 \\
    \path{shielding.los_geometry.path_multiplier} & 視線方向の光路長係数 & 1.0 \\
    \hline
  \end{tabular}
\end{table}


---
### 付録 C. 外部入力（テーブル）一覧

<!--
実装(.py): marsdisk/run.py, marsdisk/physics/radiation.py, marsdisk/physics/shielding.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/supply.py, marsdisk/physics/sinks.py, marsdisk/physics/tempdriver.py
-->

本モデルは，物性や放射輸送に関する外部テーブルを読み込み，本文中の式で用いる物理量（$T_M$, $\langle Q_{\rm pr}\rangle$, $\Phi$ など）を与える．論文ではテーブルの数値そのものを列挙せず，役割と参照先を表\ref{tab:app_external_inputs}にまとめる．実行時に採用したテーブルの出典と補間範囲（有効温度域など）は実行ログに保存し，再解析時の基準とする（付録A）．

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{外部入力（テーブル）とモデル内での役割}
  \label{tab:app_external_inputs}
  \begin{tabular}{p{0.22\textwidth} p{0.46\textwidth} p{0.24\textwidth}}
    \hline
    外部入力 & 役割 & 本文参照（代表） \\
    \hline
    火星温度履歴 $T_M(t)$ &
    放射圧（β, $s_{\rm blow}$）・昇華の入力となる温度ドライバ &
    3節 \\
    Planck 平均 $\langle Q_{\rm pr}\rangle$ &
    放射圧効率として β と $s_{\rm blow}$ を決める（灰色体近似は例外） &
    2.1節 \\
    遮蔽係数 $\Phi(\tau_{\rm los})$（本研究では $\Phi=\exp(-\tau_{\rm los})$） &
    有効不透明度 $\kappa_{\rm eff}$ を通じて遮蔽に入る\newline（遮蔽係数はテーブル入力） &
    2.2節 \\
    \hline
  \end{tabular}
\end{table}


---
### 付録 D. 略語索引

<!--
実装(.py): marsdisk/physics/psd.py, marsdisk/physics/surface.py, marsdisk/physics/smol.py, marsdisk/physics/radiation.py, marsdisk/physics/qstar.py, marsdisk/physics/sublimation.py, marsdisk/physics/viscosity.py
-->

略語は次の表にまとめる．

\begin{table}[t]
  \centering
  \caption{略語索引}
  \label{tab:app_abbreviations}
  \begin{tabular}{p{0.18\textwidth} p{0.44\textwidth} p{0.28\textwidth}}
    \hline
    略語 & 日本語 / 英語 & 備考 \\
    \hline
    PSD & 粒径分布 / particle size distribution & サイズビン分布 $n(s)$ \\
    LOS & 視線方向 / line of sight & $\tau_{\rm los}$ に対応 \\
    ODE & 常微分方程式 / ordinary differential equation & 表層 ODE \\
    IMEX & implicit-explicit & IMEX-BDF(1) に使用 \\
    BDF & backward differentiation formula & 一次 BDF \\
    $Q_{\rm pr}$ & 放射圧効率 / radiation pressure efficiency & テーブル入力 \\
    $Q_D^*$ & 破壊閾値 / critical specific energy & 破壊強度 \\
    HKL & Hertz--Knudsen--Langmuir & 昇華フラックス \\
    C5 & 半径方向拡散 / radial viscous diffusion & 1D 拡張 \\
    1D & one-dimensional & 幾何モード \\
    \hline
  \end{tabular}
\end{table}
<!--
document_type: reference
title: 記号表（論文内参照の正）
-->

<!--
実装(.py): marsdisk/schema.py, marsdisk/physics/initfields.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

### 付録 E. 記号表

本論文で用いる記号と，その意味・単位をまとめる．本文中に示す式で用いる記号の定義も，本付録を正とする．主要記号は表\ref{tab:app_symbols_main}と表\ref{tab:app_symbols_main_cont}に示す．

#### E.1 主要記号（本研究のダスト円盤モデル）

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{主要記号表（本研究で用いる記号と単位）}
  \label{tab:app_symbols_main}
  \begin{tabular}{p{0.18\linewidth}p{0.44\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
	    \hline
	    記号 & 意味 & 単位 & 備考 \\
	    \hline
	    $t$ & 時刻 & $\mathrm{s}$ & 解析では年へ換算して表示する場合がある \\
	    $r$ & 半径（代表半径） & $\mathrm{m}$ & 0D では代表値のみを用いる \\
	    $r_{\rm in},r_{\rm out}$ & 計算領域の内端・外端半径 & $\mathrm{m}$ & 環状領域 $[r_{\rm in},r_{\rm out}]$ \\
	    $A$ & 環状領域の面積 & $\mathrm{m^{2}}$ & 式\ref{eq:annulus_area_definition} \\
	    $M_{\rm in}$ & ロッシュ限界内側の内側円盤質量 & $\mathrm{kg}$ & 入力（3節） \\
	    $\Delta M_{\rm in}$ & 遷移期における放射圧起因の不可逆損失（累積） & $\mathrm{kg}$ & $\Delta M_{\rm in}=\int \dot{M}_{\rm out}(t)\,dt$ \\
	    $M_{\rm in}'$ & 更新後の内側円盤質量（長期モデルへ渡す量） & $\mathrm{kg}$ & $M_{\rm in}'=M_{\rm in}(t_0)-\Delta M_{\rm in}$ \\
	    $\Omega$ & ケプラー角速度 & $\mathrm{s^{-1}}$ & 式\ref{eq:omega_definition} \\
	    $v_K$ & ケプラー速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vK_definition} \\
    $s$ & 粒子半径 & $\mathrm{m}$ & PSD の独立変数 \\
	    $n(s)$ & 粒径分布（形状） & -- & 正規化された分布として扱う \\
	    $N_k$ & ビン $k$ の数密度（面数密度） & $\mathrm{m^{-2}}$ & Smol 解法の主状態 \\
    $m_k$ & ビン $k$ の粒子質量 & $\mathrm{kg}$ & 粒径から球形近似で導出 \\
    $Y_{kij}$ & 衝突 $(i,j)$ による破片生成の質量分率（ビン $k$ への配分） & -- & $\sum_k Y_{kij}=1$（式\ref{eq:fragment_yield_normalization}） \\
    $F_k$ & 供給ソース項（サイズビン $k$ への注入率） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:smoluchowski} \\
    $S_k$ & 追加シンクの実効ロス率 & $\mathrm{s^{-1}}$ & 式\ref{eq:smoluchowski} \\
    $\Sigma_{\rm surf}$ & 表層の面密度 & $\mathrm{kg\,m^{-2}}$ & 放射圧・昇華・衝突が作用する層 \\
    $\Sigma_{\rm deep}$ & 深層リザーバ面密度 & $\mathrm{kg\,m^{-2}}$ & 深層ミキシング有効時に追跡 \\
    $\kappa_{\rm surf}$ & 表層の質量不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & PSD から評価 \\
    $\Phi$ & 自遮蔽係数 & -- & 遮蔽有効時に $\kappa_{\rm eff}=\Phi\kappa_{\rm surf}$ \\
    $\kappa_{\rm eff}$ & 有効不透明度 & $\mathrm{m^{2}\,kg^{-1}}$ & 式\ref{eq:kappa_eff_definition} \\
		    $\tau_{\perp}$ & 垂直方向光学的厚さ & -- & 表層衝突寿命の評価に用いる \\
		    $\tau_{\rm los}$ & 火星視線方向光学的厚さ & -- & 遮蔽・停止判定に用いる \\
		    $f_{\rm los}$ & 視線補正係数（$\tau_{\rm los}=f_{\rm los}\tau_{\perp}$） & -- & 1節 \\
		    $\Sigma_{\tau_{\rm los}=1}$ & $\tau_{\rm los}=1$ に対応する表層面密度（幾何学的 proxy） & $\mathrm{kg\,m^{-2}}$ & $\Sigma_{\tau_{\rm los}=1}=(f_{\rm los}\kappa_{\rm surf})^{-1}$ \\
		    $\Sigma_{\tau_{\perp}=1}$ & $\tau_{\perp}=1$ に対応する表層面密度（幾何学的 proxy） & $\mathrm{kg\,m^{-2}}$ & $\Sigma_{\tau_{\perp}=1}=\kappa_{\rm surf}^{-1}$ \\
	    $\Sigma_{\tau=1}$ & $\tau_{\rm eff}\equiv\kappa_{\rm eff}\Sigma_{\rm surf}=1$ に対応する表層面密度（診断量） & $\mathrm{kg\,m^{-2}}$ & 式\ref{eq:sigma_tau1_definition} \\
	    \hline
  \end{tabular}
\end{table}

\begin{table}[t]
  \centering
  \small
  \setlength{\tabcolsep}{4pt}
  \caption{主要記号表（続き）}
  \label{tab:app_symbols_main_cont}
  \begin{tabular}{p{0.18\linewidth}p{0.44\linewidth}p{0.12\linewidth}p{0.18\linewidth}}
	    \hline
	    記号 & 意味 & 単位 & 備考 \\
	    \hline
	    $T_M$ & 火星表面温度 & $\mathrm{K}$ & 放射・昇華の入力 \\
	    $\langle Q_{\rm abs}\rangle$ & 粒子温度評価に用いる有効吸収効率 & -- & 式\ref{eq:grain_temperature_definition} \\
	    $\langle Q_{\rm pr}\rangle$ & Planck 平均放射圧効率 & -- & テーブル入力 \\
	    $\beta$ & 軽さ指標（放射圧/重力） & -- & 式\ref{eq:beta_definition}; $\beta>0.5$ で非束縛 \\
	    $s_{\rm blow}$ & ブローアウト粒径 & $\mathrm{m}$ & 式\ref{eq:s_blow_definition} \\
	    $t_{\rm blow}$ & ブローアウト滞在時間 & $\mathrm{s}$ & 式\ref{eq:t_blow_definition} \\
	    $\dot{\Sigma}_{\rm out}$ & 表層流出（面密度フラックス） & $\mathrm{kg\,m^{-2}\,s^{-1}}$ & 式\ref{eq:surface_outflux} \\
	    $\dot{M}_{\rm out}$ & 円盤全体の質量流出率 & $\mathrm{kg\,s^{-1}}$ & 式\ref{eq:mdot_out_definition}（出力は $\dot{M}_{\rm out}/M_{\rm Mars}$ を記録） \\
	    $M_{\rm loss}$ & 累積損失 & $\mathrm{kg}$ & $\dot{M}_{\rm out}$ 等を積分（出力は $M_{\rm loss}/M_{\rm Mars}$ を記録） \\
	    $C_{ij}$ & 衝突イベント率（単位面積あたり，$N_iN_j$ を含む） & $\mathrm{m^{-2}\,s^{-1}}$ & 式\ref{eq:collision_kernel} \\
	    $v_{ij}$ & 相対速度 & $\mathrm{m\,s^{-1}}$ & 式\ref{eq:vrel_pericenter_definition} \\
	    $e, i$ & 離心率・傾斜角（分散） & -- & 相対速度の評価に用いる \\
	    $c_{\rm eq}$ & 速度分散（平衡値） & $\mathrm{m\,s^{-1}}$ & 本文では扱わない \\
	    $Q_D^*$ & 破壊閾値（比エネルギー） & $\mathrm{J\,kg^{-1}}$ & 式\ref{eq:qdstar_definition} \\
	    \hline
  \end{tabular}
\end{table}
