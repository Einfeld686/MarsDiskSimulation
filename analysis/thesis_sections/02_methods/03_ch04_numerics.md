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
### 4.1 衝突カスケードと破片生成

衝突カスケードは小粒子供給の主因であり，PSD の形状と供給率を同時に決める．統計的な衝突解法は Smoluchowski 方程式の枠組み [@Krivov2006_AA455_509] を基礎に置き，破砕強度は LS12 補間 [@LeinhardtStewart2012_ApJ745_79] を採用し，係数はフォルステライト想定で与える．

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

$F_k$ は表層への質量供給（第3章）をサイズビンへ配分したソース項であり，面数密度 $N_k$ に対する注入率（$\mathrm{m^{-2}\,s^{-1}}$）として与える．
$S_k$ は昇華・ブローアウトなど追加シンクをまとめた実効ロス率（$\mathrm{s^{-1}}$）であり，$-S_k N_k$ の一次ロスとして扱う．

#### 4.1.1 衝突カーネル

nσv 型カーネルを用い，相対速度は Rayleigh 分布を仮定して導出する（[@LissauerStewart1993_PP3; @WetherillStewart1993_Icarus106_190; @Ohtsuki2002_Icarus155_436; @ImazBlanco2023_MNRAS522_6150; @IdaMakino1992_Icarus96_107]）．カーネルの定義は式\ref{eq:collision_kernel}に示す．

\begin{equation}
\label{eq:collision_kernel}
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,
\frac{\pi\,(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}},
\qquad H_{ij} = \sqrt{H_i^{2}+H_j^{2}}
\end{equation}

相対速度 $v_{ij}$ は局所の $v_K$ と，離心率・傾斜角の分散 $(e,i)$ から式\ref{eq:vij_definition}で評価する．

\begin{equation}
\label{eq:vij_definition}
v_{ij}=v_{K}\,\sqrt{1.25\,e^{2}+i^{2}}
\end{equation}

破壊閾値 $Q_D^*$ は LS12 補間に従い，モデル内では次式の形で表す．

\begin{equation}
\label{eq:qdstar_definition}
Q_{D}^{*}(s,\rho,v) = Q_{\mathrm{str}}(v) + Q_{\mathrm{grav}}(v)\,S(v)
\end{equation}

- 破壊閾値 $Q_D^*$: [@LeinhardtStewart2012_ApJ745_79] 補間（式\ref{eq:qdstar_definition}）
- 速度分散: せん断加熱と減衰の釣り合いから $c_{\rm eq}$ を固定点反復で求め，相対速度に反映する（[@Ohtsuki2002_Icarus155_436]）
- 速度外挿: 重力項のみ LS09 型 $v^{-3\mu+2}$ で拡張（[@StewartLeinhardt2009_ApJ691_L133; @Jutzi2010_Icarus207_54]）
- ここでの $\mu$ は衝突速度外挿（LS09）の係数であり，供給式で用いる無次元係数（第3章）とは別物として扱う．

衝突カーネルはサイズビン対ごとに衝突率 $C_{ij}$ を評価し，衝突ロス項と破片生成項を形成する．動力学パラメータ（$e, i$）は表層状態と供給の速度条件を反映して更新され，$C_{ij}$ の評価に反映される．

S9 の衝突更新では，$C_{ij}$ から各ビンの衝突寿命 $t_{\rm coll}$ と loss/gain を算定し，破片分布テンソル $Y$ に基づいて生成項を配分する．$t_{\rm coll}$ の最小値は $\Delta t$ の上限制御に用いられ，ビンごとの質量収支が質量検査で追跡される．破片生成は PSD 下限のビン境界条件と整合させ，供給注入と同一のビン系で質量保存を保証する．

#### 4.1.2 衝突レジーム分類

衝突は **最大残存率 $F_{LF}$** に基づいて2つのレジームに分類する．レジームの条件と処理は次の表にまとめる．

\begin{table}[t]
  \centering
  \caption{衝突レジームの分類と処理}
  \label{tab:collision_regimes}
  \begin{tabular}{p{0.28\textwidth} p{0.2\textwidth} p{0.42\textwidth}}
    \hline
    レジーム & 条件 & 処理 \\
    \hline
    侵食（cratering） & $F_{LF} > 0.5$ & ターゲット残存，クレーター破片生成 \\
    壊滅的破砕（fragmentation） & $F_{LF} \le 0.5$ & 完全破壊，破片分布 $g(m) \propto m^{-\eta}$ \\
    \hline
  \end{tabular}
\end{table}

- Thébault et al. (2003) に基づく侵食モデル（[@Thebault2003_AA408_775]）
- [@Krivov2006_AA455_509] に基づく壊滅的破砕モデル
- 破砕境界と最大残存率の分岐式は [@StewartLeinhardt2009_ApJ691_L133; @LeinhardtStewart2012_ApJ745_79] に従う
- 破片分布はビン内積分で質量保存を満たすように正規化し，供給・破砕由来の面密度が一貫するように設計する．

破砕生成物はフラグメント分布テンソル $Y$ を通じて各ビンに再配分され，Smoluchowski 解法の gain 項として更新される．侵食レジームでは質量が大粒径側に残存し，小粒径への供給は限定的となる．

#### 4.1.3 エネルギー簿記

衝突エネルギーの診断は，デブリ円盤の衝突カスケード研究で用いられる散逸・残存の整理に倣って行う（[@Thebault2003_AA408_775]）．各ステップで相対運動エネルギー $E_{\rm rel}$ と，そのうち熱化して散逸した成分 $E_{\rm diss}$，残留した成分 $E_{\rm retained}$ を評価し，衝突速度場の妥当性と数値安定性の確認に用いる．散逸は係数 $f_{ke}$ を用いて

\[
E_{\rm diss} = (1 - f_{ke})\,E_{\rm rel}
\]

と定義する．エネルギー簿記は診断専用であり，時間発展のフィードバックには用いない．保存項目の詳細は付録A，関連パラメータは付録B（表\ref{tab:energy_settings}）にまとめる．

---
### 4.2 数値解法と停止条件

#### 4.2.1 IMEX-BDF(1)

Smoluchowski 衝突カスケードの時間積分には IMEX（implicit-explicit）と BDF(1)（backward differentiation formula）の一次組合せを採用する（[@Krivov2006_AA455_509]）．状態ベクトルはサイズビン $k$ ごとの数密度（または面密度）で表現し，衝突ゲイン・ロスと表層再供給・シンクを同時に組み込む．剛性の強いロス項を陰的に扱うことで安定性を確保し，生成・供給・表層流出は陽的に更新する．

IMEX の分割は次の通りである．

- **損失項（陰的）**: 衝突ロス，ブローアウト損失（$s \le s_{\rm blow}$），追加シンク（代表時間 $t_{\rm sink}$）．
- **生成項（陽的）**: 衝突による破片生成と表層再供給（ソース項 $F_k$）．

外側の結合ステップ幅を $\Delta t$ とし，温度・遮蔽・供給・相判定などは同じ $\Delta t$ で更新する．IMEX ソルバ内部では $dt_{\rm eff}\le\Delta t$ を用い，負の数密度や質量誤差が生じる場合には $dt_{\rm eff}$ を縮小して再評価する．時間刻みは代表衝突時間とブローアウト滞在時間を解像するよう制約し，表\ref{tab:validation_criteria}の収束・安定性確認に基づき，外側の結合ステップ幅を $\Delta t\le 0.1\min_k t_{{\rm coll},k}$ とした．質量検査は式\ref{eq:mass_budget_definition}で定義し，許容誤差は同表に従い $0.5\\%$ とした．質量検査ログと主要診断量の保存は付録Aにまとめる．

質量検査は，更新前後のビン総面密度と，供給（$\dot{\Sigma}_{\rm prod}$）および追加シンク由来の損失を比較して定義する．

\begin{equation}
\label{eq:mass_budget_definition}
\begin{aligned}
 \Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta\Sigma &= \Sigma^{n+1} + \Delta t\,\dot{\Sigma}_{\mathrm{extra}} - \left(\Sigma^{n} + \Delta t\,\dot{\Sigma}_{\mathrm{prod}}^{(<s_{\mathrm{blow}})}\right),\\
 \epsilon_{\mathrm{mass}} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}

IMEX-BDF(1) は剛性ロス項で負の数密度が生じるのを防ぐため，ロス項を陰的に扱う設計とする．$N_k<0$ が検出された場合は $dt_{\rm eff}$ を半減して再評価し，許容誤差内の質量検査を満たした $dt_{\rm eff}$ が採用される．陽的に扱う生成項は衝突の破片生成と供給注入に限定し，質量保存は質量検査で逐次確認する．

S9 の数値更新では，衝突ロス・ブローアウト・追加シンクを陰的側に集約し，衝突生成・供給注入を陽的に与える．$\Delta t$ は $t_{\rm coll}$ と $t_{\rm blow}$ の双方を解像するよう制約し，必要に応じて内部ステップ幅 $dt_{\rm eff}$ を用いた再評価で安定性と質量保存を担保する．

#### 4.2.2 1D（半径方向拡散）挿入位置・境界条件・$\Delta t$ 制約

標準設定では半径方向を $N_r=32$ セルに分割し，各セルで局所進化を計算する．半径方向の粘性拡散は標準では無効とし，必要時のみ演算子分割で追加する．粘性拡散を有効化する場合は，各ステップの局所更新後に半径方向の拡散方程式を解く．

- **境界条件**: 内外端ともにゼロフラックス（Neumann）境界を採用する．
- **$\Delta t$ 制約**: 粘性拡散は $\theta$ 法（既定 $\theta=0.5$ の Crank–Nicolson）で半陰的に解くため，追加の安定制約は課さない．時間刻みは衝突時間とブローアウト時間に基づく制約に従う．
- **有効化条件**: 粘性拡散を含めるかどうかは感度試験として切り替え，設定は付録Bにまとめる．

粘性拡散は半径方向の面密度拡散を解くため，1D 実行のセル間結合を担当する．数値的には三重対角系の解として実装され，境界条件により質量フラックスの流出入を抑制する．

---
#### 4.2.3 初期化・終了条件・チェックポイント

##### 4.2.3.1 初期 $\tau=1$ スケーリング

初期 PSD は，指定した総質量または光学的厚さ（代表として $\tau_0=1$）になるように正規化して与える．$\tau_0=1$ スケーリングでは，火星視線方向の目標光学的厚さ $\tau_{\rm los}=\tau_0$ から $\Sigma_{\rm surf,0}$ を定め，PSD を一様にスケールする（[@StrubbeChiang2006_ApJ648_652]）．初期条件と採用値は再現実行ログに保存する（付録A）．関連パラメータは付録B（表\ref{tab:init_tau1_settings}）にまとめる．

##### 4.2.3.2 温度停止 (Temperature Stop)

停止条件は (i) 温度停止（$T_M(t)\le T_{\rm stop}$ で終了），(ii) 固定の解析期間 $t_{\rm end}$，(iii) 固定公転数のいずれかで与える．併用時の優先順位は「温度停止 → 公転数 → 年数」とし，未指定の場合は解析期間 2 年を既定とする（[@Hyodo2018_ApJ860_150]）．温度停止では冷却達成後にマージン時間を追加でき，探索の上限時間も設定できる（設定は付録B）．

##### 4.2.3.3 チェックポイント (Segmented Run)

長時間実行をセグメント化し，一定間隔で中間状態（チェックポイント）を保存して再開可能にする．保存間隔は代表値として約 30 日（0.083 年）を用い，直近の複数個のみ保持してディスク使用量を制限する（設定は付録B）．

---
#### 4.3 小括

本節では，衝突カスケードの支配式（式\ref{eq:smoluchowski}）と，それを安定に時間積分する数値解法（IMEX-BDF(1)），ならびに時間刻み制御と停止条件を定義した．これらの設定により，負の数密度を回避しつつ質量保存を監視し，表\ref{tab:validation_criteria}の基準に基づいて収束性と安定性を担保する．次節では，出力定義と検証基準を整理し，本論文で提示する結果が合格基準を満たすことを述べる．
