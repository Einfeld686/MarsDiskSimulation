## 4. 微細化シミュレーション

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/smol.py, marsdisk/physics/collisions_smol.py, marsdisk/physics/surface.py, marsdisk/physics/viscosity.py, marsdisk/io/checkpoint.py, marsdisk/io/streaming.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @Hyodo2018_ApJ860_150 -> paper/references/Hyodo2018_ApJ860_150.pdf | 用途: 温度停止条件の基準
- @Krivov2006_AA455_509 -> paper/references/Krivov2006_AA455_509.pdf | 用途: IMEX-BDF1での衝突カスケード解法
- @StrubbeChiang2006_ApJ648_652 -> paper/references/StrubbeChiang2006_ApJ648_652.pdf | 用途: 初期τ=1スケーリング/表層t_coll尺度
<!-- TEX_EXCLUDE_END -->

---
本章の目的は，衝突カスケードによる微細化（fragmentation）を Smoluchowski 方程式で定式化し，安定な数値積分法と停止条件を与えることである．ここでは，まず衝突カスケードと破片生成モデル（4.1）を示し，次に IMEX-BDF(1) による時間積分と時間刻み制御，ならびに初期化と停止条件（4.2）を整理する．

### 4.1 衝突カスケードと破片生成

本節の目的は，衝突カスケードと破片生成のモデルを定義し，Smoluchowski 方程式（式\ref{eq:smoluchowski}）の右辺を閉じることである．ここでは，まず衝突イベント率 $C_{ij}$ と衝突結果モデル（最大残存率 $F_{LF}$，破片分布 $Y_{kij}$）を導入し，供給注入項 $F_k$ と一次シンク $S_k$ を含む支配式を与える．

統計的な衝突解法は Smoluchowski 方程式の枠組み [@Krivov2006_AA455_509] を基礎に置き，破砕強度は LS12 補間 [@LeinhardtStewart2012_ApJ745_79] を採用し，係数はフォルステライト想定で与える．

ここでは，2.1.1節で定義した PSD の離散表現 $N_k(t)$ とサイズビンを状態変数とし，供給注入項 $F_k$（式\ref{eq:supply_injection_definition}）と一次シンク $S_k$（ブローアウト・昇華など；2.2.2節）を外部入力として受け取る．その上で本節では，衝突イベント率 $C_{ij}$（4.1.1節）と衝突結果モデル（最大残存率 $F_{LF}$ と破片分布 $Y_{kij}$；4.1.2節）を定義し，Smoluchowski 方程式（式\ref{eq:smoluchowski}）の右辺を閉じる．数値積分は4.2節で与える．

主要な PSD の時間発展は式\ref{eq:smoluchowski}で与える．

\begin{equation}
\label{eq:smoluchowski}
\dot{N}_k = \sum_{i\le j} C_{ij}\,\frac{m_i+m_j}{m_k}\,Y_{kij} - \left(\sum_j C_{kj} + C_{kk}\right) + F_k - S_k N_k
\end{equation}

右辺第1項が破片生成，第2項が衝突ロス，$F_k$ が供給ソース，$S_k$ が追加シンク（昇華・ガス抗力など）を表す．

ここで $Y_{kij}$ は，衝突 $(i,j)$ で失われた質量 $(m_i+m_j)$ がサイズビン $k$ に配分される質量分率（破片生成テンソル）であり，
\begin{equation}
\label{eq:fragment_yield_normalization}
\sum_k Y_{kij}=1
\end{equation}
を満たすように正規化する．このとき第1項は，衝突率 $C_{ij}$ に対し，ビン $k$ に入る質量 $(m_i+m_j)Y_{kij}$ を粒子数へ換算した生成項を与える．

$F_k$ は 3.1.4節の式\ref{eq:supply_injection_definition}で定義した供給注入源であり，面数密度 $N_k$ に対する注入率（$\mathrm{m^{-2}\,s^{-1}}$）として与える．
$S_k$ はブローアウト一次シンク $S_{{\rm blow},k}$（2.2.2節）と，昇華・ガス抗力などの追加シンクを合算した実効ロス率（$\mathrm{s^{-1}}$）であり，$-S_k N_k$ の一次ロスとして扱う．

#### 4.1.1 衝突カーネル

nσv 型カーネルを用い，相対速度は Rayleigh 分布を仮定して導出する（[@LissauerStewart1993_PP3; @WetherillStewart1993_Icarus106_190; @Ohtsuki2002_Icarus155_436; @ImazBlanco2023_MNRAS522_6150; @IdaMakino1992_Icarus96_107]）．衝突イベント率 $C_{ij}$ を式\ref{eq:collision_kernel}で定義する．

\begin{equation}
\label{eq:collision_kernel}
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,
\frac{\pi\,(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}},
\qquad H_{ij} = \sqrt{H_i^{2}+H_j^{2}}
\end{equation}

式\ref{eq:collision_kernel}の $C_{ij}$ は $N_iN_j$ を含む衝突イベント率（単位 $\mathrm{m^{-2}\,s^{-1}}$）として定義する．この定義では衝突ロス項は $(\sum_j C_{kj}+C_{kk})$ で与えられ（$\sum_j$ は $j=k$ を含む全ビン和），$+C_{kk}$ は対角成分の $1/2$ 因子と自衝突で粒子 $k$ が2個失われることを整合させる補正である．ビン $k$ の衝突寿命は
\begin{equation}
\label{eq:t_coll_definition}
t_{{\rm coll},k}=\left(\frac{\sum_j C_{kj}+C_{kk}}{N_k}\right)^{-1}
\end{equation}
で定義する．

スケールハイト $H_i$ は，傾斜角 $i$ と代表半径 $r$ を用いて $H_i\propto ir$ とする近似を標準とし，感度試験として $H/r$ を固定する近似も用いる．

相対速度 $v_{ij}$ は離心率 $e$ と局所の $v_K$ から与える．本研究の基準ケースでは高離心率の衝突を想定し，近日点近傍での接近を近似して
\begin{equation}
\label{eq:vrel_pericenter_definition}
v_{ij}=v_{K}\,\sqrt{\frac{1+e}{1-e}}
\end{equation}
を用いる．参考として，低離心率・低傾斜角の近似では

\begin{equation}
\label{eq:vij_definition}
v_{ij}=v_{K}\,\sqrt{1.25\,e^{2}+i^{2}}
\end{equation}
を用いる（[@Ohtsuki2002_Icarus155_436]）．

破壊閾値 $Q_D^*$ は BA99 のサイズ則を基礎に，LS12 の速度補間で扱う（[@BenzAsphaug1999_Icarus142_5; @LeinhardtStewart2012_ApJ745_79]）．本研究では参照速度ごとの係数テーブル（付録A）を用いて

\begin{equation}
\label{eq:qdstar_definition}
Q_{D}^{*}(s,\rho,v)=Q_s(v)\,s^{-a_s(v)}+B(v)\,\rho\,s^{b_g(v)}
\end{equation}

として評価する．速度がテーブル範囲外の場合は重力項のみ LS09 型 $v^{-3\mu_{\rm LS}+2}$（$\mu_{\rm LS}$ は速度外挿の指数）で外挿し，強度項は境界値に固定する（[@StewartLeinhardt2009_ApJ691_L133; @Jutzi2010_Icarus207_54]）．衝突速度場 $(e,i)$ は基準計算では設定値として与え，感度試験として Ohtsuki 型の平衡速度分散 $c_{\rm eq}$ を固定点反復で求め，$e=c_{\rm eq}/v_K$，$i=0.5e$ として相対速度へ反映する（[@Ohtsuki2002_Icarus155_436]）．

本研究では衝突対 $(i,j)$ に対し $s_{\rm ref}=\max(s_i,s_j)$ を代表サイズとして $Q_D^*(s_{\rm ref},\rho,v_{ij})$ を与え，次節の $F_{LF}$ と $Y_{kij}$ を定める．

#### 4.1.2 衝突レジーム分類

衝突結果は最大残存体の質量分率（largest remnant fraction）$F_{LF}$ を用いて整理する．衝突体 $(i,j)$ の総質量 $m_i+m_j$ と reduced mass $\mu_{\rm red}$ を用いると，比衝突エネルギー（specific impact energy）は
\begin{equation}
\label{eq:qr_definition}
Q_{R}=\frac{1}{2}\frac{\mu_{\rm red}v_{ij}^{2}}{m_i+m_j},\qquad \mu_{\rm red}=\frac{m_i m_j}{m_i+m_j}
\end{equation}
で与えられる（[@LeinhardtStewart2012_ApJ745_79]）．$\phi\equiv Q_R/Q_D^*$ とおくと，LS12 の近似に従い最大残存率は
\begin{equation}
\label{eq:flf_ls12}
F_{LF}(\phi)=
\begin{cases}
1-\frac{1}{2}\phi & (\phi<\phi_t)\\
f_{\rm sc}\left(\frac{\phi}{\phi_t}\right)^{\eta} & (\phi\ge \phi_t)
\end{cases}
\end{equation}
とする（$\phi_t=1.8$，$f_{\rm sc}=0.1$，$\eta=-1.5$）．本研究では $F_{LF}>0.5$ を侵食（cratering），$F_{LF}\le 0.5$ を壊滅的破砕（fragmentation）として整理する．

\begin{table}[t]
  \centering
  \caption{衝突レジームの分類と処理}
  \label{tab:collision_regimes}
  \begin{tabular}{p{0.28\textwidth} p{0.2\textwidth} p{0.42\textwidth}}
    \hline
    レジーム & 条件 & 特徴 \\
    \hline
    侵食（cratering） & $F_{LF} > 0.5$ & 最大残存体が支配的（$M_{\rm LR}=F_{LF}(m_i+m_j)$） \\
    壊滅的破砕（fragmentation） & $F_{LF} \le 0.5$ & 残余質量が支配的（$1-F_{LF}$ が大） \\
    \hline
  \end{tabular}
\end{table}

破片生成テンソル $Y_{kij}$ は，最大残存体を単一ビンへ置き，残余質量を power-law で小粒径側へ配分することで構成する（[@Krivov2006_AA455_509]）．最大残存体の質量
\[
M_{\rm LR}=F_{LF}(m_i+m_j)
\]
から半径
\[
s_{\rm LR}=\left(\frac{3M_{\rm LR}}{4\pi\rho}\right)^{1/3}
\]
を求め，$s_{\rm LR}$ を含むサイズビンを $k_{\rm LR}$ とする．残余の質量分率 $(1-F_{LF})$ は $dM/ds\propto s^{-\alpha_{\rm frag}}$ を仮定し，ビン境界 $[s_{k-},s_{k+}]$ に対する積分で
\begin{equation}
\label{eq:fragment_weights}
w^{\rm frag}_k(k_{\rm LR})=\frac{\int_{s_{k-}}^{s_{k+}} s^{-\alpha_{\rm frag}}\,ds}{\sum_{\ell\le k_{\rm LR}}\int_{s_{\ell-}}^{s_{\ell+}} s^{-\alpha_{\rm frag}}\,ds}
\end{equation}
を定義する（$k\le k_{\rm LR}$，それ以外は $w^{\rm frag}_k=0$）．したがって
\begin{equation}
\label{eq:fragment_tensor_definition}
Y_{kij}=F_{LF}\delta_{k k_{\rm LR}}+(1-F_{LF})\,w^{\rm frag}_k(k_{\rm LR})
\end{equation}
となり，式\ref{eq:fragment_yield_normalization}の正規化を満たす．破片配分指数 $\alpha_{\rm frag}$ は既定値 $\alpha_{\rm frag}=3.5$ とし，感度試験で変化させる（設定は付録B）．なお，$s\le s_{\rm blow}$ の非束縛領域に配分された質量は，ブローアウト一次シンク $S_{{\rm blow},k}$ により除去される（2.2.2節）．

以上の $Y_{kij}$ により，衝突で失われた質量 $(m_i+m_j)$ のうち $Y_{kij}$ の割合がビン $k$ に再配分され，式\ref{eq:smoluchowski}の gain 項が与えられる．

#### 4.1.3 エネルギー簿記

衝突エネルギーの診断は，デブリ円盤の衝突カスケード研究で用いられる散逸・残存の整理に倣って行う（[@Thebault2003_AA408_775]）．各ステップで相対運動エネルギー $E_{\rm rel}$ と，そのうち熱化して散逸した成分 $E_{\rm diss}$，残留した成分 $E_{\rm retained}$ を評価し，衝突速度場の妥当性と数値安定性の確認に用いる．散逸は係数 $f_{ke}$ を用いて

\[
E_{\rm diss} = (1 - f_{ke})\,E_{\rm rel}
\]

と定義する．エネルギー簿記は診断専用であり，時間発展のフィードバックには用いない．保存項目の詳細は付録A，関連パラメータは付録B（表\ref{tab:app_energy_settings}）にまとめる．

以上により，本節では衝突イベント率 $C_{ij}$ と破片生成テンソル $Y_{kij}$ を定義し，式\ref{eq:smoluchowski}の生成・ロス項を閉じた．次節では，この支配式を安定に時間積分する数値解法と停止条件を示す．

---
### 4.2 数値解法と停止条件

本節の目的は，Smoluchowski 方程式の数値積分法と時間刻み制御，および 1D 拡散項の扱いと停止条件を整理することである．ここでは，まず IMEX-BDF(1) を導入し，次に（任意の）半径方向拡散，初期化，停止条件，チェックポイントをまとめる．

#### 4.2.1 IMEX-BDF(1)

Smoluchowski 衝突カスケードの時間積分には IMEX（implicit-explicit）と BDF(1)（backward differentiation formula）の一次組合せを採用する（[@Krivov2006_AA455_509]）．状態ベクトルはサイズビン $k$ ごとの数面密度 $N_k$ で表現する．本研究の実装では，剛性の強い衝突ロス（式\ref{eq:smoluchowski}の第2項）のみを陰的に扱い，衝突による破片生成（第1項），供給注入 $F_k$，および一次シンク $-S_kN_k$（ブローアウト・昇華などを含む）は陽的に評価する．この分割により，各ビン $k$ の更新は
\begin{equation}
\label{eq:imex_bdf1_update}
N_k^{n+1}=\frac{N_k^{n}+dt_{\rm eff}\left(G_k^{n}+F_k^{n}-S_k^{n}N_k^{n}\right)}{1+dt_{\rm eff}/t_{{\rm coll},k}^{n}}
\end{equation}
と書ける．ここで $G_k^n$ は式\ref{eq:smoluchowski}の破片生成項を表し，$t_{{\rm coll},k}^{n}$ は式\ref{eq:t_coll_definition}を $t=t^n$ で評価した値である．

外側の結合ステップ幅を $\Delta t$ とし，温度・遮蔽・供給・相判定などは同じ $\Delta t$ で更新する．IMEX ソルバ内部では $dt_{\rm eff}\le\Delta t$ を用い，まず $dt_{\rm eff}=\min(\Delta t,\,0.1\min_k t_{{\rm coll},k}^{n})$ を与える．負の数面密度や質量誤差が生じる場合には $dt_{\rm eff}$ を縮小して再評価する．質量検査は式\ref{eq:mass_budget_definition}で定義し，許容誤差は表\ref{tab:validation_criteria}に従い $0.5\\%$ とした．質量検査ログと主要診断量の保存は付録Aにまとめる．

質量検査は，更新前後のビン総面密度と，供給（$\dot{\Sigma}_{\rm prod}$）および追加シンク由来の損失を比較して定義する．

\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
 \Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta\Sigma &= \Sigma^{n+1} + \Delta t\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + \Delta t\,\dot{\Sigma}_{\rm prod}^{(<s_{\rm blow})}\right),\\
 \epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}

IMEX-BDF(1) は剛性ロス項で負の数密度が生じるのを防ぐため，ロス項を陰的に扱う設計とする．$N_k<0$ が検出された場合は $dt_{\rm eff}$ を半減して再評価し，許容誤差内の質量検査を満たした $dt_{\rm eff}$ が採用される．陽的に扱う生成項は衝突の破片生成と供給注入に限定し，質量保存は質量検査で逐次確認する．

数値更新では，衝突ロスの剛性を陰的に抑えつつ，ブローアウト・追加シンクは陽的に適用する．$\Delta t$ は $\min_k t_{{\rm coll},k}$ と $t_{\rm blow}$ の双方を解像するよう制約し，必要に応じて内部ステップ幅 $dt_{\rm eff}$ を用いた再評価で安定性と質量保存を担保する．

#### 4.2.2 1D（半径方向拡散）挿入位置・境界条件・$\Delta t$ 制約

標準設定では半径方向を $N_r=32$ セルに分割し，各セルで局所進化を計算する．本研究の解析窓は最大 2 年と短く，主題は表層の微細化（衝突）と放射圧起因の質量損失であるため，本論文で提示する結果では半径方向のセル間結合（粘性拡散・輸送）は扱わず，1D は独立環として解く．したがって本研究の $\Delta t$ 制約は，衝突時間とブローアウト時間に基づく条件（4.2.1節）に従う．

半径方向輸送（粘性拡散）を感度試験として導入する場合は，拡散方程式と粘性係数 $\nu(r)$ の具体形を長期モデル側の仮定として与える必要があるため，本論文では将来拡張として位置づける．

---
#### 4.2.3 初期化・終了条件・チェックポイント

##### 4.2.3.1 初期 $\tau=1$ スケーリング

初期 PSD は，指定した総質量または光学的厚さ（代表として $\tau_0=1$）になるように正規化して与える．$\tau_0=1$ スケーリングでは，火星視線方向の目標光学的厚さ $\tau_{\rm los}=\tau_0$ から $\Sigma_{\rm surf,0}$ を定め，PSD を一様にスケールする（[@StrubbeChiang2006_ApJ648_652]）．初期条件と採用値は再現実行ログに保存する（付録A）．関連パラメータは付録B（表\ref{tab:app_init_tau1_settings}）にまとめる．

##### 4.2.3.2 温度停止 (Temperature Stop)

停止条件は (i) 温度停止（$T_M(t)\le T_{\rm stop}$ で終了），(ii) 固定の解析期間 $t_{\rm end}$，(iii) 固定公転数のいずれかで与える．併用時の優先順位は「温度停止 → 公転数 → 年数」とし，未指定の場合は解析期間 2 年を既定とする（[@Hyodo2018_ApJ860_150]）．温度停止では冷却達成後にマージン時間を追加でき，探索の上限時間も設定できる（設定は付録B）．

##### 4.2.3.3 チェックポイント (Segmented Run)

長時間実行をセグメント化し，一定間隔で中間状態（チェックポイント）を保存して再開可能にする．保存間隔は代表値として約 30 日（0.083 年）を用い，直近の複数個のみ保持してディスク使用量を制限する（設定は付録B）．

以上により，本節では時間積分法と時間刻み制御，ならびに初期化と停止条件を整理した．次節では，本章の要点を小括としてまとめる．

---
#### 4.3 小括

本節では，衝突カスケードの支配式（式\ref{eq:smoluchowski}）と，それを安定に時間積分する数値解法（IMEX-BDF(1)），ならびに時間刻み制御と停止条件を定義した．これらの設定により，負の数密度を回避しつつ質量保存を監視し，表\ref{tab:validation_criteria}の基準に基づいて収束性と安定性を担保する．次節では，出力定義と検証基準を整理し，本論文で提示する結果が合格基準を満たすことを述べる．
