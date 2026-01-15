## 5. 再現性（出力・検証・運用）

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py, marsdisk/io/writer.py, marsdisk/io/streaming.py, marsdisk/io/diagnostics.py, marsdisk/io/checkpoint.py, marsdisk/io/archive.py, marsdisk/archive.py
-->

<!-- TEX_EXCLUDE_START -->
reference_links:
- @Krivov2006_AA455_509 -> paper/references/Krivov2006_AA455_509.pdf | 用途: 衝突カスケード検証と出力診断の基準
- @StrubbeChiang2006_ApJ648_652 -> paper/references/StrubbeChiang2006_ApJ648_652.pdf | 用途: t_collスケール検証
- @ThebaultAugereau2007_AA472_169 -> paper/references/ThebaultAugereau2007_AA472_169.pdf | 用途: wavy PSD の検証（wavy有効時）
<!-- TEX_EXCLUDE_END -->

---
### 6. 出力と検証

#### 6.1 出力・I/O・再現性

時間発展の各ステップは Parquet/JSON/CSV へ記録し、後段の解析・可視化で再構成可能な形で保存する（[@Krivov2006_AA455_509]）。必須の出力は `series/run.parquet`、`series/psd_hist.parquet`、`summary.json`、`checks/mass_budget.csv` で、追加診断は設定に応じて `diagnostics.parquet` や `energy.parquet` を生成する。

**必須出力**
- `series/run.parquet` は時系列の `time`, `dt`, `tau`, `a_blow`（コード上の名称、物理量は $s_{\rm blow}$）, `s_min`, `prod_subblow_area_rate`, `M_out_dot`, `mass_lost_by_blowout`, `mass_lost_by_sinks` などを保持する。\newline 衝突・時間刻みの診断は `smol_dt_eff`, `t_coll_kernel_min`, `dt_over_t_blow` を参照する。
- `series/psd_hist.parquet` は `time`×`bin_index` の縦持ちテーブルで、`s_bin_center`, `N_bin`, `Sigma_surf` を保持する。
- `summary.json` は $M_{\rm loss}$、case status、質量保存の最大誤差などを集約する。
- `checks/mass_budget.csv` は C4 質量検査を逐次追記し、ストリーミング有無に関わらず必ず生成する。

**追加診断（任意）**
- `series/diagnostics.parquet` は `t_sink_*`, `kappa_eff`, `tau_eff` を保持する。\newline `phi_effective`, `ds_dt_sublimation` などの補助診断を含む。
- `series/energy.parquet` は衝突エネルギーの内訳を記録する（energy bookkeeping を有効化した場合のみ）。

I/O は `io.streaming` を既定で ON とし（`memory_limit_gb=10`, `step_flush_interval=10000`, `merge_at_end=true`）、大規模スイープでは逐次フラッシュでメモリを抑える。\newline
CI/pytest など軽量ケースでは `FORCE_STREAMING_OFF=1` または `IO_STREAMING=off` を明示してストリーミングを無効化する。`checks/mass_budget.csv` はストリーミング設定に関わらず生成する。

- 実行結果は `out/<YYYYMMDD-HHMM>_<short-title>__<shortsha>__seed<n>/` に格納し、`run_card.md` へコマンド・環境・主要パラメータ・生成物ハッシュを記録して再現性を担保する。
- `run_sweep.cmd` のスイープ実行では `BATCH_ROOT`（`OUT_ROOT` があればそれを使用）配下に\newline
  `SWEEP_TAG/<RUN_TS>__<GIT_SHA>__seed<BATCH_SEED>/<case_title>/` を作成し、各ケース内に `run_card.md` と主要生成物を保存する。
- `run_config.json` には採用した $\rho$, $Q_{\rm pr}$, $s_{\rm blow}$, 物理トグル、温度ドライバの出典が保存され、再解析時の基準となる。

- **参照**: analysis/run-recipes.md §出力  
- **参照**: analysis/AI_USAGE.md (I/O 規約)

---
#### 6.2 検証手順

##### 6.2.1 ユニットテスト

```bash
pytest tests/ -q
```

主要テストは analysis/run-recipes.md §検証チェックリスト を参照。特に以下でスケールと安定性を確認する。

- Strubbe–Chiang 衝突寿命スケール: `pytest tests/integration/test_scalings.py`\newline
  `::test_strubbe_chiang_collisional_timescale_matches_orbit_scaling`（[@StrubbeChiang2006_ApJ648_652]）
- Blow-out 起因 “wavy” PSD の再現: `pytest tests/integration/test_surface_outflux_wavy.py`\newline
  `::test_blowout_driven_wavy_pattern_emerges`（[@ThebaultAugereau2007_AA472_169]）
- IMEX-BDF(1) の $\Delta t$ 制限と質量保存: `pytest tests/integration/test_mass_conservation.py`\newline
  `::test_imex_bdf1_limits_timestep_and_preserves_mass`（[@Krivov2006_AA455_509]）
- 1D セル並列の on/off 一致確認（Windowsのみ）: `pytest tests/integration/test_numerical_anomaly_watchlist.py`\newline
  `::test_cell_parallel_on_off_consistency`
- 質量収支ログ: `out/checks/mass_budget.csv` で |error| ≤ 0.5% を確認（C4）

検証では、$t_{\rm coll}$ スケールが理論式のオーダーと一致すること、$\Delta t$ の制約が安定性を満たすこと、ブローアウト近傍で wavy 構造が再現されることを確認する。これらの基準は設定変更後の回帰検証にも適用する。

##### 6.2.2 実行後の数値チェック（推奨）

- `summary.json` の `mass_budget_max_error_percent` が 0.5% 以内であること。
- `series/run.parquet` の `dt_over_t_blow` が 1 未満に収まっているかを確認する。\newline 超過時は `fast_blowout_flag_*` と併せて評価する。
- 衝突が有効なケースでは `smol_dt_eff < dt` が成立し、`t_coll_kernel_min` と一貫しているかを確認する。

##### 6.2.3 ドキュメント整合性

```bash
make analysis-sync      # DocSync
make analysis-doc-tests # アンカー健全性・参照率検査
python -m tools.evaluation_system --outdir <run_dir>  # Doc 更新後に直近の out/* を指定
```

- **詳細**: analysis/overview.md §16 "DocSync/検証フローの固定"


---
### 11. 先行研究リンク

- 温度ドライバ: [Hyodo et al. (2018)](../paper/pdf_extractor/outputs/Hyodo2018_ApJ860_150/result.md)
- gas-poor/衝突起源円盤の文脈:\newline
  [Hyodo et al. (2017a)](../paper/pdf_extractor/outputs/Hyodo2017a_ApJ845_125/result.md)\newline
  [Canup & Salmon (2018)](../paper/pdf_extractor/outputs/CanupSalmon2018_SciAdv4_eaar6887/result.md)\newline
  [Olofsson et al. (2022)](../paper/pdf_extractor/outputs/Olofsson2022_MNRAS513_713/result.md)
- 放射圧・ブローアウト:\newline
  [Burns et al. (1979)](../paper/pdf_extractor/outputs/Burns1979_Icarus40_1/result.md), [Strubbe & Chiang (2006)](../paper/pdf_extractor/outputs/StrubbeChiang2006_ApJ648_652/result.md)\newline
  [Takeuchi & Lin (2002)](../paper/pdf_extractor/outputs/TakeuchiLin2002_ApJ581_1344/result.md), [Takeuchi & Lin (2003)](../paper/pdf_extractor/outputs/TakeuchiLin2003_ApJ593_524/result.md)\newline
  [Shadmehri (2008)](../paper/pdf_extractor/outputs/Shadmehri2008_ApSS314_217/result.md)
- PSD/衝突カスケード:\newline
  [Dohnanyi (1969)](../paper/pdf_extractor/outputs/Dohnanyi1969_JGR74_2531/result.md)\newline
  [Krivov et al. (2006)](../paper/pdf_extractor/outputs/Krivov2006_AA455_509/result.md)\newline
  [Thébault & Augereau (2007)](../paper/pdf_extractor/outputs/ThebaultAugereau2007_AA472_169/result.md)
- 供給・ソース/損失バランス: [Wyatt, Clarke & Booth (2011)](../paper/pdf_extractor/outputs/WyattClarkeBooth2011_CeMDA111_1/result.md)
- 初期 PSD:\newline
  [Hyodo et al. (2017a)](../paper/pdf_extractor/outputs/Hyodo2017a_ApJ845_125/result.md)\newline
  [Jutzi et al. (2010)](../paper/pdf_extractor/outputs/Jutzi2010_Icarus207_54/result.md)
- 速度分散:\newline
  [Ohtsuki et al. (2002)](../paper/pdf_extractor/outputs/Ohtsuki2002_Icarus155_436/result.md)\newline
  [Lissauer & Stewart (1993)](../paper/pdf_extractor/outputs/LissauerStewart1993_PP3/result.md)\newline
  [Wetherill & Stewart (1993)](../paper/pdf_extractor/outputs/WetherillStewart1993_Icarus106_190/result.md)\newline
  [Ida & Makino (1992)](../paper/pdf_extractor/outputs/IdaMakino1992_Icarus96_107/result.md)\newline
  [Imaz Blanco et al. (2023)](../paper/pdf_extractor/outputs/ImazBlanco2023_MNRAS522_6150/result.md)
- 破砕強度・最大残存率:\newline
  [Benz & Asphaug (1999)](../paper/pdf_extractor/outputs/BenzAsphaug1999_Icarus142_5/result.md)\newline
  [Leinhardt & Stewart (2012)](../paper/pdf_extractor/outputs/LeinhardtStewart2012_ApJ745_79/result.md)\newline
  [Stewart & Leinhardt (2009)](../paper/pdf_extractor/outputs/StewartLeinhardt2009_ApJ691_L133/result.md)
- 遮蔽 (Φ):\newline
  [Joseph et al. (1976)](../paper/pdf_extractor/outputs/Joseph1976_JAS33_2452/result.md)\newline
  [Hansen & Travis (1974)](../paper/pdf_extractor/outputs/HansenTravis1974_SSR16_527/result.md)\newline
  [Cogley & Bergstrom (1979)](../paper/pdf_extractor/outputs/CogleyBergstrom1979_JQSRT21_265/result.md)
- 光学特性: [Bohren & Huffman (1983)](../paper/pdf_extractor/outputs/BohrenHuffman1983_Wiley/result.md)
- 昇華:\newline
  [Markkanen & Agarwal (2020)](../paper/pdf_extractor/outputs/Markkanen2020_AA643_A16/result.md)\newline
  [Kubaschewski (1974)](../paper/pdf_extractor/outputs/Kubaschewski1974_Book/result.md)\newline
  [Fegley & Schaefer (2012)](../paper/pdf_extractor/outputs/FegleySchaefer2012_arXiv/result.md)\newline
  [Visscher & Fegley (2013)](../paper/pdf_extractor/outputs/VisscherFegley2013_ApJL767_L12/result.md)\newline
  [Pignatale et al. (2018)](../paper/pdf_extractor/outputs/Pignatale2018_ApJ853_118/result.md)\newline
  [Ronnet et al. (2016)](../paper/pdf_extractor/outputs/Ronnet2016_ApJ828_109/result.md)\newline
  [Melosh (2007)](../paper/pdf_extractor/outputs/Melosh2007_MPS42_2079/result.md)

- 参照インデックス: [paper/abstracts/index.md](../paper/abstracts/index.md)\newline
  [analysis/references.registry.json](../analysis/references.registry.json)


---
