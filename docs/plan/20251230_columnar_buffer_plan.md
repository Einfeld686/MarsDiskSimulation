# 列指向バッファ化 実装プラン

> **作成日**: 2025-12-30  
> **ステータス**: 完了  
> **対象**: `marsdisk/run_one_d.py`, `marsdisk/run_zero_d.py`, `marsdisk/runtime/history.py`, `marsdisk/io/streaming.py`, `marsdisk/io/writer.py`, `marsdisk/output_schema.py`

---

## 目的

- 1D/0D の `list[dict]` 生成と `_ensure_keys` 呼び出しを削減し、I/O 系の Python オーバーヘッドを下げる
- `t_coll_kernel_min` など **ステップ定数列の一括付与**を可能にする
- Streaming ON/OFF の双方で **出力スキーマ互換**を維持する
- 物理式・数値スキーム・スイッチの意味を **一切変更しない**（速度改善のみ）

---

## 背景

- `run_one_d` はセルごとに巨大な `record` 辞書を生成し、最後に `t_coll_kernel_min` を **Python ループで後付け**している。
- Parquet 書き出し時に `list[dict] -> DataFrame -> pyarrow` の変換が発生し、I/O の支配度が高いケースで顕著に遅い。
- 既存の最適化（cache/Numba 等）は計算コストには効くが、**記録生成/変換のコストは残っている**。
- 最近の計測では Python ループ比率は 10–17% 程度で、`t_end` を延ばすほど `write_parquet` の比率が上がる。**I/O と記録生成の最適化が優先**。
- 運用は **スイープ並列が主軸**で、ネスト並列（セル並列＋スイープ並列）は過剰並列になりやすい。

---

## 非スコープ

- 物理モデル変更・新式導入
- 出力列の互換性破壊（列名・単位の変更）
- `psd_hist` / `mass_budget_cells` の全面的な列指向化（フェーズ後半で検討）
- データのリサンプリングや間引き（統計的な近似）

---

## 注意点・推奨（追記）

- **推奨: ColumnarBuffer は最小APIを明記**  
  `__len__`, `clear()`, `row_count`, `columns()` or `to_table()` を定義し、Streaming からは **list 互換 or 専用分岐**で扱えるようにする。
- **推奨: Parquet メタデータを必ず継承**  
  `write_parquet_columns` / `write_parquet_table` でも `units` / `definitions` を付与し、row/columnar で同等性を保証する。
- **推奨: 列順と dtype の安定化方針を明記**  
  `output_schema` を基準に列順を固定し、欠損列は `None` で補完、dtype は `writer` で統一する。
- **推奨: Streaming の flush/メモリ推定を更新**  
  `history.records` 依存の条件を ColumnarBuffer 対応に切替え、`_estimate_bytes` を `row_count` で評価できる設計にする。
- **推奨: トグル優先順位を定義**  
  `MARSDISK_DISABLE_COLUMNAR=1` が最優先で row を強制、次に YAML/CLI の `io.record_storage_mode` を適用。
- **推奨: スイープ並列前提のスレッド抑制**  
  スイープ並列時は `CELL_THREAD_LIMIT=1` / `NUMBA_NUM_THREADS=1` を基準とし、セル並列は必要時のみ明示的に有効化する。

---

## 方針（設計概要）

1) **ColumnarBuffer を追加**し、行指向（list[dict]）と列指向を切替可能にする  
2) `writer` に **列指向入力**を受け付ける API を追加し、`pyarrow.Table` 直書きを許可  
3) `run_one_d` / `run_zero_d` の記録生成を **列指向に置換**し、定数列は一括で付与  
4) **安全なフォールバック**（row モード）を残し、段階導入する

---

## スイープ並列前提の優先順位（更新）

- 1ランあたりの **I/O と記録生成の削減**を最優先（列指向化で DataFrame/辞書生成を減らす）。
- スイープ実行時は **セル並列を基本的に使わない**前提でチューニングする（廃止はしない）。
- 短い検証では `IO_STREAMING=off` とフック類の省略を推奨し、スイープ本番では `step_flush_interval` を大きめにして I/O をまとめる。

---

## 精密化した実装方針（数学・物理の妥当性維持）

### 変更の原則

- **数値スキームと力学は不変**  
  `run_one_d` / `run_zero_d` の更新式、停止判定、シンク/供給の分岐は一切変更しない。
- **出力値は同一であるべき**  
  row/columnar の差は「記録の持ち方」だけで、数値の差分を許容しない（丸め誤差レベル）。
- **スキーマ互換性を最優先**  
  既存の列名・単位・欠損扱いを維持し、解析パイプラインの破壊を避ける。
- **行順と再現性は不変**  
  `time` / `cell_index` の並び順や RNG の呼び順・シード・checkpoint/resume の挙動を変更しない。

### 実装の粒度（安全な差分単位）

1. **I/O層の拡張のみ**（計算と記録生成は変更しない）  
   - `writer.write_parquet_table` を追加し、既存 `write_parquet` と同じメタデータ付与に限定。
2. **記録コンテナの置換**（数値は同じ）  
   - `ColumnarBuffer` の導入は `history.records` / `history.diagnostics` の入れ替えのみ。
3. **run_one_d の記録生成最適化**  
   - `t_coll_kernel_min` など **ステップ定数列の一括付与**を row→columnar で実現。
4. **Streaming 統合**  
   - flush/merge で `ColumnarBuffer` を扱う分岐を追加するだけで、出力先やスキーマは不変。

### リスクと対策（妥当性維持）

- **列欠損のリスク**: `ensure_columns` を flush 直前に強制補完（row/columnar 両方）。
- **dtypeの揺れ**: `writer` 側で dtype 正規化（現行のメタデータ付与規則を踏襲）。
- **欠損表現の揺れ**: `None`/`NaN` の扱いを現行と一致させる（置換・統一しない）。
- **既存解析の互換**: `ZERO_D_SERIES_KEYS`/`ONE_D_EXTRA_SERIES_KEYS` を列順の基準とする。


---

## 実装メモ（安全化のための具体要件）

### ColumnarBuffer API 契約（必須）

- `append_row(record: Mapping[str, Any]) -> None`  
  行辞書から列配列へ追加。欠損キーは「未設定」として扱い、`ensure_columns` 適用時に補完。
- `row_count: int` / `__len__`  
  現在の行数を返す。Streaming のメモリ推定で使用。
- `clear() -> None`  
  列配列を空にし、row_count を 0 に戻す。
- `to_table(ensure_columns: Iterable[str] | None = None) -> pa.Table`  
  欠損列を `None` で埋め、`ensure_columns` があれば列順を固定。
- `columns() -> Iterable[str]`（任意）  
  現在保持している列名一覧。

### ColumnarBuffer 内部表現（推奨）

- `dict[str, list]` を基本にする（numpy 配列は最後に変換）。
- 1 行追加の O(列数) を許容し、flush 直前に `pyarrow.Table` へ変換。
- 追加順に列を保持し、`output_schema` で指定された列順に再配列する。

### Streaming 統合の要点

- `StreamingState.flush` は `history.records` が list か ColumnarBuffer かを判定。  
  - list の場合は現行の `writer.write_parquet` を継続  
  - ColumnarBuffer の場合は `to_table` を使い `writer.write_parquet_table` へ
- `StreamingState._estimate_bytes` は `row_count` を使う（list と ColumnarBuffer の両方対応）。
- `history.records.clear()` は ColumnarBuffer の `clear()` を呼ぶか、`history` 側に共通インタフェースを持たせる。

### writer API の設計要点

- `write_parquet_columns` と `write_parquet_table` は `write_parquet` と同等の `units` / `definitions` を付与。
- `ensure_columns` を受け取り、欠損列は `None` で補完。
- dtype 安定化は `write_parquet*` 内で統一する（bool/float/str の混在を許容）。

### run_one_d 実装の具体化

- `step_records` は ColumnarBuffer を使用。
- `t_coll_kernel_min` は **step 終端で `np.full(n, value)` 相当を一括追加**。
- `psd_hist_records` / `mass_budget_cells` は当面 list[dict] を維持。
- row/columnar 切替は `io.record_storage_mode` + 環境変数の優先順位で決定。

### run_zero_d 実装の具体化（任意）

- `records` と `diagnostics` のみに ColumnarBuffer を適用。
- `summary.json` 生成や `checks/mass_budget.csv` の有無は row と同じにする。

### トグル優先順位（明文化）

1. `MARSDISK_DISABLE_COLUMNAR=1` → **強制 row**
2. `io.record_storage_mode` or `io.columnar_records` → row/columnar を選択
3. 未設定なら既定は row

### 失敗時のフォールバック

- ColumnarBuffer の `to_table` が失敗した場合は **row に落として継続**（ログ warning）。
- Parquet 書き込み失敗は現行の例外処理と同一扱い。

---

## 実装フェーズ

### フェーズA: ColumnarBuffer と writer の土台

- `marsdisk/runtime/history.py` に ColumnarBuffer を追加（records/diagnostics 用）
- `marsdisk/io/writer.py` に以下の新規 API を追加
  - `write_parquet_columns(columns: Mapping[str, Sequence], ...)`
  - `write_parquet_table(table: pa.Table, ...)`
- ColumnarBuffer の最小 API を定義（`__len__`, `clear`, `row_count`, `to_table` など）
- `marsdisk/io/streaming.py` が ColumnarBuffer を認識し、**行/列どちらでも flush**できるようにする
- **出力列の欠落は flush 直前に補完**（`ensure_columns` を ColumnarBuffer 側で実施）
- `write_parquet_*` は row と同等のメタデータ（units/definitions）を必ず付与

### フェーズB: run_one_d を列指向に置換

- `records` 生成を **列配列への append** に置換
- `t_coll_kernel_min` は **ステップ末に一括埋め**（`np.full(n, value)` 相当）
- `output_schema` のキーリストを列順の基準として使用し、動的列は最小限にする
- 既存の `psd_hist_records` / `mass_budget_cells` は当面 list[dict] を維持
- **不変条件**: ステップ内の `record` 構築ロジック（値の計算式・キーの意味）は変更しない

### フェーズC: run_zero_d への展開（任意）

- 0D の `records/diagnostics` にも ColumnarBuffer を適用
- Streaming ON/OFF と `summary.json` の互換性確認

### フェーズD: 拡張（任意）

- `psd_hist` / `mass_budget_cells` の列指向化
- 1D の `diagnostics` も列指向化

---

## 設定・トグル案

`io` に以下のいずれかを追加（互換優先）:

- `io.record_storage_mode: "row" | "columnar"`（既定 `"row"`）
- または `io.columnar_records: bool`（既定 `false`）

**安全弁**:
- `MARSDISK_DISABLE_COLUMNAR=1` で強制 row に戻す（最優先）

---

## 変更予定の主なファイル

| ファイル | 変更内容 |
|---------|----------|
| `marsdisk/runtime/history.py` | ColumnarBuffer 定義・History への組込み |
| `marsdisk/io/writer.py` | Columnar 入力対応の追加 API |
| `marsdisk/io/streaming.py` | Columnar flush 対応 |
| `marsdisk/run_one_d.py` | record 生成を列指向化、定数列の一括付与 |
| `marsdisk/run_zero_d.py` | 任意で列指向化 |
| `marsdisk/output_schema.py` | 列順・必須列の整理（破壊的変更なし） |
| `marsdisk/schema.py` | 新トグルの追加 |

---

## テスト計画

- `tests/integration/test_run_one_d_output_parity.py`
- `tests/integration/test_run_one_d_streaming_schema.py`
- `tests/integration/test_mass_budget_cells.py`
- `tests/integration/test_run_zero_d_output_parity.py`（0D拡張時）
- 新規: `tests/integration/test_columnar_records.py`  
  - row/columnar で列集合と主要値が一致すること  
  - `t_coll_kernel_min` の一括付与が正しいこと
- 追加: Parquet メタデータ（units/definitions）が row/columnar で一致すること
- 追加: Streaming ON/OFF の双方で `checks/mass_budget.csv` が生成されること
- 追加: `checks/mass_budget.csv` の内容（error_percent 等）が row/columnar で一致すること
- 追加: 既存スイープ結果の解析スクリプトが **同一列名で読み込める**こと（スキーマ互換）

---

## テスト設計（詳細）

### ColumnarBuffer 単体（unit）

- **ケース: row_count / clear の基本動作**  
  **入力**: ColumnarBuffer に 2 行分の列データを追加 → `row_count`/`__len__` を確認 → `clear()`  
  **期待**: `row_count==2`, `len==2`, `clear()` 後に `row_count==0`
- **ケース: to_table / columns の列順**  
  **入力**: `output_schema` を基準に列を追加（欠損列あり）  
  **期待**: 返却テーブルの列順が schema と一致、欠損列は `None` で補完

### writer API（unit）

- **ケース: write_parquet_columns のメタデータ継承**  
  **入力**: `{"time":[0.0], "dt":[1.0]}` を `write_parquet_columns` で保存  
  **期待**: Parquet metadata に `units`/`definitions` が付与される
- **ケース: ensure_columns の欠損補完**  
  **入力**: `ensure_columns=["time","dt","M_out_dot"]` で保存  
  **期待**: `M_out_dot` が `null` 列として作成される

### run_one_d row/columnar parity（integration）

- **ケース: Streaming OFF で row/columnar 比較**  
  **設定**: `geometry.mode=1D`, `geometry.Nr=2`, `numerics.t_end_orbits=0.02`, `numerics.dt_init=50.0`, `phase.enabled=false`, `radiation.TM_K=2000.0`, `io.streaming.enable=false`  
  **期待**:  
  - 列集合が一致（`ZERO_D_SERIES_KEYS + ONE_D_EXTRA_SERIES_KEYS`）  
  - `time`, `dt`, `M_loss_cum`, `M_out_dot` など主要列は `np.allclose(rtol=1e-12, atol=0.0)` で一致  
  - `t_coll_kernel_min` が全行で `null` ではなく、同一 `time` 内で一定
- **チェックボックス: 行順・セル順の一致（必須）**  
  - [x] `time` は昇順で一致  
  - [x] `cell_index` は同一 `time` 内で昇順かつ一致  
  - [x] `time, cell_index` の組が row/columnar で完全一致  
  **対象列**: `time`, `cell_index`
- **ケース: Streaming ON + columnar**  
  **設定**: 上記 + `io.streaming.enable=true`, `io.streaming.step_flush_interval=1`  
  **期待**: `series/run_chunk_*.parquet` が生成 → `series/run.parquet` にマージされ、列集合が row と一致
- **チェックボックス: 行順の維持（Streaming ON）**  
  - [x] `series/run.parquet` の `time, cell_index` の順序が Streaming OFF と一致  
  **対象列**: `time`, `cell_index`

### mass_budget.csv 出力（integration）

- **ケース: Streaming ON/OFF**  
  **設定**: `io.streaming.enable=true/false` を両方実行  
  **期待**: `checks/mass_budget.csv` が必ず存在し、ヘッダーを含む
- **チェックボックス: mass_budget 内容一致**  
  - [x] `time` の並びが一致  
  - [x] `error_percent`, `mass_diff`, `mass_lost` が `rtol=1e-12, atol=0.0` で一致  
  **対象列**: `time`, `error_percent`, `mass_diff`, `mass_lost`

### トグル優先順位（integration）

- **ケース: 強制 row へのフォールバック**  
  **設定**: `io.record_storage_mode=columnar` + `MARSDISK_DISABLE_COLUMNAR=1`  
  **期待**: row モードが優先され、出力スキーマが従来と一致
- **チェックボックス: 欠損表現の一致**  
  - [x] `None`/`NaN` の扱いが row と columnar で同一  
  **対象列**: `s_min`, `t_coll_kernel_min`, `sigma_tau1`（代表列）

### 0D 展開後の追加（integration, 任意）

- **ケース: run_zero_d の row/columnar 比較**  
  **設定**: 0D の小規模ケース（`t_end_years` を短く）  
  **期待**: `ZERO_D_SERIES_KEYS`/`ZERO_D_DIAGNOSTIC_KEYS` の列集合一致と主要列一致（`rtol=1e-12`）
- **チェックボックス: 行順の一致（0D）**  
  - [x] `time` は昇順で一致  
  - [x] `time` の並びが row/columnar で完全一致  
  **対象列**: `time`

### 比較基準（許容誤差）

- **数値一致**: `rtol=1e-12, atol=0.0` を基準（浮動小数誤差の範囲で完全一致を期待）
- **列順**: `output_schema` を基準に一致
- **欠損列**: `None` で補完されること（row/columnar と同等）
- **行順**: `time` / `cell_index` の順序が row/columnar で完全一致

---

## 実装タスク分割（Issue化）

- [x] **Issue A: ColumnarBuffer の基盤実装**  
  `marsdisk/runtime/history.py` に ColumnarBuffer を追加し、`__len__`/`row_count`/`clear`/`to_table` を定義。  
  受入条件: 単体テストで `row_count` と `clear` が正しく動作。

- [x] **Issue B: writer の columnar API 追加**  
  `marsdisk/io/writer.py` に `write_parquet_table` / `write_parquet_columns` を追加。  
  受入条件: units/definitions メタデータが row と一致。

- [x] **Issue C: Streaming 対応（ColumnarBuffer flush）**  
  `marsdisk/io/streaming.py` で ColumnarBuffer を判定し `to_table` 分岐を追加。  
  受入条件: Streaming ON/OFF の双方で `series/run.parquet` が生成される。

- [x] **Issue D: run_one_d の列指向化（records/diagnostics）**  
  `marsdisk/run_one_d.py` の `records` と `diagnostics` を ColumnarBuffer 化し、`t_coll_kernel_min` を一括付与。  
  受入条件: row/columnar で列集合・主要列が一致。

- [x] **Issue E: run_zero_d の列指向化（任意）**  
  `marsdisk/run_zero_d.py` の `records/diagnostics` を ColumnarBuffer 化。  
  受入条件: `ZERO_D_*` の列集合と主要列が一致。

- [x] **Issue F: 出力スキーマ整理**  
  `marsdisk/output_schema.py` の列順を基準化し、`ensure_columns` に反映。  
  受入条件: row/columnar で列順が一致。

- [x] **Issue G: テスト追加**  
  `tests/integration/test_columnar_records.py` などを追加し、row/columnar の同一性を検証。  
  受入条件: 既存の解析スクリプトが同一列名で動作する。

- **float 系**: `rtol=1e-12, atol=0.0` を基本。
- **積分・平均系**（`*_avg`, `M_loss_cum` 等）: `rtol=1e-6` まで許容。
- **bool/カテゴリ列**: `np.array_equal` で一致確認。
- **NaN 含む列**: `np.isnan` の位置一致を先に確認した上で値比較。

---

## 性能検証

- 既存の短縮ケースで **I/O ON/OFF** の A/B を実施
- `cProfile` / `pstats` で `_ensure_keys`, `writer.write_parquet` の比率を比較
- `scripts/tests/measure_case_output_size.py` で出力サイズ差を記録

---

## 検証ログ

- integration tests: `pytest tests/integration -q`  
  ログ: `out/tests/integration_20260101-002601.log`（212 passed, 3 skipped）
