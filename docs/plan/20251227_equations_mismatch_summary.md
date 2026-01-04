# 目的
現状の「仕様と実装の数式不一致」を、このファイルだけで理解できる形で整理し、修正方針を明確化する。

# 前提
- 対象は 0D 既定経路（`surface.collision_solver="smol"`）の式と周辺ユーティリティ。
- 本書は **外部の人がこの1枚だけ読む**前提で、必要な式・定義をここに明記する。

# 記号メモ（本書内で使う最小限の定義）
- $m_1, m_2$: 衝突体の質量 [kg]
- $M_{\mathrm{tot}} = m_1 + m_2$, $\mu = m_1 m_2 / M_{\mathrm{tot}}$（縮約質量）
- $Q_R = \tfrac{1}{2}\mu v^2 / M_{\mathrm{tot}}$（比衝突エネルギー）
- $Q_{\mathrm{RD}}^{*}$: 破壊閾値（catastrophic disruption threshold）
- $\phi = Q_R / Q_{\mathrm{RD}}^{*}$
- $f_{\mathrm{LR}}$: 最大残留質量分率（0–1）
- $v_K$: ケプラー速度 [m s$^{-1}$]
- $e,i$: 離心率・傾斜（無次元）
- $\Omega$: ケプラー角速度 [s$^{-1}$]
- $\tau$: 光学的厚さ（無次元）
- $\Sigma_{\mathrm{surf}}$: 表層面密度 [kg m$^{-2}$]
- $\kappa_{\mathrm{surf}}$: 表層不透明度 [m$^2$ kg$^{-1}$]
- $\Phi(\tau)$: 自遮蔽係数（0–1）
- $Q_{\mathrm{pr}}$: 放射圧効率（Planck平均）

# 本当の数式ミス（equations 準拠でコードが違う）
## E.033 最大残留分率の分岐式
- 不一致内容: `analysis/equations.md` は piecewise（$\phi<1$ と $\phi\ge1$）だが、コードは全域で線形式＋クリップ。
- 仕様（数式）:
  - $\phi = Q_R / Q_{\mathrm{RD}}^{*}$
  - $\phi < 1$: $f_{\mathrm{LR}} = 1 - 0.5\,\phi$
  - $\phi \ge 1$: $f_{\mathrm{LR}} = 0.5\,\phi^{-1.5}$
- 実装（現状のコード）:
  - $f_{\mathrm{LR}} = \mathrm{clip}\!\left(0.5\,(2 - Q_R/Q_{\mathrm{RD}}^{*}),\,0,\,1\right)$ を **全域**で使用。
- 影響: 高エネルギー側で $f_{\mathrm{LR}}$ が過大評価され、破砕生成量や PSD が歪む可能性。
- 実装位置（内部参照用）:
  - 配列版: `marsdisk/physics/fragments.py`（`largest_remnant_fraction_array`）
  - スカラー版: `marsdisk/physics/fragments.py`（`compute_largest_remnant_mass_fraction_F2`）
- 参考:
  - [@StewartLeinhardt2009_ApJ691_L133], DOI: 10.1088/0004-637X/691/2/L133
  - [@LeinhardtStewart2012_ApJ745_79], DOI: 10.1088/0004-637X/745/1/79
- 対応案:
  1) コード側を piecewise に戻す（equations 準拠）。
  2) もし線形式を採用する意図なら、equations 側を更新して根拠を追記。

## Numba 経路の c_eq フォールバック
- 不一致内容: Numba 実装で `c_eq` 解が失敗した場合 `e_base = e0 * v_k` としており、無次元の $e$ が速度スケールを含んでしまう。
- 仕様（数式）:
  - 固定点反復で $c$ を求める（下の E.021 参照）。
  - `wyatt_eq` では $e = c / v_K$、$i = 0.5\,e$ として使う。
- 実装（code）:
  - Python: 失敗時は `c_eq = e0 * v_k` と置いた後、`e_base = c_eq / v_k` で $e\approx e0$ に戻す。
  - Numba: 失敗時に `e_base = e0 * v_k` としており、$e$ が速度次元になる。
- 影響: Numba/非Numbaで $e,i,H$ が桁違いになり、衝突カーネルや $t_{\mathrm{coll}}$ が不整合になる。
- 実装位置（内部参照用）:
  - Numba: `marsdisk/physics/_numba_kernels.py`（`compute_kernel_e_i_H_numba`）
  - Python: `marsdisk/physics/collisions_smol.py`（`compute_kernel_ei_state`）
- 参考: [@Ohtsuki2002_Icarus155_436], DOI: 10.1006/icar.2001.6741
- 対応案:
  1) Numba 側のフォールバックを Python と同じ次元で統一する。
  2) フォールバックの挙動を仕様化して equations に追記する（必要なら）。

# 仕様差 / ドキュメント不整合（equations 側の修正候補）
## E.021 速度分散 c の単位
- 不一致内容: 式は $\tau$ のみで無次元だが、記述では $c$ を m/s としている。
- 仕様（数式）:
  - 反復式: $\varepsilon_n=\mathrm{clip}(\varepsilon(c_n),0,1-10^{-6})$、
    $c_{n+1}=\sqrt{f_{\mathrm{wake}}\,\tau/\max(1-\varepsilon_n^2,10^{-12})}$、
    $c_{n+1}\leftarrow 0.5(c_{n+1}+c_n)$。
  - 上式には $v_K$ が含まれず、**次元が無次元**になる。
- 実装（現状のコード）:
  - `wyatt_eq` では $e=c/v_K$ を採用しており、$c$ を速度と見なす解釈が前提になっている。
- 影響: $c$ を速度とみなした実装と衝突速度への変換で解釈が揺れる。
- 実装位置（内部参照用）:
  - 反復式: `marsdisk/physics/dynamics.py`（`solve_c_eq`）
  - 使用箇所: `marsdisk/physics/collisions_smol.py`（`compute_kernel_ei_state`）
- 参考: [@Ohtsuki2002_Icarus155_436], DOI: 10.1006/icar.2001.6741
- 対応案:
  1) $c$ を無次元と明記し、$e=c/v_K$ を明文化。
  2) あるいは式に $v_K$ を入れて速度次元の $c$ を定義し直す。

## E.007 surface ODE の Σ_tau1 クリップ
- 不一致内容: equations は `min(..., Σ_{τ=1})` を含むが、実装は surface ODE 内ではクリップしない。
- 仕様（数式）:
  - $\lambda = 1/t_{\mathrm{blow}} + I_{\mathrm{coll}}/t_{\mathrm{coll}} + I_{\mathrm{sink}}/t_{\mathrm{sink}}$
  - $\Sigma^{n+1}=\min\!\left((\Sigma^n+\Delta t\,\dot{\Sigma}_{\mathrm{prod}})/(1+\Delta t\,\lambda),\,\Sigma_{\tau=1}\right)$
- 実装（現状のコード）:
  - `sigma_tau1` は **ログ用途のみ**。`min(., Σ_{τ=1})` のクリップは行わない。
- 影響: 仕様上の「光学的厚さの上限」と実挙動がズレる。
- 実装位置（内部参照用）:
  - `marsdisk/physics/surface.py`（`step_surface_density_S1`）
- 参考:
  - [@Wyatt2008], DOI: 10.1146/annurev.astro.45.051806.110525
  - [@StrubbeChiang2006_ApJ648_652], DOI: 10.1086/505736
- 対応案:
  1) equations を現実装の方針（クリップは上流で扱う）に合わせて修正。
  2) もしくは surface ODE 内にクリップを復活させる。

## E.004 / E.012 Q_pr のフォールバック挙動
- 不一致内容: equations は「テーブル未ロード時は $Q_{pr}=1$ にフォールバック」とあるが、実装はテーブル未ロード時に例外を投げる。
- 仕様（数式）:
  - $\langle Q_{\mathrm{pr}}\rangle =
    \begin{cases}
      Q_{\mathrm{pr}} & \text{明示値がある場合}\\
      \mathcal{I}(s, T_M) & \text{テーブルがある場合}\\
      1 & \text{それ以外（灰色体近似）}
    \end{cases}$
- 実装（現状のコード）:
  - テーブル未初期化の場合は `RuntimeError` を投げる。灰色体フォールバックなし。
- 影響: ドキュメントと実行時エラー条件が不一致。
- 実装位置（内部参照用）:
  - `marsdisk/physics/radiation.py`（`_resolve_qpr`）
- 参考:
  - [@Burns1979_Icarus40_1], DOI: 10.1016/0019-1035(79)90050-2
  - [@StrubbeChiang2006_ApJ648_652], DOI: 10.1086/505736
- 対応案:
  1) equations を「テーブル必須」に修正。
  2) あるいはコードに $Q_{pr}=1$ フォールバックを追加。

# 式と一致
## 破片分配テンソル $Y_{kij}$（質量分布）
- 一致内容: 破片質量分布 $dM/ds \propto s^{-\alpha_{\mathrm{frag}}}$ のビン積分と、最大残留分の扱い。
- 仕様（数式）:
  - ビン重み: $w_k \propto \int_{s_{k-}}^{s_{k+}} s^{-\alpha_{\mathrm{frag}}}\,ds$ を正規化。
  - 分配: $Y_{kij} = f_{\mathrm{LR}}\delta_{k,k_{\mathrm{LR}}} + (1-f_{\mathrm{LR}})\,w_k$（$k \le k_{\mathrm{LR}}$ のビンへ配分）。
- 実装（現状のコード）:
  - ビン端点を用いた冪積分で `weights_table` を作成し、$k_{\mathrm{LR}}$ へ $f_{\mathrm{LR}}$ を置き、残余を $k\le k_{\mathrm{LR}}$ に配分。
- 確認結果: 仕様と一致。
- 参考:
  - [@Krivov2006_AA455_509], DOI: 10.1051/0004-6361:20077709
  - [@Birnstiel2011_AA525_A11], DOI: 10.1051/0004-6361/201015228

## 供給パワー則分配（$dN/ds$）
- 一致内容: 供給を $dN/ds \propto s^{-q}$ でビンに分配する重み付けと正規化。
- 仕様（数式）:
  - $w_k \propto \int_{s_{k-}}^{s_{k+}} s^{-q}\,ds$（注入区間との重なりで積分）。
  - $F_k = w_k\,\dot{M}_{\mathrm{supply}} / \sum_j (w_j m_j)$。
  - $w_k \le 0$ の場合は最小ビン集中注入にフォールバック。
- 実装（現状のコード）:
  - 注入範囲との重なりを評価し、冪積分で重みを計算、質量正規化して $F_k$ を構成。
- 確認結果: 仕様と一致。
- 参考:
  - [@Birnstiel2011_AA525_A11], DOI: 10.1051/0004-6361/201015228
  - [@Krivov2006_AA455_509], DOI: 10.1051/0004-6361:20077709

## 衝突カーネル $C_{ij}$
- 一致内容: $n\sigma v$ 形式のカーネルとガウス厚さ補正。
- 仕様（数式）:
  - $C_{ij} = \dfrac{N_i N_j}{1+\delta_{ij}}\,\dfrac{\pi(s_i+s_j)^2 v_{ij}}{\sqrt{2\pi}\,H_{ij}}$、
    $H_{ij}=\sqrt{H_i^2+H_j^2}$。
- 実装（現状のコード）:
  - 対角成分は 1/2 で二重計数を回避し、上式どおりに計算。
- 確認結果: 仕様と一致。
- 参考: [@Krivov2006_AA455_509], DOI: 10.1051/0004-6361:20077709

## 比衝突エネルギー $Q_R$
- 一致内容: $Q_R$ の定義（縮約質量を用いる）。
- 仕様（数式）:
  - $Q_R = \tfrac{1}{2}\mu v^2 / M_{\mathrm{tot}}$、$\mu = m_1 m_2 / M_{\mathrm{tot}}$。
- 実装（現状のコード）:
  - `compute_q_r_F2` / `q_r_array` が同式で評価。
- 確認結果: 仕様と一致。
- 参考: [@StewartLeinhardt2009_ApJ691_L133], DOI: 10.1088/0004-637X/691/2/L133

## サブブローアウト生成率
- 一致内容: 上三角和による生成率の定義。
- 仕様（数式）:
  - $\dot{m}_{<a_{\mathrm{blow}}} = \sum_{i\le j} C_{ij}\,m^{(<a_{\mathrm{blow}})}_{ij}$。
- 実装（現状のコード）:
  - 上三角インデックスで積算（Numba/NumPy とも同じ）。
- 確認結果: 仕様と一致。
- 参考: [@Krivov2006_AA455_509], DOI: 10.1051/0004-6361:20077709
