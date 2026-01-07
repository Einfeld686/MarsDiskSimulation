# シミュレーションコードの保守性分析レポート

ステータス: 調査完了・提案

本レポートは、`marsdisk/` パッケージの保守性に関する問題点を網羅的に調査した結果をまとめたものです。

スナップショット: 2026-01-02 20:38 (commit f056463fa, branch=main, dirty=true, TZ=JST)

計測ルール（固定）:
- 行数は `def` 開始〜次の `def` 直前までを1関数として数える
- 行数/サイズは `wc -l` / `wc -c` を使用
- deprecated 件数は `rg -n "deprecated" marsdisk | wc -l`（指摘数であり警告発火数ではない）
- テスト構造は `find tests/<dir> -type f | wc -l`

スナップショット更新:
- `python -m tools.maintainability_snapshot --plan docs/plan/20260102_maintainability_analysis.md`
- `python -m tools.maintainability_snapshot --plan docs/plan/20260102_maintainability_analysis.md --check`
- `python -m tools.maintainability_snapshot --plan docs/plan/20260102_maintainability_analysis.md --dry-run`

更新時の注意点:
- 見出しや表の文言を変える場合は、先にスクリプト側の検出条件を合わせる
- 手動更新は避け、`--check` で差分確認 → 更新 の順で運用する
- git/rg が使えない環境では記録が `unknown` になり得るため、結果を再確認する

---

## 🔴 重大な問題（High Priority）

### 1. 巨大なモノリシック関数

| ファイル | 関数名 | 行数 | 問題 |
|---------|-------|------|------|
| `run_zero_d.py` | `run_zero_d()` | **4,669行** (L843–L5511) | 1つの関数が5000行近く。テスト・デバッグ・拡張が極めて困難 |
| `run_one_d.py` | `run_one_d()` | **2,741行** (L214–L2954) | 同様にモノリシック |

> [!CAUTION]
> これらの関数は循環的複雑度（Cyclomatic Complexity）が非常に高い可能性があるため、次回スナップショットで `radon cc` 等により計測を行う。

**推奨対策:**
- フェーズごとの処理を独立した関数/クラスに分離
- State管理パターン（既存の `OrchestrationContext` など）の活用拡大
- 内部ヘルパー関数のモジュール外への切り出し
- 分割後のゴール: `run_zero_d`/`run_one_d` の本体をそれぞれ 1,500 行以下に縮小

---

### 2. 0D/1D ランナー間のコード重複

`run_zero_d.py` と `run_one_d.py` の間で、同一または非常に類似したコードが多数存在しています:

| 重複項目 | run_zero_d.py | run_one_d.py |
|---------|---------------|--------------|
| 定数定義 | L91-99 | L65-73 |
| `_auto_chi_blow()` | L427-439 | L140-152 |
| `_resolve_los_factor()` | L372-385 | L110-123 |
| `_series_stats()` | L4296-4305 | L2593-2599 |
| `MassBudgetViolationError` | L499-500 | L76-77 |

**影響:**
- バグ修正が両方に適用されないリスク
- 機能追加時の作業量が倍増
- テストの重複

**推奨対策:**
- 共通ロジックを `orchestrator.py` などの共通モジュールへ集約（新設予定の core 層を含む）
- 差異がある部分のみをランナー固有コードに残す
- 重複率の定量化を導入（例: `jscpd` を用い、重複率 ≤ 10% を目標）
- 受入条件（責務境界）: 0D/1D の入出力整形・可視化・I/O はランナー側に残し、物理ステップと時間積分ロジックのみを共通化する

---

### 3. 定数の重複定義（DRY違反）

`constants.py` が存在するにもかかわらず、重要な定数が複数ファイルで再定義されています:

#### `SECONDS_PER_YEAR`（5+ファイルで定義）
```
marsdisk/run_zero_d.py:91    → 365.25 * 24 * 3600.0
marsdisk/run_one_d.py:65     → 365.25 * 24 * 3600.0
marsdisk/orchestrator.py:66  → 365.25 * 24 * 3600.0
marsdisk/physics/supply.py:25 → 365.25 * 24 * 3600.0
marsdisk/physics/tempdriver.py:35 → 365.25 * SECONDS_PER_DAY
marsdisk/runtime/progress.py:10   → 365.25 * 24 * 3600.0
```

#### `MAX_STEPS`（3ファイルで定義）
```
marsdisk/run_zero_d.py:92    → 50000000
marsdisk/run_one_d.py:66     → 50_000_000
marsdisk/orchestrator.py:67  → 50_000_000
```

> [!WARNING]
> 値が異なる書式（`50000000` vs `50_000_000`）で定義されており、将来的な不整合のリスクがあります。

**推奨対策:**
- `constants.py` に `SECONDS_PER_YEAR` と `MAX_STEPS` を追加
- 他のファイルからは `from .constants import SECONDS_PER_YEAR, MAX_STEPS` でインポート
- `run_zero_d` の `_get_max_steps` による上書き互換は維持し、移行期は `constants.MAX_STEPS` を既定値として扱う

---

## 🟡 中程度の問題（Medium Priority）

### 4. 巨大なスキーマファイル

| ファイル | 行数 | クラス数 | 問題 |
|---------|------|---------|------|
| `schema.py` | 2,268行 | 61クラス | 単一ファイルに全設定モデルが集中 |

**推奨対策:**
- ドメインごとにスキーマを分割（例: `schema/supply.py`, `schema/physics.py`, `schema/io.py`）
- `schema/__init__.py` で再エクスポートして後方互換性を維持
- 受入条件: 既存の import パスを壊さず、Pydantic の JSON schema 生成が同一であること

---

### 5. 非推奨（Deprecated）APIの蓄積

deprecated 指摘は 25 件でした（`rg -n "deprecated" marsdisk | wc -l`）:

#### schema.py内の deprecated 項目
- `temps.T_M` → `radiation.TM_K` へ移行推奨（L583-586）
- `supply.mixing.mu` エイリアス（L176）
- 多数の `non-default is deprecated` 警告（L335, L359, L402, L483, L506, L511, L515, L519, L523, L529）

#### 他モジュールの deprecated 項目
- `compute_s_min_F2()` in `fragments.py:254`
- `surface_ode solver` in `surface.py:70`（2026-06以降削除予定）
- `e_profile.mode='off'/'table'` in `eccentricity.py`
- `v_rel_mode='ohtsuki'` in `collisions_smol.py:1264`

**推奨対策:**
- 明確な deprecation スケジュールを文書化（docs/plan 配下に plan を新設）
- 削除予定日を過ぎた deprecated コードの削除
- 移行ガイドの作成
- テンプレ: 対象/代替/削除日/影響範囲/検証手順 を必須項目にする

---

### 6. run_zero_d.py内の deprecated 検出ロジックの肥大化

`run_zero_d.py` の L1647-1749 付近に、100行以上の deprecated 設定検出コードが存在します。

**推奨対策:**
- 検出ロジックを専用モジュール（例: deprecation checker）に分離
- 宣言的な定義（設定キー→メッセージのマッピング）に変更
- 受入条件: 既存警告メッセージが 1:1 で保持されること

---

## 🟢 軽度の問題（Low Priority）

### 7. 物理モジュールの行数

| ファイル | 行数 | コメント |
|---------|------|---------|
| `collisions_smol.py` | 1,528行 | キャッシュ管理と衝突計算の分離を検討 |
| `sublimation.py` | 733行 | 適正範囲内 |
| `tempdriver.py` | 606行 | 適正範囲内 |
| `supply.py` | 546行 | 適正範囲内 |
| `psd.py` | 663行 | 適正範囲内 |

---

### 8. テスト構造

テストディレクトリは適切に構造化されています:
```
tests/
├── integration/  (164ファイル)
├── unit/         (67ファイル)
├── research/     (6ファイル)
├── legacy/       (2ファイル)
└── conftest.py
```

ただし、モノリシック関数（`run_zero_d`, `run_one_d`）の単体テストは困難な状態です。

補足:
- テスト数は品質指標ではないため、カバレッジや重要経路の通過率を別途追跡する

---

## 📋 優先順位付きアクションプラン

| 優先度 | 項目 | 推定工数 | 影響範囲 |
|-------|------|---------|---------|
| 🔴 1 | `run_zero_d.py` の分割 | 大（3-5日） | 高 |
| 🔴 2 | 0D/1D共通ロジックの抽出 | 大（2-3日） | 高 |
| 🔴 3 | 定数の集約（`constants.py`） | 小（2-4時間） | 中 |
| 🟡 4 | deprecated コード整理 | 中（1-2日） | 中 |
| 🟡 5 | `schema.py` の分割 | 中（1日） | 中 |
| 🟢 6 | `collisions_smol.py` の分割 | 中（1日） | 低 |
| 🟢 7 | 定量スナップショットの自動更新（`tools/maintainability_snapshot.py`） | 小（半日） | 低 |
| 🟢 8 | 複雑度/重複率の計測導入（radon/jscpd） | 小（半日） | 低 |

着手順（確定）:
1. ⑦スナップショット自動化 → ⑧計測導入
2. ③定数集約 → ②共通ロジック抽出
3. ④ deprecation 整理 → ①関数分割（互換維持のため）
4. ⑤ schema 分割 → ⑥ collisions_smol 分割

成功条件（最小セット）:
- `run_zero_d`/`run_one_d` の本体行数 ≤ 1,500 行
- 重複率 ≤ 10%（jscpd）
- deprecated 指摘数を 45 → 10 以下に削減
- CI で主要シナリオの回帰がないこと（既存テスト + 追加の smoke テスト）
- 分割前の回帰検出: 軽量設定（`configs/maintainability_regression.yml`, `t_end_years=0.0001`）の `summary.json` 主要キー（`M_loss`, `case_status`, `mass_budget_max_error_percent`）が一致すること

実装時の注意点:
- ドキュメントの表記変更はスクリプト更新条件と同期し、`--check` → 更新 → `--check` の順で運用する
- 0D/1D の入出力整形・可視化・I/O をランナー側に残し、物理ステップと時間積分のみを共通化する
- 分割前後で `configs/maintainability_regression.yml` の `summary.json` 主要キー一致を検証し、軽量実行では `IO_STREAMING=off` を併用する
- `run_zero_d` の `_get_max_steps` 上書き互換は維持し、定数集約で挙動を変えない
- deprecation は移行ガイドと期限設定を先に固め、利用中の設定を誤って削除しない
- `schema.py` 分割後も JSON schema の一致を確認し、再エクスポートで import 互換を維持する
- `radon`/`jscpd` は初回は非ブロックで導入し、基準値を記録してから閾値を調整する

run_zero_d 分割手順（フェーズ抽出）:
- 既存の軽量回帰ベースライン（`configs/maintainability_regression.yml`）で `summary.json` 主要キーを固定し、比較元を確定する
- `run_zero_d` のフェーズ境界を棚卸し（設定解決/初期化/ループ内1ステップ/出力集計/後処理）し、抽出対象を明示する
- 抽出関数の入出力（context/state）を最小化して固定し、`ZeroDHistory`/`StreamingState` を再利用してデータ契約を維持する
- まず副作用の少ない初期化フェーズから関数化し、`run_zero_d` は orchestration に寄せる
- 各フェーズ抽出ごとに軽量回帰を実行し、主要キー一致を確認してから次の抽出に進む
- 最終的に `summary.json`/`run_card.md`/`series` の互換性を再確認し、必要ならチェック項目を追加する

run_zero_d フェーズ境界（タスク化）:
- [x] 設定解決と実行前準備: config source/outdir、run_config の pre_run、physics_mode/スコープ解決、qstar 設定、放射キャッシュ初期化（`[stage] config_resolved`）
- [x] 力学初期条件: 参照半径・Ω・t_orb、e/i の再評価とサンプリング、e/i mode の分岐
- [x] 放射/温度ドライバ準備: Q_pr テーブル解決、温度テーブル自動生成、温度ドライバ確定（`[stage] temperature_driver_ready`）
- [x] 遮蔽/位相/昇華セットアップ: shielding/LOS/phi、SublimationParams、phase evaluator、tau gate 設定
- [x] PSD 初期化: s_min/a_blow 計算、PSD 状態生成、初期質量分配（`[stage] psd_init`）
- [x] 供給/輸送初期化: supply spec/runtime state、reservoir/feedback/transport の初期化（`[stage] supply_ready`）
- [x] 数値時間グリッド準備: dt/n_steps 決定、StreamingState/History/Progress 初期化（`[stage] time_grid_ready`）
- [x] 時間発展ループ: 放射・位相・昇華・供給・衝突/表層の更新、質量収支/診断、ストリーミング flush
- [x] 後処理/出力: ストリーミング merge、rollup 補完、summary/run_card/energy/mass_budget 出力、アーカイブ

計測値（初回）:
- 計測コマンド: `python -m tools.maintainability_metrics`
- jscpd: duplication 4.1%（33361/813687 lines, ignore: .venv と tmp_debug/agent_test（out 配下））
- radon: avg_complexity 7.22, max_complexity 914, grade_counts A=506/B=144/C=69/D=12/E=8/F=5
- 非ブロック運用（暫定閾値）: jscpd duplication ≤ 10%、radon avg_complexity ≤ 10（B相当）

実装タスク（チェックリスト）:
- [x] スナップショット更新フローを `--check` → 更新 → `--check` で固定し、運用手順を明文化する
- [x] `radon`/`jscpd` を導入して初回計測値を取得し、非ブロック運用・閾値を記録する
- [x] `SECONDS_PER_YEAR` / `MAX_STEPS` を `constants.py` に集約し、参照統一と互換維持を実装する
- [x] 0D/1D 共通ロジックの候補を棚卸しし、受入条件（責務境界）に沿って抽出する
- [x] deprecation スケジュールと移行ガイドを整備し、期限超過の削除まで完了する
- [x] 回帰検出用の軽量設定 `configs/maintainability_regression.yml` を追加する
- [x] baseline 回帰検出（`configs/maintainability_regression.yml` の `summary.json` 主要キー一致）を実行し、`run_zero_d` の分割前後で結果が一致することを確認する
  - 実行: `out/` 配下の `20260102-1914_maint_regression__f056463fa__seed0`（IO_STREAMING=off、`M_loss=1.2889e-08`, `case_status=ok`, `mass_budget_max_error_percent=3.69e-14`）
  - 実行: `out/` 配下の `20260102-2354_maint_regression__f056463fa__seed0`（IO_STREAMING=off、series/diagnostics は既存オフ基準と一致）
  - 実行: `out/` 配下の `20260103-0017_maint_regression__f056463fa__seed0`（IO_STREAMING=off、summary の差分は streaming のみ、series/diagnostics は既存オフ基準と一致）
- [x] ストリーミング回帰の基準受理: `out/` 配下の `20260102-2241_maint_regression_stream__f056463fa__seed0` を基準結果として扱う合意を記録する
  - 実行: `out/` 配下の `20260102-2355_maint_regression_stream__f056463fa__seed0`（IO_STREAMING=on、summary 主要キー一致）
  - series/diagnostics: `out/` 配下の `20260102-1914_maint_regression__f056463fa__seed0` と比較して差分なし
  - 実行: `out/` 配下の `20260103-0017_maint_regression_stream__f056463fa__seed0`（IO_STREAMING=on、summary/series/diagnostics は既存オフ基準と一致）
- [ ] `run_one_d` をフェーズ単位で分割し、回帰検出を通す
- [ ] `schema.py` を分割し、再エクスポート互換と JSON schema 一致を確認する
- [ ] `collisions_smol.py` を分割し、キャッシュ管理と衝突計算を分離する

---

## 付録: ファイルサイズ一覧

```
marsdisk/
├── run_zero_d.py      266,196 bytes (5,673 lines) ⚠️
├── run_one_d.py       152,690 bytes (2,957 lines) ⚠️
├── schema.py           83,703 bytes (2,268 lines) ⚠️
├── physics/
│   ├── collisions_smol.py  56,067 bytes (1,528 lines)
│   ├── sublimation.py      28,204 bytes (733 lines)
│   ├── psd.py              23,725 bytes (663 lines)
│   ├── supply.py           22,335 bytes (546 lines)
│   └── ...
├── orchestrator.py     19,989 bytes (601 lines)
├── io/
│   ├── writer.py       31,357 bytes (580 lines)
│   ├── archive.py      22,351 bytes (663 lines)
│   └── ...
└── constants.py         1,766 bytes (61 lines)
```
