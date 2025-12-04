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
| RUN_MARS_GASPOOR_v01 | ガス希薄基準（0D） | configs/base.yml | out/*RUN_MARS_GASPOOR_v01* | ガスがほとんど無い衝突起源ダスト円盤を 0 次元モデルで時間発展させる基準 run。粒子数収支と代表 β の時間変化を確認する。 | - | - | primary | スライドでは「代表 run」として必ず 1 回は紹介する。結果モードでもこの run をベースラインとし、ほかの run は差分説明にとどめる。 |
| RUN_TL2003_TOGGLE_v01 | TL2003 トグル感度 | configs/base.yml + configs/overrides/tl2003_on.yml | out/*RUN_TL2003_TOGGLE_v01* | TL2003 型のガス存在ケースとガス希薄基準を比較し、サブブローアウト粒子の減衰スケールや寿命がどれだけ変わるかを見る run。 | - | - | support | ガス希薄基準との「差分」を 1 枚のスライドにまとめる用途で使う。単独で長く説明しない。図が揃っていない場合はテキストだけでもよい。 |
| RUN_TEMP_DRIVER_v01 | 強放射・β 掃引 | configs/mars_temperature_driver.yml | out/*RUN_TEMP_DRIVER_v01* | 火星放射場や β 分布を時間的に変化させたときの応答を見る run。高 β 領域での質量フローや寿命の感度を確認する。 | - | - | support | β パラメータ掃引の例として、必要なら 1 枚だけ紹介する。結果がまだ無い場合は「こういう run を用意している」程度の説明にとどめる。 |
| RUN_WAVY_PSD_v01 | wavy PSD 実験 | configs/base.yml + configs/overrides/psd_wavy.yml | out/*RUN_WAVY_PSD_v01* | 粒径分布に人工的な山谷（wavy PSD）を入れたときに、放射圧と衝突でどのように平滑化されるかを調べる計画 run。 | - | - | planned | まだ実行していない前提。「今後やりたい実験一覧」のスライドで 1 行だけ触れる。詳細な説明や図は不要。 |
| RUN_HIGH_BETA_SHIELD_v01 | 高 β・遮蔽テスト | configs/base.yml + configs/overrides/high_beta_shield.yml | out/*RUN_HIGH_BETA_SHIELD_v01* | β が大きい粒子が多数ある場合に、遮蔽効果をオン/オフしたときの違いを確認する run。極端な高 β 条件でモデルがどこまで安定に動くかを見る。 | - | - | planned | これも計画段階として扱う。スライドでは、遮蔽モデルの限界や今後の検証計画を話すときに run 名を列挙する程度でよい。 |
