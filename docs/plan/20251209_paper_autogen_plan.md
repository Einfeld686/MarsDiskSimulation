# 論文自動生成ロードマップ（作業メモ）

目的: 本リポジトリの analysis 群と実行ログを材料に、段階的な自動生成パイプラインで論文草稿を組み立てる手順を整理する。GitHub には push しないローカル運用前提。

## 0. 事前の読み込み・更新
- `analysis/AI_USAGE.md` と `analysis/overview.md` を参照し、参照規約と最新の責務割りを確認する。
- analysis を編集した場合のみ `python -m tools.doc_sync_agent --all --write` → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` を実行する。論文生成パイプラインはデフォルトで analysis 更新を呼ばず、必要時のみ `--update-analysis` 等の明示スイッチで起動する。
- 生成に使う RUN_/FIG_ は `analysis/run_catalog.md` と `analysis/figures_catalog.md` から選択し、一意性を崩さない。

## 1. 入力収集ステップ（データ整形）
- 1 論文 = 1 マニフェスト（例: `configs/<paper_config>.yml`）とし、`runs: [RUN_001, RUN_002, ...]` と FIG_ID の集合を列挙する。JSON も `{runs: {run_id: {...}}, derived: {...}}` のようにネストして「論文単位」を保持する。
- サンプル: `configs/paper_marsdisk_draft.yml`（既存 `out/<run_id>` を束ねる草稿用）。`python tools/paper_manifest.py --manifest configs/paper_marsdisk_draft.yml --outdir out/<paper_run_id>` で `out/<paper_run_id>/resolved_manifest.json` / `out/<paper_run_id>/paper_checks.json` / `out/<paper_run_id>/figure_tasks.json` を生成する。
- 各 run の `out/<stamp>/run_card.md` を読み取り、設定・環境・パラメータ・乱数種を抽出して JSON にまとめる。簡易スキーマを定義し、`run_id: str`, `M_out_dot: float`, `tau: list[float]`, `tags: list[str]` などを型チェックする。
- `out/<stamp>/series/*.parquet` から主要系列（M_out_dot, prod_subblow_area_rate, tau など）を集計し、図表用の tidy データフレームを生成する。
- `out/<run_id>/summary.json` と `out/<run_id>/checks/mass_budget.csv` を突合し、質量収支と安定性のステータスを付与する。論文レベルの集約タグ（質量収支OK率、IMEX安定率など）もここで計算して JSON に格納する。

## 2. テキスト素片生成ステップ（セクション別）
- 機械が書く範囲と人間が書く範囲を分離する。背景・設定列挙・数値要約・しきい値比較はテンプレートで自動生成し、解釈や考察（Discussion/Conclusion）は `%% MANUAL_DISCUSSION %%` のような手書きブロックを残して上書きしない。
- テンプレート例: `{{ auto_results_paragraph(run_id) }}` を数値描写専用の枠にし、`%% MANUAL_xxx %%` で人手領域を確保する。
- 単位系（SI/cgs）、小数桁、対数表記の採否をテンプレート設定で持たせ、後から一括調整できるようにする。
- 引用・参考文献は `REF:slug -> bibkey` の対応表（YAML/JSON）を用意し、BibTeX/CSL 生成をそこから行う。未知の出典は `analysis/UNKNOWN_REF_REQUESTS.jsonl` に登録し、本文には `TODO(REF:slug)` を置く。
- `analysis/equations.md` のアンカー参照を踏まえ、背景・手法の定型文をテンプレート化（数式はアンカーリンクのみで再タイプしない）。

## 3. 図表生成ステップ（再現性付き）
- `analysis/figures_catalog.md` の FIG_ID をキーに、対応する run と生成手順をマッピングする。複数 run 比較図も扱えるよう、`FIG_010: {runs: [RUN_A, RUN_B], script: ...}` のような構造を想定する。
- Parquet 集計から直接生成する図は、軸・単位・凡例のテンプレートを固定し、スタイルは共通の matplotlib スタイルファイルまたは `plot_style.py`（実装済: `paper/plot_style.py`）に集約する。`paper_manifest.py --emit-figure-tasks` で `out/<paper_run_id>/figure_tasks.json` を出力し、後続の描画スクリプトの入力に使う。
- `scripts/plots/render_figures_from_tasks.py --tasks out/<paper_run_id>/figure_tasks.json --resolved-manifest out/<paper_run_id>/resolved_manifest.json` で run_id→outdir を解決した推奨コマンド（`out/<paper_run_id>/figure_commands.txt`）を生成し、手元の CLI に合わせて実行する。共通描画ユーティリティとして `scripts/plots/plot_from_runs.py` を用意（mode: beta_timeseries / mass_budget / psd_wavy）。
- 乱数を使う図は run_card の seed を読み、再現性を保証する。
- 表（例: 感度掃引のまとめ）は `pandas.DataFrame.to_markdown()` 等で Markdown/LaTeX 両対応のフォーマットを出力する。

## 4. アセンブリステップ（論文骨子統合）
- 「1 論文 = 1 コンフィグ」を基本にし、`configs/<paper_config>.yml` にタイトル・著者・キーワード・採用する RUN_ID/FIG_ID・章構成テンプレートを記述する。
- セクション別テキスト素片と図表パスを統合する組版スクリプトを用意する（TeX なら main.autogen.tex を Jinja で生成し、main.manual.tex で手直しを重ねる等の二層構造を許容）。Markdown→Pandoc も選択肢に含める。
- メタデータ（タイトル、著者、キーワード、対応 RUN_/FIG_ 一覧、Git shortsha）を同時に埋め込む。
- ビルド成果物と中間生成物は `out/<YYYYMMDD-HHMM>_paper_draft__<shortsha>/` にまとめ、実行コマンドとハッシュを `out/<run_id>/run_card.md` ライクに記録する。

## 5. 検証ステップ（自動チェック）
- チェックレベルを「エラー/警告/情報」に分ける（例: 質量収支 >0.5% はエラーでビルド失敗、IMEX 収束ギリギリは警告で脚注を出すなど）。
- チェック結果を `out/<run_id>/paper_checks.json` に集約し、質量収支・IMEX・RUN/FIG の欠損重複・spell/grammar・アンカー整合性を記録する。`tools/paper_manifest.py` は mass_budget と dt_over_t_blow の閾値判定を含み、`--extra-checks <json|jsonl>` で外部ツール（spell/grammar/anchor）結果もマージできる。
- 質量収支誤差（|error_percent| < 0.5%）と IMEX 収束条件（Δt ≤ 0.1 min t_coll,k）を再評価し、本文に記載したしきい値と矛盾しないか確認する。
- 図表の再生成が FIG_ID と一致するか、RUN_ID が欠損・重複していないかをチェックする。
- 全文生成後に spell/grammar チェックとアンカー整合性の確認を走らせ、差分をログ化する。

## 6. 運用メモ
- 本ファイルはローカル補助用であり、GitHub への push は行わない（CI 想定外）。共有する場合は別ブランチや外部ストレージで。
- 追加の自動化スクリプトを置く場合は `tools/` または `scripts/` に配置し、analysis への参照と再現手順を明示する。
- 将来共有を見据え、簡易版ユーザ向けドキュメントを `docs/<paper_pipeline>.md` 等に分離して用意する余地を残す。

## 7. 次の実装順序（推奨）
- まず Step 1（論文マニフェスト + 入力整形）と Step 3（図表再生成）を動かし、RUN/FIG の再現性ループを固める。
- 続いて Step 2 の自動テキスト（Methods/Results の定型部）を載せ、Discussion は `%% MANUAL %%` のまま残して骨組みを確認する。
- 最後に Step 4–5 でビルド成果物構造と paper_checks.json の出力形式を固め、CI からも実行できるようにする。

## 現状のスケルトンと成果物
- マニフェスト例: `configs/paper_marsdisk_draft.yml`（RUN/FIG の束ね方としきい値を定義、既存 out/ ディレクトリに紐付け済）
- 解決スクリプト: `tools/paper_manifest.py`（`out/<paper_run_id>/resolved_manifest.json`, `out/<paper_run_id>/paper_checks.json`, `out/<paper_run_id>/figure_tasks.json` を生成）
- 図生成: `scripts/plots/plot_from_runs.py`（`out/<paper_run_id>/figure_tasks.json` の mode に応じた簡易図を生成）
- 図コマンド生成: `scripts/plots/render_figures_from_tasks.py`（`out/<paper_run_id>/figure_tasks.json` から `out/<paper_run_id>/figure_commands.txt` を生成）
- 図スタイル: `paper/plot_style.py`（rcParams の統一適用ユーティリティ）
- 手書き枠: `paper/manual/discussion.md`, `paper/manual/conclusion.md`（自動生成が上書きしない考察・結論用プレースホルダ）
