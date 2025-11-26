# フェーズ3：火星放射圧ブローアウト監査

## A1. ブローアウト信号経路
- **放射入力→β/`a_blow` 解決**  
  `run_zero_d` で Mars 由来の温度ドライバと ⟨Q_pr⟩ テーブルを読み込み、`_resolve_blowout` で `radiation.blowout_radius` を反復しながら `a_blow` と `beta` を確定する。[marsdisk/run.py:599-681] のブロックは `radiation.qpr_lookup` / `radiation.beta` / `grid.omega_kepler` を結び付け、`chi_blow_eff`→`t_blow` を決定する。[marsdisk/run.py:812-831]
- **PSD と s_min 床の更新**  
  `_resolve_blowout` の出力 `a_blow` を `psd.update_psd_state` へ渡し、`s_min_effective` を `psd` フロアとリンク。ステップごとに `psd.apply_uniform_size_drift` で sublimation による下限変動と κ の再評価を行う。[marsdisk/run.py:900-997]
- **ループ毎の再評価**  
  各ステップで `grid.omega_kepler` を再評価し `t_blow_step = chi_blow_eff / Omega_step` を取得、`radiation.beta` で最新 `β` を追跡。`fast_blowout_ratio = dt / t_blow_step` から `_fast_blowout_correction_factor` や必要ならサブステップ個数を決定。[marsdisk/run.py:906-1121]
- **遮蔽→Σ_{τ=1} クリップ**  
  `shielding.effective_kappa` / `shielding.apply_shielding` により κ_eff と Σ_{τ=1}` を計算し、`surface.step_surface` に `sigma_tau1` として連結する。[marsdisk/run.py:1135-1207] `surface.step_surface_density_S1` は `sigma_new = min(sigma_new, sigma_tau1)` のクリップ後に放射フラックス `sigma_new * Ω` を評価。[marsdisk/physics/surface.py:96-170]
- **表層 ODE と固体判定**  
  `phase_controller.evaluate` が `phase_decision.state == "vapor"` の際は `enable_blowout=False` とし、固体時のみ `surface.step_surface` で IMEX-BDF(1) を適用する。[marsdisk/run.py:1040-1208] 供給は `supply.get_prod_area_rate` から取得し `prod_subblow_area_rate` として ODE に注入。[marsdisk/run.py:1195-1207, marsdisk/physics/supply.py:3-101]
- **記録・出力**  
  `records`（series/run.parquet）に `M_out_dot`, `mass_lost_by_blowout`, `beta_at_smin`, `Sigma_tau1` 等を保存し、`diagnostics.parquet` には κ/Φ/遮蔽の派生値を出力。[marsdisk/run.py:1379-1567] `summary.json` と `checks/mass_budget.csv` には `M_loss_rp_mars`, `mass_loss_rp_mars` 等を集計し、`writer.write_parquet/json/csv` を通じて永続化。[marsdisk/run.py:1652-1785, marsdisk/io/writer.py:1-200]

## A2. 要件適合性（現状判定）
| # | 要件 | 判定 | 根拠 |
|---|---|---|---|
| 1 | 火星放射のみ（太陽項無効） | **No** | `Radiation` スキーマには `use_mars_rp`/`use_solar_rp` のような物理トグルが存在せず、CLI でも `radiation_field` は単純に `cfg.radiation.source` を文字列で拾うだけなので、旧来の「solar/TL2003」系設定を要求された際に即時拒否したり強制無効をログ出力する仕組みがない。[marsdisk/schema.py:444-520, marsdisk/run.py:476-489, 1747-1775] 仕様で求められた「Mars 圧のみに限定」スイッチを明示できないため補強が必要。 |
| 2 | 固体のみにブローアウト適用 | **Yes** | `phase_controller.evaluate` の結果が `state=="vapor"` の時は `enable_blowout=False`／`sink_selected="hydro_escape"` に切り替え、`surface.step_surface` に渡す前に放射損失を停止。[marsdisk/run.py:1054-1091, 1170-1193] |
| 3 | 表層限定（Σ_{τ=1} と整合） | **Yes** | 各サブステップで `sigma_tau1_limit` を遮蔽から計算し、`surface.step_surface` に `sigma_tau1` を渡して `sigma_new = min(sigma_new, sigma_tau1)` のクリップ後に `outflux` を評価。[marsdisk/run.py:1135-1208, marsdisk/physics/surface.py:96-170] |
| 4 | 内側円盤のみを前提 | **Yes** | CLI は `scope.region != "inner"` を即座に拒否し（`marsdisk/run.py:463-465`）、半径解決も `geometry.r` または内側ディスク平均のみを許可している。[marsdisk/run.py:562-588] 外縁前提のスケーリングや遠点到達ロジックは存在しない。 |
| 5 | 2年スパンで t_blow・高速補正が安定 | **Yes** | `t_blow = chi_blow_eff / Ω`（`marsdisk/run.py:812-844`）を各ステップで更新し、`_fast_blowout_correction_factor` が `1-exp(-Δt/t_blow)` を解析的に評価して 0–1 の範囲にクリップ。[marsdisk/run.py:1093-1132, marsdisk/run.py:203-228] `dt_over_t_blow` の監視とサブステップ分割も同ブロックで実施。 |

→ 要件 1 が未達のため、`radiation.use_mars_rp / use_solar_rp` 等のトグル追加と火星専用強制（B1～B5）が必要。

## A3. ⟨Q_pr⟩ の出自確認
- `run_zero_d` は `radiation.qpr_lookup(size, T_use)` を唯一の参照点としており、`T_use` は Mars 温度ドライバ（`tempdriver.resolve_temperature_driver`）から供給される。[marsdisk/run.py:599-681, marsdisk/physics/tempdriver.py:1-140]
- `radiation.qpr_lookup` / `_resolve_qpr` は `Q_pr` をテーブルまたは override から解決し、失敗時は Mars 用のテーブルロード強制で RuntimeError を投げるため、太陽スペクトルを読み込む経路は存在しない。[marsdisk/physics/radiation.py:60-146]
- β や `a_blow` の導出式は Mars の重力・放射定数を固定で使用し、`L_M = 4πR_M^2σT_M^4` をベースにした放射圧効率を計算している。[marsdisk/physics/radiation.py:250-283] 따라서 Mars 黒体放射モデル以外は入り込まない。
