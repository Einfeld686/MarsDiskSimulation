# コード整備の追加改善項目

> **作成日**: 2025-12-17  
> **関連**: [20251216_code_reorganization_for_collision_physics.md](docs/plan/20251216_code_reorganization_for_collision_physics.md)（Phase 1–3 完了済み）

---

## 背景

Phase 1–3 のコード整備が完了し、以下が達成済み:
- `CollisionStepContext` 導入
- `ProgressReporter`, `StreamingState`, `ZeroDHistory` 抽出
- テストディレクトリ再構成（`unit/`, `integration/`, `research/`, `legacy/`）
- Phase5 削除、Phase7 → `extended_diagnostics` リネーム
- Coverage guard: `function_reference_rate: 0.98`, `anchor_consistency_rate: 1.0`

本ドキュメントでは、デバッグ効率と拡張性向上のための**追加改善項目**を整理する。

---

## Open Questions（実施前に決定が必要）

| # | 質問 | 選択肢 | 推奨 |
|---|------|--------|------|
| 1 | 関数外出しで新設するパッケージ | A: `marsdisk/<utils>/` を新設 / B: 既存 `config_utils.py` 等に統合 | B（既存活用） |
| 2 | `make clean-tmp` でtarball/inventory を削除対象にするか | A: 含める / B: 成果物として保持 | B（保持） |

---

## 1. 高優先度

### 1.1 coverage holes 解消

**現状**: `analysis/coverage/coverage.json` に 2 件の未参照関数が存在

```json
"holes": [
  "marsdisk/physics/collisions_smol.py#step_collisions",
  "marsdisk/physics/radiation.py#grain_temperature_graybody"
]
```

**実施手順**:
```bash
# 1. アンカー追加
#    analysis/overview.md などの仕様ドキュメントに以下を追記
#    - marsdisk/physics/collisions_smol.py:515–547
#    - marsdisk/physics/radiation.py:120–147
#      （E記号は equations.md ではなく参照のみ）

# 2. DocSync + ドキュメントテスト + 評価システム（AGENTS.md 必須ワークフロー）
python -m tools.doc_sync_agent --all --write
make analysis-doc-tests
python -m tools.evaluation_system --outdir out/<latest-run-dir>  # 直近の run 出力を指定

# 3. カバレッジ確認
cat analysis/coverage/coverage.json | jq '.holes'
# → [] であること
```

**工数**: 15 分

---

### 1.2 `writer.py` の Phase7 コメント更新

**現状**: `marsdisk/io/writer.py` に「Phase7」コメントが 6 箇所残存（L202–204, L226–228）

**対応**: 「Phase7 diagnostics」→「extended diagnostics」に統一

**工数**: 10 分

---

## 2. 中優先度

### 2.1 `run.py` の関数数削減

**現状**: `run.py` に 29 関数、4,826 行（目標 4,000 行以下）

**パッケージ構成の現状** (新設ファイルは存在しない):
```
marsdisk/
├── runtime/
│   ├── __init__.py      # 既存: ProgressReporter, ZeroDHistory をexport
│   ├── history.py       # 既存
│   └── progress.py      # 既存
├── config_utils.py      # 既存: 設定ロード関連
└── <utils>/             # ← 未作成
```

**移動候補と配置オプション**:

| 関数群 | オプション A（新設） | オプション B（既存活用） |
|--------|---------------------|------------------------|
| `_resolve_time_grid`, `_resolve_seed` | `runtime/<config_helpers>.py` | `config_utils.py` に追加 |
| `_parse_override_value`, `_apply_overrides_dict` | `<utils>/cli.py` | `config_utils.py` に追加 |
| `_human_bytes`, `_memory_estimate` | `<utils>/format.py` | `runtime/` に追加 |
| `_ensure_finite_kappa`, `_safe_float` | `<utils>/numerics.py` | 移動せず（低優先） |

> [!IMPORTANT]
> **アンカー更新が必要**
>
> 関数を移動すると以下のファイルに影響:
> - `analysis/run_py_sections.md`: 関数行番号参照
> - `analysis/inventory.json`: 関数シンボル参照
> - `analysis/overview.md`: 可能性あり
>
> **必須ポストワークフロー**:
> ```bash
> # 移動完了後
> python -m analysis.tools.make_run_sections  # run_py_sections.md 再生成
> python -m tools.doc_sync_agent --all --write
> make analysis-doc-tests
> python -m tools.evaluation_system --outdir out/<run_id>
> ```

**工数**: 2–3 時間（アンカー更新含む）

---

### 2.2 ログレベルの統一と拡充

**現状**: `collisions_smol.py` に `logger.debug()` が 1 箇所のみ

**推奨追加**（`isEnabledFor` ガード付きで計算オーバーヘッドを回避）:
```python
# step_collisions_smol_0d 内
if logger.isEnabledFor(logging.DEBUG):
    logger.debug(
        "collision kernel: t_coll=%.3e, e=%.4f, i=%.4f",
        t_coll_kernel, e_kernel, i_kernel
    )
    logger.debug(
        "fragment tensor: shape=%s, Y_max=%.3e",
        Y_tensor.shape, float(np.max(Y_tensor))
    )
```

**工数**: 30 分

---

## 3. 低優先度

### 3.1 一時ディレクトリ・ファイルの管理

**現状**（2025-12-17 時点）:

| 種別 | パス | 扱い |
|------|------|------|
| **保持（成果物）** | `tmp_debug_backup_20251216.tar.gz` | Git外退避バックアップ、削除しない |
| **保持（記録）** | `tmp_debug_inventory.txt` | 削除前のファイルリスト、参照用に保持 |
| **削除可能** | `tmp_debug_mass_budget/`, `tmp_debug_mass_budget2/` | テスト完了後に削除 |
| **削除可能** | `tmp_debug_sampling/` | テスト完了後に削除 |
| **削除可能** | `tmp_debug_test_gate/`, `_gate2/`, `_gate3/` | テスト完了後に削除 |
| **削除可能** | `tmp_debug_test_psat/` | テスト完了後に削除 |
| **削除可能** | `tmp_eval_fixture/` | テスト完了後に削除 |

**`make clean-tmp` タスク案**:
```makefile
clean-tmp:
	@echo "Removing temporary debug directories (preserving backup tarball)..."
	rm -rf tmp_debug_mass_budget tmp_debug_mass_budget2
	rm -rf tmp_debug_sampling
	rm -rf tmp_debug_test_gate tmp_debug_test_gate2 tmp_debug_test_gate3
	rm -rf tmp_debug_test_psat
	rm -rf tmp_eval_fixture
	@echo "Preserved: tmp_debug_backup_*.tar.gz, tmp_debug_inventory.txt"
```

---

### 3.2 Numba フォールバックのテスト強化

**現状**: `_fragment_tensor` に Numba 無効時のフォールバック処理があるが、専用テストなし

**対応**: `tests/unit/test_fragment_tensor_fallback.py` を追加し、`MARSDISK_DISABLE_NUMBA=1` 環境でのテストを実施

---

### 3.3 `DEBUG_STAGE` 環境変数の整理

**現状**: `run.py:L89` に `DEBUG_STAGE = bool(int(os.environ.get("MARSDISK_DEBUG_STAGE", "0")))`

**対応**: 利用箇所を精査し、不要なら削除。必要なら使い方をドキュメント化

---

## 完了条件

### 高優先度（必須）
- [x] coverage holes が 0 件
- [x] DocSync + doc-tests + evaluation_system が全てパス
- [x] `writer.py` の Phase7 コメントが更新されている

### 中優先度（推奨）
- [x] `run.py` が 4,000 行以下
- [x] `analysis/run_py_sections.md` がリファクタ後の構造を反映
- [x] 衝突物理モジュールに `isEnabledFor` ガード付きログ出力が追加されている

### 低優先度（任意）
- [x] `make clean-tmp` タスクが追加されている
- [x] Numba フォールバックテストが追加されている

---

## 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2025-12-17 | 初版作成 |
| 2025-12-17 | ユーザー指摘反映: Open Questions 追加、DocSync ワークフロー明記、パッケージ構成現状と選択肢を詳細化、ログにisEnabledForガード追加、tmp_debug リスト最新化と削除対象明確化 |
