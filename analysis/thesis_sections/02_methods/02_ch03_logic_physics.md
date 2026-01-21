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

先行研究は，Phobos/Deimos を形成しうる衝突条件として，Vesta-Ceres 級の衝突体による斜め衝突が必要であり，成功例が衝突角 30-60$^{\circ}$ に分布することを示している（[@CanupSalmon2018_SciAdv4_eaar6887]）．衝突前の火星が無視できない自転を持ち，その自転軸が衝突で与えられる角運動量ベクトルと一致しない場合，生成円盤の平均軌道面は火星赤道面から傾いた非赤道円盤になりうるため，粒子の軌道傾斜角（inclination, $i$）には平均値とばらつきが生じる（[@Hyodo2017b_ApJ851_122]）．さらに火星の扁平率 $J_2$ による節点歳差を考えると，$a\sim2-10\,R_{\rm Mars}$，$e\sim0.5-0.9$ の範囲では歳差の時間スケールが 1-100 年程度であり，傾斜角に依存する見積もりが与えられている（[@Hyodo2017b_ApJ851_122]）．したがって本研究が対象とする数年-10年の時間範囲では，衝突直後に生じた傾斜角のばらつきが残存し，その鉛直方向の運動が内部の物質を光が比較的通りやすい表層へ運び続ける過程が起こりうると考え，本研究ではこれを表層再供給としてパラメータ化して取り込む．具体的には，光学的厚さ $\tau\simeq1$ に対応する初期表層面密度 $\Sigma_{\tau=1,0}(r)$ を質量スケール，局所公転周期 $T_{\rm orb}(r)$（$T_{\rm orb}=2\pi/\Omega$）を時間スケールとして，1 公転あたりに $\Sigma_{\tau=1,0}$ の $f_{\rm orb}$ を補充する規格化を式\ref{eq:supply_target_orbit}で与える．

\begin{equation}
\label{eq:supply_target_orbit}
\dot{\Sigma}_{\rm target}(r)=\mu_{\rm orb} f_{\rm orb}\,\frac{\Sigma_{\tau=1,0}(r)}{T_{\rm orb}(r)}
\end{equation}

ここで $\mu_{\rm orb}$ は強度の不確かさを吸収する無次元パラメータである．以下では $\Sigma_{\tau=1,0}$ を $\Sigma_{\rm ref}$ として扱い，目標供給率 $\dot{\Sigma}_{\rm target}$ の基準面密度として用いる．

供給の基礎率は式\ref{eq:prod_rate_definition}で定義する（[@WyattClarkeBooth2011_CeMDA111_1]）．

\begin{equation}
\label{eq:prod_rate_definition}
\dot{\Sigma}_{\mathrm{prod}}(t,r) = \max\!\left(\epsilon_{\mathrm{mix}}\;R_{\mathrm{base}}(t,r),\,0\right)
\end{equation}

供給率の時間依存形は定常値・べき乗・外部テーブル・区分定義などから選び，温度依存・$\tau$ フィードバック・有限リザーバを組み合わせて非定常性を表現する（設定は付録Bを参照）．ここでの $\mu_{\rm orb}$ は供給強度の不確かさを吸収するパラメータであり，衝突速度外挿で用いる $\mu$ と混同しないよう区別する．

本研究の基準ケースでは定常供給を採り，参照光学的厚さ $\mu_{\rm ref}$（標準 $\mu_{\rm ref}=1$）に対応する基準面密度を式\ref{eq:supply_sigma_ref_mu}で定義する（$\Phi$ は遮蔽係数，遮蔽無効時は $\Phi=1$）．式\ref{eq:supply_target_orbit}の $\Sigma_{\tau=1,0}$ はこの基準面密度と同一視する．

\begin{equation}
\label{eq:supply_sigma_ref_mu}
\begin{aligned}
\Sigma_{\rm ref} &= \frac{\mu_{\rm ref}}{\kappa_{\rm eff,ref}\,\mathrm{los\_factor}},\\
\kappa_{\rm eff,ref} &= \Phi(\mu_{\rm ref})\,\kappa_{\rm surf}.
\end{aligned}
\end{equation}

混合係数 $\epsilon_{\rm mix}$ は供給の有効度を表し，感度掃引で代表値を変化させて影響を評価する（付録A）．

供給は「名目供給→混合（$\epsilon_{\mathrm{mix}}$）→温度スケール→$\tau$ フィードバック→有限リザーバ→深層/表層への配分」の順に評価される．供給が深層へ迂回した場合でも，表層面密度と PSD の更新は同一タイムステップ内で整合的に行われる．中間量の保存と再解析手順は付録Aにまとめる．

#### 3.1.1 フィードバック制御 (Supply Feedback)

$\tau$ 目標に追従する比例制御により，供給率をスケールさせることができる．フィードバックは供給ゲートの**上流**で適用し，$\tau_{\rm stop}$ 超過時は停止判定を優先する．設定項目は付録B（表\ref{tab:supply_feedback_settings}）にまとめる．

#### 3.1.2 温度カップリング (Supply Temperature)

火星温度に連動した供給スケーリングを有効化する場合は，基準温度 $T_{\rm ref}$ に対して $(T/T_{\rm ref})^{\alpha}$ のべき乗でスケールするか，外部テーブルから補間する．設定項目は付録B（表\ref{tab:supply_temperature_settings}）にまとめる．

#### 3.1.3 リザーバと深層ミキシング

有限質量リザーバを追跡し，供給を一旦深層に蓄積したうえで，ミキシング時間（公転数換算）で表層へ放出するモデルを用意する．$\tau$ が過大になった場合は停止判定で扱う．リザーバ枯渇時は供給をゼロにするか，残量に応じて漸減させるかを選ぶ．設定項目は付録Bにまとめる．

#### 3.1.4 注入パラメータ

注入パラメータは付録B（表\ref{tab:supply_injection_settings}）にまとめる．

注入モードは PSD 形状の境界条件として働くため，供給率とビン解像度の整合が重要である．感度試験では注入指数 $q$ と最小注入サイズを変化させ，ブローアウト近傍の wavy 構造や質量収支への影響を評価する．
