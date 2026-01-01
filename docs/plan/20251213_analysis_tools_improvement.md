# Analysis Tools Improvement

analysis 自動更新ツール群を整理し、現行ワークフローとの整合性を高める。

## 背景

ツール移動の名残で多段 shim が残存し、`reference_tracker` や `UNKNOWN_REF_REQUESTS` との連携が未統合。`make analysis-update` の定義も `AGENTS.md` の意図と完全には一致していない。

---

## User Review Required

> [!IMPORTANT]
> **Phase 1 変更**: shim は**削除せず維持**します。`python -m tools.doc_sync_agent` は既存 CI・AGENTS.md・AI_USAGE.md で標準パスとして使用されており、互換性を保ちます。

> [!WARNING]
> **UNKNOWN_REF_REQUESTS**: 既存の未解決 slug があるため、CI fail-fast ではなく **warn-only** をデフォルトとします。将来的に `--strict` オプションで exit 1 化する余地を残します。

---

## Proposed Changes

### Phase 1: Shim 維持・整理

#### 変更なし（shim 維持）

- `tools/doc_sync_agent.py` → `tools/pipeline/doc_sync_agent.py` → `marsdisk/ops/doc_sync_agent.py` の経路を**維持**
- `tools/coverage_guard.py` → `tools/pipeline/coverage_guard.py` も同様に維持
- `pyproject.toml` は存在しないため変更不要（requirements.txt 運用継続）

#### [MODIFY] [doc_sync_agent.py](tools/pipeline/doc_sync_agent.py)

docstring を更新し、この shim が意図的に残されていることを明記：

```python
"""互換性のための薄いラッパー。

実体は ``marsdisk.ops.doc_sync_agent`` に移動済み。
このファイルは tools/doc_sync_agent.py および AGENTS.md 標準手順
(python -m tools.doc_sync_agent) からの呼び出しを維持するために残す。
"""
```

---

### Phase 2: Makefile 整備（AGENTS.md 完全準拠）

#### [MODIFY] [Makefile](Makefile)

現行:
```makefile
analysis-update: analysis-pipeline
```

提案（AGENTS.md 手順を完全反映）:
```makefile
# AGENTS.md: DocSync → doc-tests → evaluation_system
analysis-update: analysis-sync
	python analysis/tools/make_coverage.py
	python -m tools.coverage_guard
	python tools/run_analysis_doc_tests.py
	@echo "[analysis-update] evaluation_system requires --outdir; run manually:"
	@echo "  python -m tools.evaluation_system --outdir <run_dir>"
```

> [!NOTE]
> `evaluation_system` は `--outdir` が必須のため自動実行せず、手動実行を促すメッセージを表示。直近の out/ パスが必要なため。

代替案（OUTDIR 変数使用）:
```makefile
analysis-update: analysis-sync
	python analysis/tools/make_coverage.py
	python -m tools.coverage_guard
	python tools/run_analysis_doc_tests.py
ifdef OUTDIR
	python -m tools.evaluation_system --outdir $(OUTDIR)
endif
```

---

### Phase 3: Reference Tracker（任意・標準フロー外）

#### [MODIFY] [Makefile](Makefile)

```makefile
# 任意: 参照レジストリとの差分検出（標準フローには含まない）
analysis-refs:
	python tools/reference_tracker.py --validate
```

> [!NOTE]
> `analysis-refs` は `analysis-update` の依存に**含めない**。論文準備時など必要に応じて個別実行する位置づけ。

---

### Phase 4: UNKNOWN_REF_REQUESTS 検証（warn-only）

#### [NEW] [check_unknown_refs.py](tools/check_unknown_refs.py)

```python
#!/usr/bin/env python3
"""Report pending UNKNOWN_REF_REQUESTS entries (warn-only by default)."""
import argparse
import json
from pathlib import Path

REQUESTS_PATH = Path("analysis/UNKNOWN_REF_REQUESTS.jsonl")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 if pending requests exist")
    args = parser.parse_args()

    if not REQUESTS_PATH.exists():
        print("No analysis/UNKNOWN_REF_REQUESTS.jsonl found.")
        return 0

    entries = [json.loads(line) for line in REQUESTS_PATH.read_text().splitlines() if line.strip()]
    pending = [e for e in entries if not e.get("resolved")]

    if pending:
        print(f"[WARN] Pending reference requests: {len(pending)}")
        for e in pending[:5]:
            print(f"  - {e.get('slug')}: {e.get('type')}")
        if args.strict:
            return 1
    else:
        print("All reference requests resolved.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

#### [MODIFY] [Makefile](Makefile)

```makefile
# 任意: 未解決参照リクエストの確認（warn-only, 標準フロー外）
analysis-unknown-refs:
	python tools/check_unknown_refs.py

# --strict で CI fail-fast にする場合
analysis-unknown-refs-strict:
	python tools/check_unknown_refs.py --strict
```

---

## フロー整理

| ターゲット | 用途 | 標準フロー |
|-----------|------|-----------|
| `analysis-sync` | DocSync + assumptions | ✅ |
| `analysis-update` | sync + coverage + guard + doc-tests | ✅ (evaluation_system は手動) |
| `analysis-refs` | reference_tracker 差分検出 | ❌ (任意) |
| `analysis-unknown-refs` | UNKNOWN_REF 件数報告 | ❌ (任意, warn-only) |
| `analysis-unknown-refs-strict` | 同上 + fail-fast | ❌ (CI 導入時に検討) |

---

## Verification Plan

### Automated Tests

```bash
# Phase 2 完了後
make analysis-update   # 成功終了 + evaluation_system 手動実行メッセージ表示

# Phase 3 完了後
make analysis-refs     # 差分ゼロまたは期待通りの警告

# Phase 4 完了後
make analysis-unknown-refs        # pending 件数表示 + exit 0
make analysis-unknown-refs-strict # pending あれば exit 1
```

### Manual Verification

- `python -m tools.doc_sync_agent --help` が引き続き動作することを確認
- `AGENTS.md` と Makefile ターゲットのドキュメント一致を目視チェック
