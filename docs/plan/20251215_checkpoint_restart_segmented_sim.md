# チェックポイント・リスタート機能：セグメント分割シミュレーション

> 作成日: 2025-12-15  
> **ステータス**: 実装完了（2026-01-01更新）  
> 区分: 機能追加提案（長時間シミュレーションのメモリ問題解決）

## 実装完了状況

以下の主要機能が `marsdisk/runtime/checkpoint.py` および関連モジュールに実装済み：

- ✅ `CheckpointState` dataclass: シミュレーション状態の保存構造
- ✅ `save_checkpoint()`: 状態のファイル保存
- ✅ `load_checkpoint()`: 状態の復元
- ✅ `list_checkpoints()`: チェックポイント一覧取得
- ✅ `cleanup_old_checkpoints()`: 古いチェックポイントの削除（keep_last_n サポート）
- ✅ `run_zero_d.py` へのリスタート機能統合
- ✅ スクリプト（run_sweep.cmd, run_temp_supply_sweep.cmd）での `numerics.resume.*` オーバーライド対応

---

## 本プロジェクト・ドキュメントについて

### プロジェクト概要

本リポジトリ（MarsDiskSimulation / `marsshearingsheet`）は、**火星ロッシュ限界内の高密度ダストディスク**を対象に、放射圧によるブローアウトと衝突破砕カスケードをシミュレーションして質量損失・流出率を定量化するものです。詳細は以下を参照してください：

- **全体仕様**: [analysis/overview.md](../../analysis/overview.md)
- **物理モデル式**: [analysis/equations.md](../../analysis/equations.md)
- **実行レシピ**: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- **AI向け利用ガイド**: [analysis/AI_USAGE.md](../../analysis/AI_USAGE.md)

### 用語定義

| 用語 | 意味 | 参考 |
|------|------|------|
| **チェックポイント** | シミュレーション状態をファイルに保存し、後から再開可能にする仕組み | — |
| **セグメント分割** | 長時間シミュレーションを複数の短い区間に分けて実行する手法 | — |
| `sigma_surf` | 表面密度 [kg m⁻²] | — |
| `psd_state` | 粒径分布の状態（ビンサイズ、数密度等） | — |
| `run_zero_d()` | メインのシミュレーションドライバー関数 | [run.py](../../marsdisk/run.py) |

---

## 背景と目的

### 問題点

`run_temp_supply_sweep.sh` の実行時に以下のエラーが発生：

```
[mem est] run_rows=15,778,800 psd_rows=631,152,000 ... total~220.4 GB
```

原因：
- `dt_init=20` 秒という小さなタイムステップ
- `t_end_until_temperature_K=1000` という長い終了条件（数年〜数十年）
- 結果として約**1,580万ステップ**になり、メモリ要件が220GB超

現在のアーキテクチャでは全ステップを一度に実行する必要があり、メモリ不足やハングの原因となっている。

### 提案

シミュレーションをセグメント（例: 1年ごと）に分割し、各セグメント終了時に状態を保存、次のセグメントで再開する機能を追加する。

**メリット**:
1. メモリ使用量の大幅削減（セグメントごとにデータをフラッシュ）
2. 長時間シミュレーションの信頼性向上（クラッシュからの復旧が可能）
3. 進捗の可視化と中断・再開のサポート

---

## 変更点

### 設定追加

```yaml
numerics:
  checkpoint:
    enabled: true                    # チェックポイント機能の有効化
    interval_years: 1.0              # 保存間隔（年単位）
    path: "{outdir}/checkpoints"     # 保存先ディレクトリ
    format: json                      # json または pickle
    keep_last_n: 3                    # 保持するチェックポイント数（古いものは削除）
  
  resume:
    enabled: false                   # リスタート機能の有効化
    from_path: null                  # チェックポイントファイルパス
```

### チェックポイントに保存する状態

| 変数名 | 型 | 説明 |
|--------|-----|------|
| `sigma_surf` | float | 現在の表面密度 |
| `sigma_deep` | float | 深部密度（deep_mixing使用時） |
| `psd_state` | dict | 粒径分布の完全な状態 |
| `time` | float | 現在のシミュレーション時刻 [s] |
| `step_no` | int | 現在のステップ番号 |
| `M_loss_cum` | float | 累積質量損失 |
| `mass_lost_by_blowout` | float | ブローアウトによる累積損失 |
| `mass_lost_by_sinks` | float | シンクによる累積損失 |
| `supply_state` | dict | 供給システムの状態（リザーバ残量等） |
| `T_M_current` | float | 現在の火星温度 |
| `rng_state` | bytes | 乱数生成器の状態（再現性確保） |

### 実装詳細

#### 1. 新規モジュール: `marsdisk/io/checkpoint.py`

```python
def save_checkpoint(path: Path, state: CheckpointState) -> None:
    """シミュレーション状態をファイルに保存"""
    
def load_checkpoint(path: Path) -> CheckpointState:
    """チェックポイントから状態を復元"""
    
def find_latest_checkpoint(dir: Path) -> Optional[Path]:
    """最新のチェックポイントファイルを検索"""

@dataclass
class CheckpointState:
    """チェックポイントに保存する状態の定義"""
    sigma_surf: float
    sigma_deep: float
    psd_state: Dict[str, Any]
    time: float
    step_no: int
    # ... その他の状態変数
```

#### 2. `run_zero_d()` への統合

| 箇所 | 変更内容 |
|------|----------|
| 関数シグネチャ | `resume_from: Optional[Path] = None` パラメータ追加 |
| 初期化 | `resume_from` がある場合はチェックポイントから状態を復元 |
| メインループ | `checkpoint.interval_years` ごとに状態を保存 |
| ストリーミング | チェックポイントと併用可能（独立した仕組み） |

#### 3. スキーマ拡張: `marsdisk/schema.py`

```python
class CheckpointConfig(BaseModel):
    enabled: bool = False
    interval_years: float = 1.0
    path: Optional[str] = None
    format: Literal["json", "pickle"] = "json"
    keep_last_n: int = 3

class ResumeConfig(BaseModel):
    enabled: bool = False
    from_path: Optional[str] = None
```

#### 4. CLI拡張

```bash
# 通常実行（チェックポイント有効）
python -m marsdisk.run --config config.yml \
    --override numerics.checkpoint.enabled=true \
    --override numerics.checkpoint.interval_years=0.5

# リスタート実行
python -m marsdisk.run --config config.yml \
    --resume-from out/run_001/checkpoints/checkpoint_step_500000.json
```

---

## テスト計画

### 自動テスト

新規テストファイル: `tests/test_checkpoint_restart.py`

| テスト名 | 検証内容 |
|----------|----------|
| `test_checkpoint_save_load` | 状態の保存・復元が正確に行われること |
| `test_resume_continues_correctly` | リスタート後のシミュレーションが連続実行と同じ結果になること |
| `test_checkpoint_interval` | 指定した間隔でチェックポイントが作成されること |
| `test_keep_last_n` | 古いチェックポイントが自動削除されること |
| `test_mass_budget_across_restart` | リスタート前後で質量収支が維持されること |

**実行コマンド**:
```bash
pytest tests/test_checkpoint_restart.py -v
```

### 統合テスト

`run_temp_supply_sweep.sh` の軽量版で検証：

```bash
# 短時間テスト（30日分を2セグメントに分割）
COOL_TO_K=4500 \
CHECKPOINT_INTERVAL_YEARS=0.04 \
python -m marsdisk.run --config configs/test_checkpoint.yml
```

### 手動検証項目

1. **メモリ使用量の確認**:
   - Activity Monitor / `htop` でメモリ使用量を監視
   - チェックポイント後にメモリが解放されることを確認

2. **リスタート後の継続性**:
   - チェックポイントから再開した結果が連続実行と一致することを確認
   - `summary.json` の値が一貫していることを確認

---

## 影響範囲・互換性

| 観点 | 影響 |
|------|------|
| **既存設定** | デフォルトは `checkpoint.enabled=false` → 動作変更なし |
| **出力ファイル** | 新規ディレクトリ `checkpoints/` 追加のみ。既存出力は不変 |
| **ストリーミング** | 併用可能。チェックポイントとストリーミングは独立 |
| **質量収支** | チェックポイント前後で累積値を正確に引き継ぐ |

---

## 実装優先度

| フェーズ | 内容 | 優先度 |
|----------|------|--------|
| Phase 1 | 基本的なチェックポイント保存・復元 | **高** |
| Phase 2 | CLI `--resume-from` オプション | **高** |
| Phase 3 | 古いチェックポイントの自動削除 | 中 |
| Phase 4 | pickle 形式サポート（高速化） | 低 |

---

## 補足: セグメント長の目安とメモリ効果の試算

- 現状: dt=20 s, t_end≈2 yr → n_steps≈3.1×10^7、n_bins≈40 で psd_rows≈1.2×10^9、メモリ見積≈220 GB。
- 目安: 1 セグメントを **30 日** (= 2.59×10^6 s) とすると n_steps≈1.3×10^5、psd_rows≈5.2×10^6、同スケールでメモリ見積は約 200 GB→**~5 GB** 程度に縮減。
- さらに短縮 (1 日) なら n_steps≈4.3×10^3、psd_rows≈1.7×10^5 でメモリ見積 ~0.2 GB オーダー。用途に応じて interval_years を 0.0027 (1 日)〜0.083 (30 日) に設定する。

## 補足: シリアライズ対象のサイズと形式

- `psd_state`: bin 数×フィールド数。40 bin で float64×数十列 → 数 kB〜数百 kB。pickle/json どちらでも可だが、速度重視なら pickle、可読性重視なら json。
- `supply_state`: reservoir 残量や deep_mixing のキュー。典型的に数十バイト〜数 kB。
- `rng_state`: `np.random.RandomState` の `get_state()` で ~2 kB。pickle 固定。
- 合計: 1 チェックポイントあたり数 MB 以下が目安。keep_last_n=3 なら数十 MB 以内に収まる。

## 補足: テストの縮退条件

- 縮退設定で 1 秒〜数秒で終わるようにする: `t_end_years=1e-6`、`dt_init=1`、`sizes.n_bins=12`、`supply.enabled=false`、`streaming.enabled=true`。
- `test_resume_continues_correctly`: 2 セグメント (各 1e-6 yr) を実行し、連続実行との差分 <1e-9 を確認。
- `test_checkpoint_interval`: interval_years=5e-7 で 2 回以上 checkpoint が生成されることを確認。

## 補足: アウトプットパスの契約と並列時の衝突回避

- チェックポイント保存先: 既定で `<outdir>/checkpoints/ckpt_<step>.json`（または .pkl）。outdir 配下に限定し、並列 run は outdir ごとに分かれる想定。
- `keep_last_n`: 新規保存後に古いファイルを削除。ファイル名に step 番号と時刻ハッシュを入れてユニーク化する。
- streaming と併用: checkpoint は `io.outdir` 内に固定サブディレクトリを作り、parquet/chunk と衝突しないパスを使う（例: checkpoints/ 以下のみ）。

---

## 参考

### 関連ドキュメント
- 物理式の詳細: [analysis/equations.md](../../analysis/equations.md)
- シミュレーション実行方法: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- AI向け利用ガイド: [analysis/AI_USAGE.md](../../analysis/AI_USAGE.md)

### コード参照
| 機能 | ファイル | 備考 |
|------|----------|------|
| メインドライバー | [run.py](../../marsdisk/run.py) | `run_zero_d()` L1081〜 |
| 状態管理 | [run.py](../../marsdisk/run.py) | `ZeroDHistory` L672〜 |
| ストリーミング | [run.py](../../marsdisk/run.py) | `StreamingState` L696〜 |
| 設定スキーマ | [schema.py](../../marsdisk/schema.py) | 拡張予定 |
