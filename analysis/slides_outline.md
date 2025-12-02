このファイルは、analysis 配下の説明を「私がスライドとして読み解く」ための骨格を固定する。数式は `analysis/equations.md`、モデル全体の詳細は `analysis/overview.md` を単一ソースとし、ここではスライド単位の目的と参照先だけを定義する。

## 最小スライドセット（10 枚固定）
| slide_id | title | type | mandatory | goal | key_points_draft | eq_refs | fig_refs | run_refs | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 問題設定とゴール | framing | yes | 火星ロッシュ内のガス希薄円盤で何を示すコードなのかを一枚で思い出す。 | Phobos/Deimosの軌道・物性と捕獲難; Hyodo+/Ronnet+/Canup&Salmonの大衝突円盤像; 本コードはgas-poor放射圧支配の検証用 | - | FIG_MARTIAN_MOONS_CONTEXT | - | literature_map.mdのREF_HYODO2017A,REF_RONNET2016,REF_CANUP2018を確認し、overview冒頭と読み合わせる。 |
| S02 | 大衝突とガス希薄前提 | background | yes | gas-poor前提がどの論文に支えられているかを一覧で確認する。 | Hyodo+2017/2018の蒸気比; Ronnet+2016の凝縮と微粒子; Kuramoto 2024などgas-richとの差異 | - | FIG_DISK_STRUCTURE_CARTOON | RUN_MARS_GASPOOR_v01 | overviewの前提・ガス節を読む。 |
| S03 | 火星放射とβ・blow-out | equations | yes | T_Mから⟨Q_pr⟩,β,a_blow,t_blowへの流れを俯瞰し、クリップ基準を把握する。 | Q_prテーブル入力の前提; β・a_blow・t_blow・chi_blowのつながりを矢印で示す | E.001,E.002,E.013,E.014 | FIG_QPR_BETA_FLOW | RUN_TEMP_DRIVER_v01 | 数式はequations.md参照。overviewの放射・blow-out節を参照。 |
| S04 | 0Dモデルの構造 | model | yes | run_zero_dが保持するstateとODE/代数式の接続を鳥瞰する。 | Smoluchowski破砕・表層ODE・放射/遮蔽の3ブロック、入力と主要出力の流れ | E.010,E.015,E.016,E.017 | FIG_MODEL_BLOCK_DIAGRAM | RUN_MARS_GASPOOR_v01 | overviewのモデル概要節を読む。 |
| S05 | 破砕カスケードとsub-blow-out供給 | equations | yes | sub-blow-out生成率がどの式で決まりmass budgetとどう結びつくか整理する。 | v_ijとC_ij、Q_D*、E.035の\dot{m}_{<a_blow}; 感度パラメータ(Q_D*,e_0など) | E.020,E.023,E.024,E.026,E.035 | FIG_PSD_SCHEMATIC | RUN_WAVY_PSD_v01 | overviewの破砕・PSD節とtestsのQ_D*設定を参照。 |
| S06 | 表層方程式・TL2003・Strubbe–Chiang | equations | yes | gas-poor既定とALLOW_TL2003トグルの意味を一枚で整理する。 | Strubbe–Chiang型t_collとloss; TL2003の薄ガスODE(E.007); 既定でどこを無効にするか | E.006,E.007,E.009 | FIG_SURFACE_ODE_SCHEMATIC | RUN_TL2003_TOGGLE_v01,RUN_MARS_GASPOOR_v01 | AI_USAGE.mdのgas-poor注記とoverviewの表層節を確認。 |
| S07 | 放射・遮蔽・温度ドライバ実装 | implementation | yes | Q_pr/Phiテーブルと火星温度ドライバのデータフローを把握する。 | qpr_table_pathとphi_tableの読み込み; mars_temperature_driverとT_M_usedの決まり方; CSV/NPZ生成メモ | E.013,E.015,E.016,E.017,E.031 | FIG_RADIATION_PIPELINE | RUN_TEMP_DRIVER_v01,RUN_HIGH_BETA_SHIELD_v01 | tables/やtools/の生成スクリプトにリンクし、overviewのI/O節を参照。 |
| S08 | 標準gas-poorラン結果 | results | yes | 標準条件でのτ, M_out_dot, beta_at_smin, mass budgetを一目で復習する。 | τ(t),M_out_dot(t),beta_at_smin(t)の代表時系列; mass budget誤差とM_loss | - | FIG_MLOSS_TIMESERIES,FIG_TAU_TIMESERIES | RUN_MARS_GASPOOR_v01 | summary.json/run_cardとfigures_catalogで対応図を確認。 |
| S09 | 感度: 温度・gas-rich・Q_pr | results | yes | 条件を振ったときのM_lossやβ/a_blow変化をざっくり把握する。 | 温度ドライバ差分; ALLOW_TL2003=trueの挙動; Q_prテーブル材質差の影響 | - | FIG_SENSITIVITY_GRID | RUN_TEMP_DRIVER_v01,RUN_TL2003_TOGGLE_v01 | run_catalogでhigh priorityのRUNを確認し、overview感度節を参照。 |
| S10 | まとめ・限界・TODO | discussion | yes | 適用範囲と限界、次の実装・検証TODOを一枚に圧縮する。 | 0D gas-poorで言える/言えない; 未実装物理と感度計画; DocSyncやevaluation_systemとの連携メモ | - | - | RUN_MARS_GASPOOR_v01 | UNKNOWN_REF_REQUESTSやevaluation_system結果サマリへのリンクを追記予定。 |

## メモ
- このファイルは手編集のみ（自動生成禁止）。増やす場合も既存IDを変えずにS11以降を追加する。
- eq_refsは必ず`analysis/equations.md`のE.xxxのみを列挙し、式を再掲しない。
- fig_refs/run_refsは将来の`figures_catalog.md`/`run_catalog.md`と1:1対応させ、IDは一意に保つ。
- overviewの該当節やliterature_map/glossaryをnotesに明示し、読む順番の誘導に使う。
