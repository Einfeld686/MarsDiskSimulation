## 3. 表層への質量供給

<!--
実装(.py): marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/physics/supply.py, marsdisk/physics/phase.py, marsdisk/physics/shielding.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @CanupSalmon2018_SciAdv4_eaar6887 -> paper/references/CanupSalmon2018_SciAdv4_eaar6887.pdf | 用途: 衝突条件と衝突角の範囲
- @Hyodo2017b_ApJ851_122 -> paper/references/Hyodo2017b_ApJ851_122.pdf | 用途: 非赤道円盤とJ2歳差スケール
- @WyattClarkeBooth2011_CeMDA111_1 -> paper/references/WyattClarkeBooth2011_CeMDA111_1.pdf | 用途: 供給率のパラメータ化
<!-- TEX_EXCLUDE_END -->

---
### 3.1 表層再供給と輸送

表層再供給（supply）は表層への面密度生成率として与え，サイズ分布と深層輸送を通じて PSD に注入する．ここでの表層再供給は外側からの流入を精密に表すものではなく，深部↔表層の入れ替わりを粗く表現するためのパラメータ化である．定常値・べき乗・テーブル・区分定義の各モードを用意し，温度・$\tau$ フィードバック・有限リザーバを組み合わせて非定常性を表現する（[@WyattClarkeBooth2011_CeMDA111_1]）．

先行研究は，Phobos/Deimos を形成しうる衝突条件として，Vesta-Ceres 級の衝突体による斜め衝突が必要であり，成功例が衝突角 30-60$^{\circ}$ に分布することを示している（[@CanupSalmon2018_SciAdv4_eaar6887]）．衝突前の火星が無視できない自転を持ち，その自転軸が衝突で与えられる角運動量ベクトルと一致しない場合，生成円盤の平均軌道面は火星赤道面から傾いた非赤道円盤になりうるため，粒子の軌道傾斜角（inclination, $i$）には平均値とばらつきが生じる（[@Hyodo2017b_ApJ851_122]）．さらに火星の扁平率 $J_2$ による節点歳差を考えると，$a\sim2-10\,R_{\rm Mars}$，$e\sim0.5-0.9$ の範囲では歳差の時間スケールが 1-100 年程度であり，傾斜角に依存する見積もりが与えられている（[@Hyodo2017b_ApJ851_122]）．したがって本研究が対象とする数年-10年の時間範囲では，衝突直後に生じた傾斜角のばらつきが残存し，その鉛直方向の運動が内部の物質を光が比較的通りやすい表層へ運び続ける過程が起こりうると考え，本研究ではこれを表層再供給としてパラメータ化して取り込む．具体的には，火星視線方向の光学的厚さ $\tau_{\rm los}\simeq1$ に対応する初期表層面密度 $\Sigma_{\tau_{\rm los}=1,0}(r)$ を質量スケール，局所公転周期 $T_{\rm orb}(r)$（$T_{\rm orb}=2\pi/\Omega$）を時間スケールとして，1 公転あたりに $\Sigma_{\tau_{\rm los}=1,0}$ の $f_{\rm orb}$ を補充する規格化を式\ref{eq:supply_target_orbit}で与える．

\begin{equation}
\label{eq:supply_target_orbit}
\dot{\Sigma}_{\rm target}(r)=\mu_{\rm orb} f_{\rm orb}\,\frac{\Sigma_{\tau_{\rm los}=1,0}(r)}{T_{\rm orb}(r)}
\end{equation}

ここで $\mu_{\rm orb}$ は強度の不確かさを吸収する無次元パラメータである．以下では $\Sigma_{\tau_{\rm los}=1,0}$ を $\Sigma_{\rm ref}$ として扱い，目標供給率 $\dot{\Sigma}_{\rm target}$ の基準面密度として用いる．

供給の基礎率は式\ref{eq:prod_rate_definition}で定義する（[@WyattClarkeBooth2011_CeMDA111_1]）．

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\mathrm{prod}}(t,r) = \max\!\left(\epsilon_{\mathrm{mix}}\;R_{\mathrm{base}}(t,r),\,0\right)
\end{equation}

供給率の時間依存形は定常値・べき乗・外部テーブル・区分定義などから選び，温度依存・$\tau$ フィードバック・有限リザーバを組み合わせて非定常性を表現する．ここでの $\mu_{\rm orb}$ は供給強度の不確かさを吸収するパラメータであり，衝突速度外挿で用いる $\mu$ と混同しないよう区別する．

本研究の基準ケースでは定常供給を採り，参照光学的厚さ $\mu_{\rm ref}$（標準 $\mu_{\rm ref}=1$）に対応する基準面密度を式\ref{eq:supply_sigma_ref_mu}で定義する（$\Phi$ は遮蔽係数，遮蔽無効時は $\Phi=1$）．式\ref{eq:supply_target_orbit}の $\Sigma_{\tau_{\rm los}=1,0}$ はこの基準面密度と同一視する．

\begin{equation}
\label{eq:supply_sigma_ref_mu}
\begin{aligned}
\Sigma_{\rm ref} &= \frac{\mu_{\rm ref}}{\kappa_{\rm eff,ref}\,f_{\rm los}},\\
\kappa_{\rm eff,ref} &= \Phi(\mu_{\rm ref})\,\kappa_{\rm surf}.
\end{aligned}
\end{equation}

混合係数 $\epsilon_{\rm mix}$ は供給の有効度を表し，感度掃引で代表値を変化させて影響を評価する（付録A）．

供給の計算は，名目供給率 $R_{\rm base}(t,r)$（供給モードで与える）から出発し，混合係数・温度依存・$\tau$ フィードバック・有限リザーバ（任意）を順に反映した後，供給ゲートにより適用可否を決め，深層バッファ（任意）を経由して PSD の離散ビンへ注入する，という固定された順序で行う．すなわち，候補となる表層への面密度生成率 $\dot{\Sigma}_{\rm cand}(t,r)$ を
\begin{equation}
\dot{\Sigma}_{\rm cand}= f_{\rm res}\;f_{\tau}\;f_{T}\;\max\!\left(\epsilon_{\mathrm{mix}}R_{\mathrm{base}},\,0\right)
\end{equation}
で定義し，実際に表層へ適用する供給率は
\begin{equation}
\dot{\Sigma}_{\rm in}=g_{\rm sup}\,\dot{\Sigma}_{\rm cand}
\end{equation}
で与える．ここで $f_T$ は温度倍率，$f_{\tau}$ は $\tau$ 目標に基づくフィードバック倍率，$f_{\rm res}$ は有限リザーバによるクリップ因子（リザーバ無効時は $f_{\rm res}=1$），$g_{\rm sup}\in\{0,1\}$ は供給ゲートである．供給ゲートは数値の立ち上げと相状態の整合のために導入し，本研究では（i）初期ステップでは外部供給を適用しない，（ii）相状態が固体でないステップでは外部供給を停止する，という規則で $g_{\rm sup}$ を定める．

また，$\tau_{\rm stop}$ を超える光学的厚さは本研究の想定（表層が「光が比較的通りやすい」状態）を逸脱するため，$\tau_{\rm los}>\tau_{\rm stop}(1+\mathrm{tol})$ を満たした時点でシミュレーションを早期終了する（停止判定）．ここで $\mathrm{tol}$ は停止判定に用いる相対許容であり，停止判定は相状態が固体のステップに対して適用する．供給が深層へ迂回した場合でも，表層面密度と PSD の更新は同一タイムステップ内で整合的に行われる．中間量の保存と再解析手順は付録Aにまとめる．

#### 3.1.1 フィードバック制御 (Supply Feedback)

本研究では，表層の火星線視光学的厚さ $\tau_{\rm los}(t,r)$ を目標値 $\tau_{\rm tar}$ に近づけるため，供給率に無次元倍率 $f_{\tau}(t,r)$ を掛けて調整する．$\tau_{\rm los}$ は当該ステップの表層面密度 $\Sigma_{\rm surf}$ と，PSD から得た表層不透明度 $\kappa_{\rm surf}$ を用いて
\begin{equation}
\tau_{\rm los}=\kappa_{\rm surf}\,\Sigma_{\rm surf}\,\mathrm{los\_factor}
\end{equation}
で評価する（$\mathrm{los\_factor}$ は鉛直方向から火星線視方向への換算係数）．

フィードバックは比例制御の誤差
\begin{equation}
e_{\tau}\equiv\frac{\tau_{\rm tar}-\tau_{\rm los}}{\max(\tau_{\rm tar},\epsilon)}
\end{equation}
に基づき，供給倍率を各ステップで更新する．ここで $\epsilon$ はゼロ除算回避のための微小量である．ステップ幅を $\Delta t$，応答時間を $t_{\rm resp}$，比例ゲインを $k_{\tau}$ とすると，実装では
\begin{equation}
f_{\tau}\leftarrow\mathrm{clip}\!\left(f_{\tau}\left[1+k_{\tau}\frac{\Delta t}{t_{\rm resp}}\,e_{\tau}\right],\,f_{\tau,\min},\,f_{\tau,\max}\right)
\end{equation}
で更新し，更新後の $f_{\tau}$ を当該ステップの供給率（温度スケール後）に乗じる．ここで $\mathrm{clip}(x,a,b)\equiv\min(\max(x,a),b)$ は上下限クリップを表す．$\tau_{\rm los}$ が非有限の場合は $f_{\tau}$ を更新しない．$f_{\tau}$ の初期値は $f_{\tau}(t{=}0)=f_{\tau,0}$ として与える．

#### 3.1.2 温度カップリング (Supply Temperature)

供給率が火星温度 $T_{\rm M}(t)$ に連動すると仮定する場合，温度倍率 $f_T(t)$ を導入し，混合後の供給率に乗じる．解析式によるスケーリング（scale）では
\begin{equation}
f_T(t)=\mathrm{clip}\!\left(f_{T,\rm ref}\left(\frac{T_{\rm M}(t)}{T_{\rm ref}}\right)^{\alpha_T},\,f_{T,\min},\,f_{T,\max}\right)
\end{equation}
とし，$T_{\rm ref}$ は基準温度，$\alpha_T$ は温度感度指数，$f_{T,\rm ref}$ は $T_{\rm ref}$ における倍率，$f_{T,\min},f_{T,\max}$ は上下限である．

外部テーブル（table）を用いる場合は，$T_{\rm M}$ をキーとして値 $y(T_{\rm M})$ を線形補間で読み出す．テーブル値の解釈には，(i) $y$ を倍率として扱い，上式の $\mathrm{clip}$ と同様に上下限を適用して $f_T$ を与える（value\_kind=scale），(ii) $y$ を供給率そのもの（面密度生成率）として用い，$R_{\rm base}$ と $\epsilon_{\rm mix}$ による名目供給を上書きする（value\_kind=rate），の2通りを区別する．

#### 3.1.3 リザーバと深層ミキシング

外部供給が有限の総量を持つ場合，供給リザーバの残量 $M_{\rm res}(t)$ を追跡し，1ステップで供給可能な最大面密度生成率を
\begin{equation}
\dot{\Sigma}_{\max}=\frac{M_{\rm res}(t)}{A\,\Delta t}
\end{equation}
（$A$ は対象領域の面積）として，$\dot{\Sigma}_{\rm cand}$ を $\dot{\Sigma}_{\max}$ でクリップする．このとき $M_{\rm res}$ は
\begin{equation}
M_{\rm res}(t{+}\Delta t)=\max\!\left(M_{\rm res}(t)-\dot{\Sigma}_{\rm in}(t)\,A\,\Delta t,\,0\right)
\end{equation}
で更新する．リザーバ枯渇近傍の扱いとして，(i) クリップのみで枯渇時に供給が停止する方式（hard\_stop），(ii) 残量比が所定の閾値を下回ったとき $\dot{\Sigma}_{\rm cand}$ を残量比に比例して漸減させる方式（taper），のいずれかを選ぶ．

さらに，深層↔表層の交換を有限の混合時間で表すため，深層バッファ（面密度）$\Sigma_{\rm deep}(t,r)$ を導入する．混合時間は公転数換算で $t_{\rm mix}(r)=N_{\rm mix}T_{\rm orb}(r)$ として与え，深層から表層へのフラックスは
\begin{equation}
\dot{\Sigma}_{\rm deep\to surf}=\frac{\Sigma_{\rm deep}}{t_{\rm mix}}
\end{equation}
で近似する．実装では，供給を表層へ直接注入する（direct）か，一旦すべて深層へ迂回してから $t_{\rm mix}$ で放出する（deep\_mixing）かを選べる．また，$\Sigma_{\tau_{\rm los}=1}$ に基づく表層の余裕（headroom）で深層$\to$表層フラックスを制限する設定も用意するが，$\tau$ に基づく停止判定（$\tau_{\rm stop}$）を有効化した基準ケースでは，二重の制限を避けるため headroom 制限を用いない．

#### 3.1.4 注入パラメータ

表層へ適用された供給率 $\dot{\Sigma}_{\rm in}(t,r)$ は，PSD（粒径分布）の離散ビンに対する質量注入項として配分する．サイズビンの中心 $s_k$ と粒子質量 $m_k$ を用い，ビン $k$ への数密度注入源 $F_k$（単位時間あたりの粒子数）は
\begin{equation}
\label{eq:supply_injection_definition}
F_k=\frac{\dot{\Sigma}_{\rm in}\,w_k}{m_k},\qquad \sum_k m_k F_k=\dot{\Sigma}_{\rm in}
\end{equation}
となるよう，非負の重み $w_k$ を定める．ここで $m_k$ は実装上はビン中心に対応する代表質量として評価する．

注入モード（injection mode）は $w_k$ の与え方を指定するもので，本研究では次を用意する．

- min\_bin: 有効最小サイズ $s_{\min,\rm eff}$ 以上で最小のビン $k_\ast$ に全質量を注入する（$w_k=\delta_{k k_\ast}$）．
- powerlaw\_bins: ある範囲 $[s_{\rm inj,min},s_{\rm inj,max}]$ に対して $dN/ds\propto s^{-q}$ を仮定し，ビン幅との重なりに応じて $w_k$ を与える．下限は $s_{\min,\rm eff}$ でクリップし，総注入質量が $\dot{\Sigma}_{\rm in}$ に一致するよう正規化する．
- initial\_psd: 初期 PSD の各ビン質量重みに比例して注入する．

powerlaw\_bins の場合，ビン境界を $[s_{k-},s_{k+}]$ とし，下限 $s_{\rm floor}\equiv\max(s_{\min,\rm eff},s_{\rm inj,min})$，上限 $s_{\rm ceil}\equiv s_{\rm inj,max}$ を用いると，実装上は
\begin{equation}
\label{eq:supply_injection_powerlaw_bins}
\tilde{w}_k=\int_{\max(s_{k-},s_{\rm floor})}^{\min(s_{k+},s_{\rm ceil})} s^{-q}\,ds,\qquad
F_k=\frac{\dot{\Sigma}_{\rm in}\,\tilde{w}_k}{\sum_j m_j\tilde{w}_j}
\end{equation}
の形で $F_k$ を定め，$\sum_k m_k F_k=\dot{\Sigma}_{\rm in}$ を満たすようにする．ここで $s_{\min,\rm eff}$ は当該ステップで有効な PSD の下限サイズ（ブローアウト半径や床モデルにより決まる）である．

注入モードは PSD 形状の境界条件として働くため，供給率とビン解像度（特に $s_{\min,\rm eff}$ 近傍）の整合が結果に直接影響する．感度試験では注入指数 $q$ や注入サイズ範囲を変化させ，ブローアウト近傍の wavy 構造や質量収支への影響を評価する．

本節で用いた各パラメータ（$\tau_{\rm tar},k_{\tau},t_{\rm resp},T_{\rm ref},\alpha_T,N_{\rm mix},q,s_{\rm inj,min},s_{\rm inj,max}$ など）と対応する設定項目は，付録Bの表\ref{tab:supply_feedback_settings}〜表\ref{tab:supply_injection_settings}に一覧する．
