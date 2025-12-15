# 式↔コード対応検証機能の導入計画

> **文書種別**: 計画書（Diátaxis: How-to Guide / Implementation Plan）
> **作成日**: 2025-12-15
> **ステータス**: Draft

## 1. 背景と目的

### 問題提起

現在、`analysis/equations.md` には約45の数式定義 (E.001–E.045) が存在し、それぞれがコード参照（例: `[marsdisk/physics/surface.py#wyatt_tcoll_S1 [L65–L76]]`）を持っています。しかし、以下の問題があります：

1. **式の未実装検出**: `equations.md` に定義された式がコード内で実装されているか不明
2. **コードの未定義計算**: コード内の計算がどの式 (E.xxx) に対応するか不明
3. **参照の陳腐化**: コード変更時に式への参照が更新されない可能性
4. **乖離の検出困難**: 式の定義とコードの実装が乖離しても検出する仕組みがない

### 目標

**DocSyncAgent に式↔コード対応検証機能を追加**し、以下を自動化する：

- 式番号 (E.xxx) とコード実装の対応マッピング生成
- 未実装式 / 未定義計算の検出と報告
- 対応関係の整合性レポート生成

## 2. 現状分析

### 2.1 equations.md の構造

```markdown
### (E.006) marsdisk/physics/surface.py: surface_collisional_time
[@StrubbeChiang2006_ApJ648_652; Eq.(1)]
```latex
t_{coll} = 1 / (Ω τ_⊥)
```
**Numerics**
- [marsdisk/physics/surface.py#wyatt_tcoll_S1 [L65–L76]]
```

**パターン**:
- 式番号: `(E.xxx)` 形式
- コード参照: `[path/to/file.py#function_name [L123–L456]]` 形式
- 文献参照: `[@AuthorYear_Journal]` 形式

### 2.2 既存の DocSyncAgent 機能

| 機能 | 説明 | 式検証への応用 |
|------|------|----------------|
| `inventory.json` | シンボル一覧 | ✅ 関数の行番号取得 |
| `_rewrite_references` | 行番号同期 | ✅ 参照形式の認識 |
| `coverage.json` | カバレッジ計測 | ✅ 参照マッチング基盤 |

### 2.3 provenance_report.md の役割

`analysis/provenance_report.md` は既に「式カバレッジ」セクションを持っており、検証結果の出力先として適切です。

## 3. 提案する変更

### 3.1 新規ファイル

#### [NEW] `analysis/equation_code_map.json`

式とコードの対応を機械可読形式で保存：

```json
{
  "equations": [
    {
      "eq_id": "E.006",
      "title": "surface_collisional_time",
      "formula_latex": "t_{coll} = 1 / (Ω τ_⊥)",
      "code_refs": [
        {
          "file": "marsdisk/physics/surface.py",
          "symbol": "wyatt_tcoll_S1",
          "line_start": 65,
          "line_end": 76
        }
      ],
      "literature_refs": ["StrubbeChiang2006_ApJ648_652"],
      "status": "implemented"
    }
  ],
  "unmapped_equations": ["E.029", "E.030"],
  "unmapped_code": [
    {"file": "marsdisk/physics/radiation.py", "symbol": "some_function"}
  ],
  "stats": {
    "total_equations": 45,
    "mapped": 42,
    "unmapped": 3,
    "coverage_rate": 0.933
  }
}
```

---

### 3.2 DocSyncAgent への機能追加

#### [MODIFY] `marsdisk/ops/doc_sync_agent.py`

**追加する関数/クラス**:

1. `parse_equations_md(path: Path) -> list[EquationEntry]`
   - `equations.md` をパースして式定義を抽出
   - 正規表現で式番号、LaTeX、コード参照を抽出

2. `extract_code_equation_refs(symbols: list[SymbolInfo]) -> dict[str, list[str]]`
   - コード内の `@ref E.xxx` コメントを検出（新規フォーマット提案）
   - 既存のdocstringから式参照を抽出

3. `compute_equation_coverage(equations, code_refs) -> EquationCoverage`
   - 式とコードの対応を計算
   - 未実装/未定義を検出

4. `_cmd_equations(args) -> int`
   - `python -m tools.doc_sync_agent equations` サブコマンド
   - JSON レポートと Markdown レポートを生成

---

### 3.3 equations.md への注釈強化

現在の参照形式を維持しつつ、検証しやすくするための軽微な整備：

```markdown
### (E.006) t_coll — 表層衝突時間
<!-- eq_status: implemented -->
<!-- primary_impl: marsdisk/physics/surface.py#wyatt_tcoll_S1 -->
```

## 4. 実装詳細

### 4.1 式パーサー

```python
EQUATION_ID_PATTERN = re.compile(r"^### \(E\.(\d{3})\)")
CODE_REF_PATTERN = re.compile(
    r"\[(marsdisk/[^\]]+\.py)#([A-Za-z0-9_]+)\s+\[L(\d+)–L?(\d+)?\]\]"
)

@dataclass
class EquationEntry:
    eq_id: str  # "E.006"
    title: str
    code_refs: list[CodeRef]
    literature_refs: list[str]
    latex: str | None = None
```

### 4.2 検証ロジック

```python
def verify_equation_code_mapping(
    equations: list[EquationEntry],
    inventory: list[InventoryRecord],
) -> VerificationResult:
    """
    1. 各式のcode_refsがinventoryに存在するか確認
    2. 行番号範囲が正しいシンボルを指しているか確認
    3. inventoryの関数がいずれかの式から参照されているか確認
    """
```

### 4.3 出力形式

#### analysis/equation_code_map.json

```json
{
  "generated_at": "2025-12-15T15:45:00+09:00",
  "equations": [...],
  "verification": {
    "passed": true,
    "warnings": ["E.029: no code reference found"],
    "errors": []
  }
}
```

#### analysis/provenance_report.md への追記

```markdown
## 式カバレッジ

| Metric | Value |
|--------|-------|
| 定義済み式 | 45 |
| 実装済み | 42 (93.3%) |
| 未実装 | 3 |

### 未実装の式
- (E.029): placeholder — 実装待ち
- (E.030): placeholder — 実装待ち
```

## 5. 検証計画

### 5.1 自動テスト

#### 既存テストの拡張: `tests/test_doc_sync_agent.py`

```python
def test_equation_parsing():
    """equations.md から式定義を正しく抽出できることを確認"""
    
def test_equation_code_mapping():
    """式とコードの対応マッピングが正しく生成されることを確認"""
    
def test_equation_coverage_report():
    """カバレッジレポートが正しく生成されることを確認"""
```

**実行コマンド**:
```bash
pytest tests/test_doc_sync_agent.py -v -k equation
```

### 5.2 統合テスト

```bash
# 式検証を実行
python -m tools.doc_sync_agent equations --write

# 出力ファイルを確認
cat analysis/equation_code_map.json | jq '.stats'
```

### 5.3 手動検証

1. `analysis/equation_code_map.json` が生成されること
2. JSON に `unmapped_equations` が正しく列挙されること
3. `make analysis-update` が引き続き正常動作すること

## 6. 段階的導入

### Phase 1: パーサーと基本マッピング（工数: 1日）
- `equations.md` パーサー実装
- `equation_code_map.json` 生成機能
- 基本テスト追加

### Phase 2: 検証とレポート（工数: 0.5日）
- 未実装/未定義の検出
- `provenance_report.md` への自動追記
- CI統合（`make analysis-update` に追加）

### Phase 3: コード側注釈（オプション、工数: 1日）
- コード内 `# @ref E.xxx` 注釈の検出
- 双方向マッピングの完成

## 7. リスクと緩和策

| リスク | 影響 | 緩和策 |
|--------|------|--------|
| equations.md の形式変更 | パーサー破損 | 形式を固定し、テストでカバー |
| 大量の未実装警告 | ノイズ増加 | `<!-- eq_status: placeholder -->` で抑制 |
| 既存ワークフロー干渉 | CI失敗 | 警告のみで失敗にしない |

## 8. 成功指標

- [ ] `equation_code_map.json` が自動生成される
- [ ] 未実装式が3件以下に減少
- [ ] `make analysis-update` の実行時間増加が1秒以下
- [ ] 全テストが合格

---

## 変更ファイルまとめ

| ファイル | 変更種別 | 説明 |
|----------|----------|------|
| `marsdisk/ops/doc_sync_agent.py` | MODIFY | 式パーサーと検証ロジック追加 |
| `analysis/equation_code_map.json` | NEW | 式↔コード対応マップ |
| `tests/test_doc_sync_agent.py` | MODIFY | 式検証テスト追加 |
| `Makefile` | MODIFY | `analysis-update` に equations ステップ追加 |
