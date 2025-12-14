このファイルは重要なシミュレーション run を AI と著者が共有するための機械可読インデックスである。  
各行は `out/` 配下の 1 グループ（`out/<timestamp>__RUN_ID/...` のようなディレクトリ）に対応し、config ファイルと出力ディレクトリの対応づけを整理する。  
数式や物理定義は `analysis/equations.md` の (E.xxx) アンカーを参照し、ここでは再掲しない。

`status` 列はスライド生成時の優先度も兼ねており、次の値だけを使う想定とする。

* `primary` : 代表 run。構成モードでも必ず名前を出す。結果モードではまずここを題材にする。
* `support` : 比較用 run。primary run を説明するときの補助としてだけ使う。
* `planned` : まだ実行していない計画 run。スライドでは「今後の実験」の 1 枚にまとめる。
* `deprecated` : 過去の run。原則として新しいスライドには出さない。

| run_id | short_label | config_path | out_pattern | purpose_ja | eq_refs | fig_refs | status | notes_for_AI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RUN_TEMP_SUPPLY_SWEEP_v01 | 温度×供給スイープ（27ケース） | configs/sweep_temp_supply/temp_supply_T4000_eps1.yml | temp_supply_sweep/\<ts\>\_\_\<sha\>\_\_seed\*/T\*\_mu\*\_phi\*/ | T_LIST∈{5000,4000,3000}K × MU_LIST∈{1.0,0.5,0.1} × PHI_LIST∈{20,37,60} の 27 ケースで τ≈1 維持と供給経路（deep_mixing）を検証する主要スイープ。slab 冷却モデルを使用。 | E.027,E.042,E.043 | FIG_TEMP_SUPPLY_OVERVIEW,FIG_SUPPLY_SURFACE,FIG_OPTICAL_DEPTH | primary | 現在の研究の中心。スイープ結果から M_loss 感度とτ維持条件を評価する。`scripts/research/run_temp_supply_sweep.sh` で実行。 |
| RUN_MARS_GASPOOR_v01 | ガス希薄基準（0D） | configs/base.yml | out/*RUN_MARS_GASPOOR_v01* | ガスがほとんど無い衝突起源ダスト円盤を 0 次元モデルで時間発展させる基準 run。粒子数収支と代表 β の時間変化を確認する。 | - | FIG_BETA_SERIES_01 | support | スイープとの比較用ベースライン。単独では使わず差分説明に用いる。 |
| RUN_TL2003_TOGGLE_v01 | TL2003 トグル感度 | configs/base.yml + configs/overrides/tl2003_on.yml | out/*RUN_TL2003_TOGGLE_v01* | TL2003 型のガス存在ケースとガス希薄基準を比較し、サブブローアウト粒子の減衰スケールや寿命がどれだけ変わるかを見る run。 | - | FIG_SHIELDING_SERIES_01 | deprecated | gas-poor 既定では無効。参考程度にのみ言及。 |
| RUN_TEMP_DRIVER_v01 | 強放射・β 掃引 | configs/mars_temperature_driver.yml | out/*RUN_TEMP_DRIVER_v01* | 火星放射場や β 分布を時間的に変化させたときの応答を見る run。高 β 領域での質量フローや寿命の感度を確認する。 | - | FIG_BETA_SERIES_01 | deprecated | temp_supply_sweep で温度依存性をカバーするため非推奨。 |
| RUN_WAVY_PSD_v01 | wavy PSD 実験 | configs/base.yml + configs/overrides/psd_wavy.yml | out/*RUN_WAVY_PSD_v01* | 粒径分布に人工的な山谷（wavy PSD）を入れたときに、放射圧と衝突でどのように平滑化されるかを調べる計画 run。 | - | FIG_PSD_WAVY_01 | planned | 感度試験として今後検討。wavy_strength パラメータの効果を確認する。 |
| RUN_HIGH_BETA_SHIELD_v01 | 高 β・遮蔽テスト | configs/base.yml + configs/overrides/high_beta_shield.yml | out/*RUN_HIGH_BETA_SHIELD_v01* | β が大きい粒子が多数ある場合に、遮蔽効果をオン/オフしたときの違いを確認する run。極端な高 β 条件でモデルがどこまで安定に動くかを見る。 | - | - | planned | これも計画段階として扱う。遮蔽モデルの限界検証に使用予定。 |
