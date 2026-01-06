# 衝突キャッシュ保持（ケース間）実装プラン

> **作成日**: 2026-01-06  
> **ステータス**: draft  
> **対象**: `marsdisk/physics/collisions_smol.py`, `marsdisk/run_zero_d.py`, `scripts/runsets/common/run_sweep_worker.py`, `marsdisk/schema.py`  
> **目的**: 0D スイープ（同一プロセス連続実行）で衝突キャッシュを保持し、ケース間の再計算を削減する

---

## 背景

- 0D スイープの CPU 時間は `collisions_smol` / `smol` が支配的で、ケース間の同一グリッド再計算が多い。
- 同一プロセス連続実行（持続ワーカー）時に、衝突キャッシュをケース間で再利用できれば総実行時間を短縮できる見込み。
- ただし、サイズグリッド変更時にキャッシュが誤再利用されるリスクがあるため、**安全な保持条件**が必要。

---

## 目的

- 連続実行時に限って衝突キャッシュを保持し、**再計算コストを削減**する。
- グリッド・物性・衝突モデルの不一致時は **必ずキャッシュを破棄** できる仕組みを用意する。
- 既存の物理式や出力内容は変更しない。

---

## 影響範囲

**対象**
- 0D の `run_zero_d` 実行パス
- `collisions_smol` のキャッシュ管理（断片テンソル、weights、Q_D*、供給分配）
- 持続ワーカー経由のスイープ実行

**非対象**
- 1D 拡張（C5）や衝突モデルそのものの変更
- プロセス間キャッシュ共有（IPC/ディスクキャッシュ）

---

## 想定リスクと対策

- **グリッド不一致での誤再利用**
  - 対策: `sizes/edges` のシグネチャを計算し、異なる場合は強制リセット。
- **キー衝突・近似フィンガープリント**
  - 対策: `sizes_version/edges_version` を安定ハッシュ値で上書きするオプションを導入。
- **メモリ圧迫**
  - 対策: キャッシュ上限を維持し、ケース数や閾値で明示的にリセット可能にする。
- **設定ミスによる例外**
  - 対策: `numerics.collision_cache.persist` 未設定時は既定 `false` を保証し、`getattr` で防御的に参照する。
- **JSONシリアライズ失敗**
  - 対策: `sizes_version/edges_version` を `int` として保存し、`np.uint64` 等を避ける。
- **初期化順序による参照エラー**
  - 対策: PSD 構築後にのみシグネチャ計算を行い、`sizes/edges` が未生成の状態で参照しない。

---

## 設計方針

1. **保持フラグを明示**  
   - 例: `numerics.collision_cache.persist: true`（既定は `false`）
2. **安全な再利用条件**  
   - `sizes/edges` の安定ハッシュ（配列バイト列のハッシュ）を生成
   - ハッシュが変わったら `reset_collision_caches()` を実行
3. **キャッシュキーの安全化**  
   - 保持有効時のみ `sizes_version/edges_version` を安定ハッシュ値へ上書きし、異なるグリッドの衝突を防ぐ
4. **運用の可視化**  
   - キャッシュ再利用/リセットのログを `INFO` で出力（ケース間挙動の確認用）

---

## 実装タスク

- [ ] **設定スキーマ拡張**
  - `marsdisk/schema.py` の `Numerics` に `collision_cache.persist` フラグを追加
- [ ] **シグネチャ生成ユーティリティ**
  - `collisions_smol` に `make_collision_cache_signature(sizes, edges, rho, alpha_frag, qstar_sig)` を追加
- [ ] **リセット条件の改修**
  - `run_zero_d._reset_collision_runtime_state()` で
    - `persist=false` → 従来どおり常時リセット
    - `persist=true` → シグネチャ差分時のみリセット
- [ ] **サイズバージョンの安定化**
  - 保持有効時に限って `psd_state["sizes_version"]` / `edges_version` を
    安定ハッシュで初期化
- [ ] **ワーカースイープ連携**
  - `run_sweep_worker.py` で持続ワーカー使用時は `persist=true` を既定にする

---

## 検証

- **同一グリッド2連続**で結果一致し、キャッシュ再利用ログが出ること
- **異なるグリッド連続**でキャッシュがリセットされること
- 既存の `mass_budget`/`summary` の差分がないこと

---

## 実装手順（チェックリスト）

- [ ] `collision_cache.persist` を追加し、設定読み込みで既定 `false` を保証
- [ ] シグネチャ生成で `sizes/edges` を `float64` かつ `C_CONTIGUOUS` に正規化
- [ ] 連続実行の先頭でシグネチャ比較 → 変更時のみ `reset_collision_caches()`
- [ ] キャッシュ再利用/破棄のログを `INFO` で1回だけ出力
- [ ] 既存の `MARSDISK_DISABLE_COLLISION_CACHE=1` の動作を維持

---

## 実装完了指標（チェックリスト）

- [ ] `persist=false` で従来挙動と完全一致（bitwise か許容差以内）
- [ ] `persist=true` で同一グリッド連続実行の結果が `persist=false` と一致
- [ ] 異なるグリッド連続実行でキャッシュがリセットされるログが出る
- [ ] `checks/mass_budget.csv` の `error_percent` が既定の許容内（≤0.5%）
- [ ] 連続ケースで実行時間が短縮される（ベンチマークで観測）

---

## テスト計画（チェックリスト）

- [ ] **A/B テスト**: `persist=false/true` の結果一致を確認（同一設定）
- [ ] **グリッド差分テスト**: `n_bins` や `s_min` を変えた2ケース連続でキャッシュリセット確認
- [ ] **Q_D* 変更テスト**: `qstar` 係数表/単位系の変更が結果に反映されること
- [ ] **サイズ進化テスト**: `s_min` 進化や drift を含む設定で A/B 一致を確認
- [ ] **メモリ監視**: 長時間実行で RSS の線形増加がないこと
- [ ] **サイズ更新検証**: `sizes_version/edges_version` が更新イベントで確実に増えること
- [ ] **物理モード切替**: `physics_mode` を切り替えても衝突無効時の結果が変わらないこと
- [ ] **スレッド再現性**: スレッド数を変えても同一設定の結果が一致すること

---

## ロールバック

- `persist_collisions=false` に戻せば従来動作に復帰
- トラブル時は `MARSDISK_DISABLE_COLLISION_CACHE=1` で強制無効化

---

## 検討事項

- シグネチャに含めるパラメータの最小集合（`rho`, `alpha_frag`, `qstar_sig` の扱い）
- ハッシュ方式（SHA1 など）の選定と計算コスト
