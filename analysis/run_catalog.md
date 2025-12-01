手動でキュレートした「スライドやドキュメントで使用を許可する run」のカタログ。`run_id` は一意かつ安定なラベルで、命名規則は `RUN_<TARGET>_<REGIME>_vNN`（例: `RUN_MARS_GASPOOR_v01`）。`run_id` の重複は禁止し、out/ 側の run_card に紐づける。

| run_id | short_label | physical_regime | out_dir_pattern | run_card_relpath | status | notes |
| --- | --- | --- | --- | --- | --- | --- |
| RUN_MARS_GASPOOR_v01 | gas-poor 基本 | 蒸気≲数% で TL2003 無効の基準 run | out/2024*/gaspoor_v01*/ | run_card.md | placeholder | TODO: 実データで置換。 |
| RUN_MARS_GASRICH_v01 | gas-rich 感度 | gas-rich 想定で圧力ドライブを追加 | out/2024*/gasrich_v01*/ | run_card.md | placeholder | TODO: 設定ファイルと out_dir を確定。 |
| RUN_TL2003_TOGGLE_v01 | TL2003 有効化 | gas-rich 想定で TL2003 表層トルクを on/off | out/2024*/tl2003_toggle_v01*/ | run_card.md | placeholder | TODO: ALLOW_TL2003=true ケースを登録。 |
| RUN_TEMP_DRIVER_v01 | 温度ドライバ掃引 | 火星温度テーブルで β・a_blow の変化を追う | out/2024*/temp_driver_v01*/ | run_card.md | placeholder | TODO: テーブルパスと run_card を紐付け。 |
| RUN_WAVY_PSD_v01 | wavy PSD 実験 | wavy_strength>0 で PSD ジグザグを確認 | out/2024*/wavy_psd_v01*/ | run_card.md | placeholder | TODO: スナップショット出力を確認して反映。 |
