# 仮定自動抽出システム（初期草案）

目的: code/analysis から仮定と式参照を機械抽出し、`analysis/assumption_trace.md` と `analysis/assumptions_overview.md` を自動更新する段取りをまとめる。既存の出典管理（`analysis/references.registry.json` / `analysis/source_map.json` / `analysis/UNKNOWN_REF_REQUESTS.jsonll` / `analysis/inventory.json`）を前提に、仮定レベルの集約レイヤー `analysis/assumption_registry.jsonl` を追加する。

## 0. 事前確認と運用ルール
- 最終的には `make assumptions-autogen-check` で doc_sync → scan → render → analysis-doc-tests → evaluation_system を一括実行することを目標にする。それまでは `python -m tools.doc_sync_agent --all --write` → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` を同一バッチで回す。
- 仮定が出典不明な場合は `analysis/UNKNOWN_REF_REQUESTS.jsonl` に slug を登録し、コードや docs では `TODO(REF:slug)` を使う（AI_USAGE 準拠）。
- 数式の唯一ソースは `analysis/equations.md`。本システムは eq_id とアンカーのみ参照し、式本文を再生成しない。
- `analysis/assumption_trace.md` / `assumptions_overview.md` は、`@-- BEGIN:ASSUMPTION_REGISTRY --`〜`@-- END:ASSUMPTION_REGISTRY --` の自動ブロックをレンダーで上書きし、それ以外は人間が追記可能とする（全自動ファイルにする案も残すが、当面は部分自動で overview の運用に揃える）。
- UNKNOWN_REF_REQUESTS の slug は仮定系なら `assumption:<slug>` を推奨し、式レベルの slug と混在させない。

## 1. スコープと「仮定」の定義
- 対象モジュール: 0D ロジック（ブローアウト・遮蔽・PSD・表層 ODE・Smol カーネル）、設定 YAML、analysis 配下のメタ資料。
- 非対象: 1D 拡散、paper 自動生成、SiO₂ cooling サブプロジェクト、外部論文の全文スクレイプ。
- 本システムで扱う「仮定」の種類（抽出対象）
  - 物理前提: 例) gas-poor, thin disk, t_blow=1/Ω, 固定温度近似。
  - 数値スキーム: 例) IMEX-BDF1, 固定ステップ, fast_blowout 補正有無。
  - 運用/トグル: 例) blowout.enabled, psd.floor.mode, freeze_kappa, ALLOW_TL2003=false。
- scope 軸を追加し、仮定が効く範囲を示す: `project_default`（例: gas-poor 前提）, `module_default`（例: thin disk 0D 近似）, `toggle`（例: ALLOW_TL2003）。
- project_default の上書きは toggle で明示する（例: gas-poor を既定とし、`ALLOW_TL2003=true` で gas-rich 式を有効化）。
- assumption_tags は上記区分や物理テーマを示す短いラベル（例: `geometry:thin_disk`, `numerics:imex_bdf1`, `ops:gas_poor_default`）で、意味を詰め込みすぎない。

## 2. 正式スキーマ（assumption_registry の1レコード）
- フィールド（schema が truth、registry はそれに従う。生成方法/責務を併記）
  - `id`（必須）: 安定な識別子。Phase1 は人手で `category:slug`（例: `physics:thin_disk:001`、英小文字+数字+ハイフン/コロン推奨）を付与、将来は eq_id+tag から自動生成も検討。
  - `scope`（任意）: `project_default` | `module_default` | `toggle`。人手で指定。
  - `eq_id`（0件以上）: (E.xxx) 配列。DocSync が保証する `analysis/equations.md` 辞書からスキャナが自動付与。
  - `assumption_tags`（0件以上）: ラベル群。Phase1 人手、Phase2 以降スキャナが TODO(REF:slug) やタグ候補から補完。
  - `config_keys`（0件以上）: `schema.Config` のドット付きパス（例: `physics.blowout.enabled`）。スキャナが schema.Config introspect + config_utils label を利用して自動付与。
  - `code_path`（0件以上）: `analysis/source_map.json` のキーを優先し、無い場合のみ `[marsdisk/..py:line–line]` を fallback。スキャナ責務。
  - `run_stage`（1件以上推奨）: `init_ei` / `time_grid` / `physics_controls` / `surface_loop` / `smol_kernel` 等の列挙。Phase1 は人手で付与し、将来 decorator 等で自動化。
  - `provenance`（構造体）:
    - `paper_key`（任意）: `references.registry.json` のキー。Phase1 人手。
    - `unknown_slug`（任意）: `UNKNOWN_REF_REQUESTS` の slug（`assumption:` プレフィックス推奨）。スキャナが不足時に補完。
    - `source_kind`（必須）: `"equation" | "config" | "code_comment" | "test"`。スキャナが付与。
    - `note`（任意）: 補足。config_utils の label や特記事項をスキャナが追記。
  - `tests`（0件以上）: 関連 pytest 名。Phase1 任意手入力、将来は test_metadata から自動解決を検討。
- `analysis/assumption_trace_schema.md` では上記フィールドの型と必須/任意を定義し、registry はこれに準拠する。`analysis/assumption_registry.jsonl` が機械可読な唯一の元データ、`assumption_trace.md` / `assumptions_overview.md` はレンダーされた出力。
- 代表例（gas-poor デフォルトと TL2003 トグルを追跡するイメージ）
  - id: `ops:gas_poor_default`
  - scope: `project_default`
  - assumption_tags: [`geometry:thin_disk`, `ops:gas_poor_default`]
  - eq_id: TL2003 関連式を比較用に列挙するかは schema 側で方針決め（適用外を明示する場合は note で除外理由を書く）
  - config_keys: [`radiation.ALLOW_TL2003`, `physics.blowout.enabled`]
  - provenance: `paper_key=TakeuchiLin2003_ApJ593_524`, `source_kind="equation"`, `note="gas-poor を既定とし TL2003 は toggle true でのみ有効"`
  - tests: （空でも可、将来 surface/tau_gate 系テストを紐づけ）

## 3. 成果物と入力
- 成果物: `analysis/assumption_registry.jsonl`（構造化データ）、`assumption_trace.md` / `assumptions_overview.md`（自動ブロック上書き）、検知ログ（未解決 slug, coverage）。
- 既存メモの役割:
  - `assumption_trace_gap_list.md`: 既知のカバレッジ穴の手書きリスト（入力、当面手動）。
  - `assumption_trace_data_sources.md`: どのファイル群をスキャン対象にするかの一覧（入力、当面手動）。
- 入力ソース: `analysis/` docs（eq_id, TODO slug）, `marsdisk/` ソース（関数・コメント）, `configs/` YAML（値とブールトグル）, `schema.py` / `config_utils.py`（canonical key とラベル）, `analysis/source_map.json` / `analysis/inventory.json`（優先 index）。

## 4. フェーズ案（最新案に一本化）
1. ベースライン調査: `analysis/assumption_trace.md` skeleton, `AI_USAGE`, `overview.md` の provenance 節、`schema.py` / `config_utils.py`（温度・幾何・label返却）、`assumption_trace_gap_list.md`, `assumption_trace_data_sources.md` を読み、必須フィールド表と run_stage マップ（run.py の段階→列挙値）を起こす。inventory.json は「関数一覧＋アンカー付き index」として位置づける。
2. スキーマ確定: `assumption_trace_schema.md` を更新し、2章フィールドを必須/任意にマーク。config_keys の表記（ドットパス）、run_stage 列挙、provenance 構造、scope の扱いを明文化。必要 slug を UNKNOWN_REF_REQUESTS に登録（`assumption:` プレフィックス）。
3. 抽出パイプライン PoC（scanner 役割を明示）:
   - eq_id: `analysis/equations.md` → eq 辞書（DocSync 前提）→ source_map/inventory のアンカーと紐付け。未解決は WARN。
   - code_path: source_map/inventory のキーを優先し、足りない場合のみ rg+ast で `[file:line–line]` を補う。
   - config_keys: Pydantic の `schema.Config` を introspect し、leaf フィールドのドットパスを抽出。config_utils（resolve_reference_radius, resolve_temperature_field 等）が返す label を provenance.note に格納。
   - Markdown: TODO(REF:*) / assumption_tags / scope を軽量 regex で拾い、未知 slug は UNKNOWN_REF_REQUESTS に登録。
   - run_stage: run.py の段階マップに従い、scanner は JSONPath 風 (`run_config.physics_controls.blowout_enabled`) を code_path に併記可能とする。
   - tests: Phase1 は空でもよく、手入力のみ。将来 pytest コレクションからの自動紐付けを検討。
4. 集約・レンダー: スキャナ出力を `analysis/assumption_registry.jsonl` に書き出し、`analysis/tools/render_assumptions.py` で `assumption_trace.md` / `assumptions_overview.md` の自動ブロックを再生成。初回 PoC では現行構造に寄せて diff を確認し、将来の構造変更は意図的に記録する。
5. 検証・CI フック: `make assumptions-autogen-check` を追加し、doc_sync → scan → render → analysis-doc-tests → evaluation_system を束ねる。スキャナ単体は eq_id 未検出で WARN 続行だが、make ターゲットでは equation_coverage（例: ≥0.95）、function_reference_rate、anchor_consistency_rate が閾値未達なら FAIL。

## 5. 技術メモ
- eq_id パース: 見出しと `(E.xxx)` を対象にし、式本文は無視。coverage 指標 `equation_coverage = (#registry に含まれる eq_id の一意数) / (analysis/equations.md の eq_id 総数)` をログ出力し、しきい値はフェーズ5で決定。
- function_reference_rate: `analysis/source_map.json` で equation 出典を持つ code_path のうち、registry に登場する割合を指標とする。
- anchor_consistency_rate: source_map.json と inventory.json の行範囲が scanner 推定の `[file:line–line]` と一致（±数行）する割合。
- 解析手段の優先度: `analysis/source_map.json` / `analysis/inventory.json` を第一ソースとし、不足分のみ rg+ast で補う。inventory.json は「関数一覧＋アンカー付き index」として扱う。コードコメント由来は provenance.source_kind=`code_comment` で区別。
- config_keys: ドット付きパス（例: `surface.use_tcoll`, `radiation.TM_K`）。`config_utils` の返す label を provenance.note に写し、YAML の生値ではなく schema 上のキーを canonical にする。
- analysis/assumption_trace.md の運用: 自動ブロックを上書きし、手書き部分は保持。完全自動ファイルに分離する場合は `.autogen.md` を別途用意するオプションを残す。
- code_path/run_stage: run.py の段階構造に沿って run_stage を付与し、code_path は JSONPath 風を基本形とする。段階マップ（init_ei/time_grid/physics_controls/surface_loop/smol_kernel）はフェーズ1で固定し、decorator 化も検討。
- run_stage テンプレ（初期案）: `init_ei`（初期 e/i 設定、例: run_config["init_ei"] セクション）、`time_grid`（_resolve_time_grid 系）、`physics_controls`（blowout/shielding/psd_floor 等の有効化判断）、`surface_loop`（表層 ODE, tau_gate/gate_factor, fast_blowout 判定）、`smol_kernel`（Smoluchowski カーネル・質量検査）。フェーズ1で run.py の該当関数/辞書キーとの対応表を作る。

## 6. リスクと緩和
- アンカーずれ・誤検出: DocSyncAgent 連動と `analysis/tools/check_docs.py --strict` で検査。eq_id 未発見は WARN だが、coverage 指標が閾値未達なら make ターゲットで FAIL。
- スコープ膨張: 1D 拡散や paper 自動生成は別プランへ分離。フェーズ3の PoC 完了をマイルストーンに判断。
- 依存追加: 標準ライブラリ優先。新規ライブラリが必要な場合は最小限に限定し、事前合意を得る。

## 7. 直近の ToDo（作業順メモ）
- [x] フェーズ1: `assumption_trace_gap_list.md` / `assumption_trace_schema.md` / `assumption_trace_data_sources.md` / `overview.md` / `schema.py` / `config_utils.py` の現状確認と必須フィールド表の作成。
- [x] フェーズ2: スキーマ更新（2章フィールド、run_stage 列挙、provenance 構造）、UNKNOWN_REF slug 登録。
- [x] フェーズ3: `analysis/tools/scan_assumptions.py` を作成し、registry へ1件以上自動登録する PoC。source_map/inventory 優先の抽出方針を実装。
- [x] フェーズ4: `analysis/tools/render_assumptions.py` を拡張し、自動生成した docs を既存版と diff 確認。coverage 指標と equation_coverage を測り、`make analysis-doc-tests` で確認。
- [x] フェーズ5: `make assumptions-autogen-check` を追加し、doc_sync → scan → render → analysis-doc-tests → evaluation_system を束ねる。閾値未達時の FAIL 条件を設定。
