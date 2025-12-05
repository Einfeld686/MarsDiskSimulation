このディレクトリはワークステーションで再実行するためのテンプレートです。

- config_base_sublimation.yml: 現在の設定スナップショット（TM_K=4000, phase.enabled=true, dt_init=2.0, safety=0.08 など）。
- run_command.sh: 簡易実行スクリプト。OUTDIR 環境変数で出力先を上書きできます。
- 依存: python 3.10+、必要なライブラリ（numpy, scipy, pandas, pyarrow, ruamel.yaml, pydantic 等）をインストールしておいてください。
- 昇華: ロジスティック発散回避のため HKL に切り替えるオーバーライドを含めています（alpha_evap=0.007, mu=0.0440849, A=13.613, B=17850）。valid_K はコード既定のままです。
- 実行例:
    OUTDIR="out/$(date -u +%Y%m%d-%H%M%S)_sublim_smol_phase_MAX50M" ./run_template_sublim_smol_phase_MAX50M/run_command.sh
- 注意: MAX_STEPS はコード側で 50,000,000 に拡大済みです。メモリ負荷が高い場合は n_bins を減らす／t_end_years を短縮するなど調整してください。
