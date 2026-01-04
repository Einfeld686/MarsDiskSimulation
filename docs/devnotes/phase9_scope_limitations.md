# フェーズ9 内側0Dシミュレーションのスコープと限界

## 目的・背景
- 本ノートは `run_zero_d` が物理的に妥当となる条件と、適用外となる条件を仕様として明示する。[@Hyodo2018_ApJ860_150] のガス貧シナリオから着想を得ているが、ここでは実装済み前提の整理にとどめ、追加モデルは提案しない。

## 適用範囲（スコープ）
- 空間: `scope.region` は常に `"inner"` へ強制され、半径を 1 点代表とする 0D モデル。`disk.geometry.r_in_RM/r_out_RM` から単一の `Omega` を決め、半径方向の輸送や外側円盤は扱わない。[marsdisk/config_utils.py:14–43][marsdisk/run.py:643–799]
- 時間: 解析窓はデフォルト 2 年 (`scope.analysis_years`) で、`numerics.t_end_*` 未指定時にこの値が書き戻される。時間刻みは `_resolve_time_grid` が `t_blow=1/Ω` の 5% と `t_end/200` の最小を取り、数年スパンで吹き飛び時間を解像する設計。10^5 年級の長期進化には適さない。[marsdisk/run.py:306–367][marsdisk/run.py:643–693][marsdisk/run.py:1083–1095]

## 想定している物理過程
- 昇華シンク: `sinks.mode!="none"` かつ `physics_mode!="collisions_only"` のときに有効で、HKL 由来の `ds/dt` とガス抗力を「代表粒径の有効時定数」として足し合わせるだけ。流体力学的に時間発展する蒸気逃散は解かず、簡略シンクとして扱う。[marsdisk/run.py:1049–1080][marsdisk/run.py:1241–1270][marsdisk/physics/sinks.py:70–160]
- 衝突カスケード: 表層 ODE は `Σ̇ = prod - Σ/t_blow - Σ/t_coll - Σ/t_sink` を固定ステップの IMEX-Euler で解く。`t_coll` は Wyatt 型 `1/(Ωτ)` を optically thin 面にだけ適用し、フル Smoluchowski カスケードやサイズ分割の衝突演算は行わない。[marsdisk/physics/surface.py:17–175][marsdisk/run.py:1400–1527][marsdisk/run.py:1720–1784]
- 放射圧ブローアウト（火星のみ）: `radiation_field` は Mars 固定で、β と `a_blow` は火星の黒体放射から計算する。`use_solar_rp` 要求はログ警告のみにとどまり、太陽放射は常に無効。ブローアウトは `collisions_active` かつ `rp_blowout_enabled` かつ β≥0.5 のときのみ走り、固体相限定で τ ゲートの条件を満たす場合に限る。[marsdisk/run.py:664–920][marsdisk/run.py:1272–1305][marsdisk/physics/radiation.py:250–288]

## 物理モードの組み合わせと解釈
- モード分離: `physics_mode` は `sublimation_only` / `collisions_only` / `combined` に正規化され、`primary_scenario` と `process_overview` に記録される。`collisions_only` では昇華シンクと `ds/dt` が停止し、`sublimation_only` では衝突とブローアウトが停止する。[marsdisk/run.py:575–693][marsdisk/run.py:1069–1080][marsdisk/run.py:2063–2196]
- ブローアウトの有効条件: `blowout.enabled`・`sinks.rp_blowout.enable`・`radiation.use_mars_rp` が真で、かつ上記の衝突モードが有効なときのみ表層流出を計算する。Gate モードや τ ゲートに阻まれた場合は outflux が 0 になる。[marsdisk/run.py:903–920][marsdisk/run.py:1272–1305][marsdisk/run.py:1720–1784]
- 単一過程比較の読み替え: 研究で用いる「経路A:昇華のみ」「経路B:衝突のみ」は Phase5 比較ランナーが生成する 2 本のサブランと一致し、出力は `variant` 列付きでマージされる（本ノートは設定解釈のみを対象）。[marsdisk/run.py:2142–2209][marsdisk/run.py:2528–2557]

## 妥当性の条件
- 軌道条件: Wyatt スケーリングの前提から、低離心率・低傾斜で光学的に薄い面に対する代表値として解釈する。厚いガス層や大きな e/i の非線形力学は含まない。[marsdisk/physics/surface.py:17–83]
- 相状態: 相判定が固体のときのみブローアウトを許可し、蒸気相では水素逃散の簡易時定数に切り替える。固体→蒸気の移行はフラグ切り替えのみで、相転移の詳細熱力学は解かない。[marsdisk/run.py:1272–1317]
- 放射場の固定性: 火星放射温度ドライバの時間変化のみを追跡し、太陽照射や火星放射の長期進化は無視する設定である。[marsdisk/run.py:664–681][marsdisk/run.py:1720–1744]
- 時間分解能: `dt_over_t_blow` を監視しつつ固定ステップで進めるため、`dt/t_blow` が大きくなる長時間・低 Ω スケールでは補間誤差が増える。数年窓と t_blow オーダーを同時に解像できる設定で使う。

## 限界と非対応事項
- 太陽放射圧・Lorentz 力・大気抗力など火星起源でない外力は未実装。`use_solar_rp` は無視される。[marsdisk/run.py:664–920][marsdisk/run.py:2282–2347]
- 外側円盤・半径方向輸送・粘性拡散は解かず、1 本の代表半径に閉じた質量収支のみを扱う。[marsdisk/run.py:643–799][marsdisk/run.py:1400–1527]
- フル衝突カスケードや多層 PSD 進化は省略し、Wyatt 時定数と単一の表層 ODE に還元している。質量スペクトルの“wavy”は補正項どまりで、粒子追跡や Monte Carlo は行わない。[marsdisk/run.py:957–1233][marsdisk/physics/surface.py:17–175]
- ガス散逸・蒸気膨張は `t_sink`/`hydro_escape_timescale` の代替時定数で近似し、流体力学的な圧力勾配や補給源の時間変動は扱わない。[marsdisk/run.py:1241–1313][marsdisk/physics/sinks.py:70–160]
- 長期進化や衛星形成（10^5–10^7 年）を問う研究、外側ディスクの遠点通過や太陽干渉を含む課題には、時間スケールと力学モデルの双方で適用外。

## 出力と解釈のガイド
- `summary.json` の `inner_disk_scope` / `analysis_window_years` / `radiation_field` / `primary_scenario` / `process_overview` / `time_grid` で、本ノートのスコープ条件と一致しているかを確認できる。[marsdisk/run.py:2063–2237]
- `run_config.json` には `scope_controls`・`physics_controls`・`process_controls`・`time_grid`・`radiation_provenance` が保存され、再解析時に放射源やモードの解決結果を追跡できる。[marsdisk/run.py:2282–2440]
- `checks/mass_budget.csv` は各ステップの質量収支誤差（許容 0.5%）を残す。`dt_over_t_blow` 列（series/run.parquet）も併せて時間解像の妥当性を確認する。[marsdisk/run.py:1720–1784][marsdisk/run.py:1923–1976]

### 研究者向けチェックリスト
- 解析したい時間スケールが `summary.analysis_window_years` と同程度（数年）である。
- `summary.radiation_field=="mars"` かつ `summary.blowout_active` が意図した値かを確認したうえで、太陽放射圧や外側円盤を含める必要がない。
- `summary.primary_scenario`（combined/衝突のみ/昇華のみ）が研究の「経路A/B」に対応している。
- `summary.time_grid.dt_step_s` と `dt_over_t_blow_median` が blow-out 時間を十分に解像している。
- 質量収支 (`checks/mass_budget.csv`) が許容内で、`run_config.physics_controls` のトグルが意図どおりかを確認できる。
