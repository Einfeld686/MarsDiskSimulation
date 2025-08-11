目的 火星ロッシュ限界内の高密度ダスト円盤を対象に、
* 内部（破砕のみSmoluchowski）で生成されるblow‑out未満の小粒子供給（式：C1–C3, P1, F1–F2, D1–D2）と、
* 表層（剥ぎ取り）での放射圧による剥離・流出（式：R1–R3, S0–S1）、 を2年間カップリングして**$\dot M_{\rm out}(t)$ と $M_{\rm loss}$を定量化するシミュレーションを、新規リポジトリ構造で実装してください。先行研究の式を明示採用し、必要拡張（赤外光源・光学的厚さ・非定常PSD）以外は新式を導入しない**でください。
完成条件（必須の動作）
1. CLI: python -m marsdisk.run --config configs/base.yml で**0D（半径無次元）**が完走。
2. 出力:
    * 時系列 out/series/*.parquet：$\dot{\Sigma}^{(<a_{\rm blow})}{\rm prod}(t)$, $\dot M{\rm out}(t)$, 主要スカラー。
    * 集計 out/summary.json：2年間の $M_{\rm loss}$ と感度掃引の表。
    * 検証 out/checks/mass_budget.csv：質量保存（C4）のログ（|誤差| < 0.5%）。
3. ユニットテスト（pytest）
    * Wyattの衝突寿命スケーリング（$t_{\rm coll}!\approx!T_{\rm orb}/(4\pi\tau)$）のオーダー一致
    * Blow‑out即時消滅による**“wavy” PSDの定性的再現**
    * IMEX（loss陰・gain陽）で安定、$\Delta t\le 0.1\min t_{{\rm coll},k}$ で収束
4. YAMLで物理スイッチ（昇華・ガス抗力・自遮蔽倍率・wake係数など）を外出し。
技術選定と依存
* Python 3.11+, numpy, scipy, numba(任意), pydantic, ruamel.yaml, pandas, pyarrow, xarray(任意), matplotlib(検証用プロット)
* Mie平均$\langle Q_{\rm pr}\rangle$はテーブル読み込みを基本（CSV/NPZ）。ライブラリ（例：miepython）があれば生成ユーティリティも用意。
* 多層RTの自遮蔽係数$\Phi(\tau,\omega_0,g)$もテーブル入力＋双線形補間をデフォルト。
リポジトリ構成
marsdisk/
  configs/
    base.yml
    sweep_example.yml
  marsdisk/
    __init__.py
    constants.py
    grid.py                  # 0D/1Dラッパ、Ω(r), vK(r)
    io/
      __init__.py
      writer.py              # parquet/json出力
      tables.py              # Mie/Qpr, Phi テーブル I/O
    physics/
      radiation.py           # R1–R3: Q_pr 平均, β, a_blow
      shielding.py           # S0: Φ(τ,ω0,g) 適用とΣ_τ=1クリップ
      dynamics.py            # D1–D2: 速度分散の自己調整 c_eq
      qstar.py               # F1: Q_D*(s), LS12補間
      fragments.py           # F2 + 破片分布（α, 最小size境界）
      psd.py                 # P1 + 3スロープ + "wavy"補正
      collide.py             # C1–C2: C_ij, 生成フラックス
      smol.py                # C3–C4: IMEX-BDF(1)実装, 質量検査
      surface.py             # S1: 表層ODE, 剥ぎ取り率
      sinks.py               # 昇華・ガス抗力など追加シンク
      viscosity.py           # C5(任意): 半径1D拡散(演算子分割)
    run.py                   # 全体オーケストレータ/CLI
    validate.py              # 検証・可視化スクリプト
    schema.py                # pydantic: 設定スキーマ
  tests/
    test_scalings.py
    test_mass_conservation.py
    test_surface_outflux.py
  out/   # 生成物
  README.md
  pyproject.toml / requirements.txt
数値仕様（最小要件）
* サイズビン：対数30–60（デフォルト40）。範囲 $s\in[10^{-6},3]$ m
* 時間積分：IMEX-BDF(1)（loss陰, gain陽, S_k陽）。必要ならBDF2も実装可。
* Blow‑out滞在時間：$t_{\rm blow}=1/\Omega$（デフォルト・感度スイープ可）
* PSD下限：$s_{\min}(t)=\max(a_{\rm blow}, s_{\rm sub}(T))$
* 自遮蔽：$\Sigma_{\rm surf}\to\min(\Sigma_{\rm surf},,\Sigma_{\tau=1}=1/\kappa_{\rm surf}^{\rm eff})$
* 乱流速度：$c\to c_{\rm eq}(\tau,\epsilon)$（Ohtsuki型）を固定点反復で解く
* 0Dを先に完成 → 任意で1D半径拡張（C5）をスイッチ実装
出力に最低限含めるカラム
* time, dt, tau, a_blow, s_min, kappa, Qpr_mean, beta_at_smin
* Sigma_surf, Sigma_tau1, outflux_surface, t_blow
* prod_subblow_area_rate (=\dot{Σ}^{(<a_blow)}_{prod})
* M_out_dot, M_loss_cum
* mass_total_bins, mass_lost_by_blowout, mass_lost_by_sinks
検証（ログ）
* 式(C4)に基づく質量差分を毎ステップ記録（%）
* Wyattスケールの $t_{\rm coll}$ 推定とモデル内 $t_{\rm coll}$ の比
* “wavy”の指標（隣接ビンの偏差ジグザグ度）
