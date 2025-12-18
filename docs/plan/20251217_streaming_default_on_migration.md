# ストリーミング既定 ON への移行とテスト時の明示 OFF

> **作成日**: 2025-12-17  
> **関連計画**: [20251216_code_reorganization_for_collision_physics.md](./20251216_code_reorganization_for_collision_physics.md)

---

## 目的

重いスイープでの OOM を避けつつ、テスト/軽量ケースでは明示 OFF で I/O オーバーヘッドとファイル依存を抑える運用に整理する。

---

## 必要な実装セット

### Config/スキーマ

`io.streaming.enable` の既定値を `true` に変更し、以下の安全デフォルトを明記：

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `memory_limit_gb` | 10 | ストリーミング時のメモリ上限 |
| `step_flush_interval` | 10000 | フラッシュ間隔 |
| `merge_at_end` | true | 終了時にマージを実行 |

### ランタイム

ストリーミング有効でも `checks/mass_budget.csv` を最終マージ後に必ず書き出すように `run_zero_d` を修正。

> [!IMPORTANT]
> 現状 `streaming=true` で `mass_budget` をスキップする分岐があるため、これを削除または条件変更する必要がある。

### ドキュメント

以下のドキュメントに「既定 ON・テスト時は明示 OFF」とデフォルト値・切替手順を追記：

- `analysis/overview.md`
- `analysis/run-recipes.md`
- `AGENTS.md`

### テスト更新

`mass_budget` 出力や I/O 依存の期待値を streaming 前提に見直し、必要ならフィクスチャで `io.streaming.enable=false` を適用。

---

## テスト時に OFF を強制するパターン（併用可）

| パターン | 実装方法 | 適用場面 |
|----------|----------|----------|
| **pytest fixture** | `tests/conftest.py` で `STREAMING_OVERRIDES = {"io.streaming.enable": False}` を共通オーバーライド適用 | 単体テスト全般 |
| **pytest オプション** | `pytest --no-streaming` → `FORCE_STREAMING_OFF=1` を `run_zero_d` 側で最優先で OFF | CI 実行時 |
| **テンプレート設定** | `configs/test_defaults.yml` を用意し、`io.streaming.enable: false` を含める | ドキュメント系/小規模テスト |
| **CI/Make 固定** | `IO_STREAMING=off make test` で CI 実行時は強制 OFF | CI パイプライン |

---

## 逃げ道

ローカルの遅い/容量不足ストレージ向けに、環境変数 `FORCE_STREAMING_OFF=1` を実装して明示 OFF できるようにする（既定 ON でも緊急時に切れる）。

---

## 実施ステップ

1. [ ] `schema.py` で `io.streaming.enable` のデフォルトを `true` に変更
2. [ ] `run.py` の `mass_budget` スキップ分岐を修正
3. [ ] `tests/conftest.py` に fixture 追加
4. [ ] ドキュメント（`analysis/overview.md`, `analysis/run-recipes.md`, `AGENTS.md`）を更新
5. [ ] 全テスト通過を確認

---

## 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2025-12-17 | 初版作成（`20251216_code_reorganization_for_collision_physics.md` の付録から分離） |
