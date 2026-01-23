<!-- TEX_EXCLUDE_START -->
### （資料）式一覧（内部参照用：PDF除外）

このファイルは `analysis/equations.md` の式番号 (E.###) を一覧表示するための作業用メモであり，論文PDFには含めない．本文中では式は各節に掲示し，記号定義は付録 E（記号表）を参照する．

---
### F.1 軌道力学と時間尺度

ケプラー運動の基本式に従う\citep{Burns1979_Icarus40_1}．

\begin{equation}
\tag{E.001}
\label{eq:E001}
v_K(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r}}
\end{equation}

\begin{equation}
\tag{E.002}
\label{eq:E002}
\Omega(r)=\sqrt{\frac{G\,M_{\rm Mars}}{r^{3}}}
\end{equation}

\begin{equation}
\tag{E.007}
\label{eq:E007}
t_{\rm blow}=\frac{1}{\Omega}
\end{equation}

---
### F.2 粒径境界とブローアウト

放射圧比 $\beta$ とブローアウト境界の定義は古典的整理に従う\citep{Burns1979_Icarus40_1,StrubbeChiang2006_ApJ648_652}．$s_{\min,\rm eff}$ のクリップは実装上の境界条件である．

\begin{equation}
\tag{E.008}
\label{eq:E008}
s_{\min,\rm eff}=\max\!\left(s_{\min,\rm cfg},\,s_{\rm blow,eff}\right)
\end{equation}

\begin{equation}
\tag{E.013}
\label{eq:E013}
\beta = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle}{4\,G\,M_{\rm Mars}\,c\,\rho\,s}
\end{equation}

\begin{equation}
\tag{E.014}
\label{eq:E014}
s_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_M^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle}{2\,G\,M_{\rm Mars}\,c\,\rho}
\end{equation}

---
### F.3 遮蔽と光学的厚さ

自遮蔽係数 $\Phi$ と有効不透明度の取り扱いは放射輸送近似（delta-Eddington 等）に基づく\citep{Joseph1976_JAS33_2452,HansenTravis1974_SSR16_527}．

\begin{equation}
\tag{E.015}
\label{eq:E015}
\kappa_{\rm eff}=\Phi(\tau)\,\kappa_{\rm surf}
\end{equation}

\begin{equation}
\tag{E.016}
\label{eq:E016}
\Sigma_{\tau_{\rm eff}=1} =
\begin{cases}
 \kappa_{\rm eff}^{-1}, & \kappa_{\rm eff} > 0,\\
 \infty, & \kappa_{\rm eff} \le 0.
\end{cases}
\end{equation}

\begin{equation}
\tag{E.017}
\label{eq:E017}
\Phi=\Phi(\tau,\omega_0,g)
\end{equation}

---
### F.4 表層流出（ブローアウト）

ブローアウト滞在時間スケール $t_{\rm blow}\sim1/\Omega$ と流出評価はデブリ円盤の標準的近似に基づく\citep{StrubbeChiang2006_ApJ648_652,Wyatt2008}．

\begin{equation}
\tag{E.009}
\label{eq:E009}
\dot{\Sigma}_{\rm out} = \frac{\Sigma_{\rm surf}}{t_{\rm blow}}
\end{equation}

---
### F.5 Smoluchowski 方程式と質量収支

衝突カスケードの Smoluchowski 記述と質量収支検査はデブリ円盤モデルの実装例に従う\citep{Krivov2006_AA455_509,Thebault2003_AA408_775,Birnstiel2011_AA525_A11,Wyatt2008}．$\epsilon_{\rm mass}$ の形は実装上の定義である．

\begin{equation}
\tag{E.010}
\label{eq:E010}
\dot{N}_k = \sum_{i\le j} C_{ij}\,\frac{m_i+m_j}{m_k}\,Y_{kij} - \left(\sum_j C_{kj} + C_{kk}\right) + F_k - S_k N_k
\end{equation}

\begin{equation}
\tag{E.011}
\label{eq:E011}
\begin{aligned}
 \Sigma^{n} &= \sum_k m_k N_k^{n}, & \Sigma^{n+1} &= \sum_k m_k N_k^{n+1},\\
 \Delta\Sigma &= \Sigma^{n+1} + \Delta t\,\dot{\Sigma}_{\rm extra} - \left(\Sigma^{n} + \Delta t\,\dot{\Sigma}_{\rm prod}^{(<s_{\rm blow})}\right),\\
 \epsilon_{\rm mass} &= \frac{|\Delta\Sigma|}{\Sigma^{n}}.
\end{aligned}
\end{equation}

---
### F.6 衝突（速度・カーネル・破砕強度）

相対速度近似は低離心率・低傾斜のレイリー分布仮定に基づく\citep{LissauerStewart1993_PP3,WetherillStewart1993_Icarus106_190,Ohtsuki2002_Icarus155_436,IdaMakino1992_Icarus96_107,ImazBlanco2023_MNRAS522_6150}．衝突カーネルは薄い円盤の $n\sigma v$ 形式\citep{Krivov2006_AA455_509}，破壊閾値 $Q_D^*$ は BA99/LS12 の係数補間に基づく\citep{BenzAsphaug1999_Icarus142_5,LeinhardtStewart2012_ApJ745_79,StewartLeinhardt2009_ApJ691_L133}．

\begin{equation}
\tag{E.020}
\label{eq:E020}
v_{ij}=v_K\,\sqrt{1.25\,e^{2}+i^{2}}
\end{equation}

\begin{equation}
\tag{E.021}
\label{eq:E021}
\begin{aligned}
\varepsilon_n &= {\rm clip}\!\left(\varepsilon(c_n),\,0,\,1-10^{-6}\right),\\
c_{n+1} &= \sqrt{\frac{f_{\rm wake}\,\tau}{\max(1-\varepsilon_n^{2},\,10^{-12})}},\\
c_{n+1} &\leftarrow \tfrac12\left(c_{n+1} + c_n\right)
\end{aligned}
\end{equation}

\begin{equation}
\tag{E.024}
\label{eq:E024}
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,
\frac{\pi\,(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}},
\qquad H_{ij} = \sqrt{H_i^{2}+H_j^{2}}
\end{equation}

\begin{equation}
\tag{E.026}
\label{eq:E026}
Q_{D}^{*}(s,\rho,v) = Q_{\rm str}(v) + Q_{\rm grav}(v)\,S(v)
\end{equation}

---
### F.7 表層再供給（supply）

供給率の定義はデブリ円盤の簡略注入モデルに沿う\citep{Wyatt2008}．$\mu$ から $R_{\rm base}$ への変換（E.027a）は定義に基づく補助式である．

\begin{equation}
\tag{E.027}
\label{eq:E027}
\dot{\Sigma}_{\rm in}(t,r) = \max\!\left(\epsilon_{\rm mix}\;R_{\rm base}(t,r),\,0\right)
\end{equation}

\begin{equation}
\tag{E.027a}
\label{eq:E027a}
R_{\rm base} = \frac{\mu\,\Sigma_{\tau_{\rm eff}=1}}{\epsilon_{\rm mix}\,t_{\rm blow}}
\end{equation}

---
### F.8 昇華（HKL）と飽和蒸気圧

HKL フラックスと飽和蒸気圧の取り扱いは昇華モデルの標準形に従う\citep{VanLieshoutMinDominik2014_AA572_A76,Kubaschewski1974_Book,VisscherFegley2013_ApJL767_L12,Pignatale2018_ApJ853_118}．

\begin{equation}
\tag{E.018}
\label{eq:E018}
J(T) =
\begin{cases}
 \alpha_{\rm evap}\max\!\bigl(P_{\rm sat}(T) - P_{\rm gas},\,0\bigr)
 \sqrt{\dfrac{\mu}{2\pi R T}}, &
 \text{if HKL enabled},\\[10pt]
 \exp\!\left(\dfrac{T - T_{\rm sub}}{\max(dT, 1)}\right), & \text{otherwise.}
\end{cases}
\end{equation}

\begin{equation}
\tag{E.036}
\label{eq:E036}
P_{\rm sat}(T) =
\begin{cases}
 10^{A - B/T}, & \text{if clausius},\\[6pt]
  10^{{\rm PCHIP}_{\log_{10}P}(T)}, & \text{if tabulated}.
\end{cases}
\end{equation}
<!-- TEX_EXCLUDE_END -->
