# 物理計算フローのシーケンス図

> **文書種別**: リファレンス（Diátaxis: Reference）
> **自動生成**: このドキュメントは `tools/make_physics_flow.py` により自動生成されます。
> 手動編集しないでください。
> **情報源**:
> - run.py セクション表: `analysis/run_py_sections.md`
> - schema 参照: `marsdisk/schema.py`
> - dataflow 参照: `analysis/overview.md`

本ドキュメントは火星ダスト円盤シミュレーションの物理計算フローを Mermaid 図で可視化し、
モジュール間の依存関係と計算順序を明確化します。

> **読み方（重要）**: 本書は運用で基準とする `scripts/runsets/windows/run_sweep.cmd` の既定フロー（**1D + Smol**）を主経路として示します。  
> 0D（`run_zero_d`）は **デバッグ／スモークテスト用の補助経路**として位置付け、詳細は最小限に留めます。

---

## 0. run_sweep.cmd 実行時の物理フロー（Windows・簡略版）

`scripts/runsets/windows/run_sweep.cmd` は **スイープの実行ラッパー**であり、
物理計算そのものは `python -m marsdisk.run` に委譲されます。
各ケースは「base config + overrides + case overrides」をマージしてから実行され、
タイムステップ内の物理計算は **本書の 2章と同じ**です。

```mermaid
flowchart TB
    A["run_sweep.cmd"] --> B[Python解決・依存導入]
    B --> C{preflight?}
    C -->|skip| D[archive/paths準備]
    C -->|run| D
    D --> E["run_temp_supply_sweep.cmd"]
    E --> F[case list作成: T, eps, tau, i0]
    F --> G[case overrides生成]
    G --> H["overrides merge: base + overrides + case"]
    H --> I["python -m marsdisk.run"]
    I --> J["run_one_d（1D・run_sweep既定）"]
    J --> K["per-step physics (Section 2)"]
    I --> L["hooks: plot or eval (optional)"]
```

**ケースごとに変わる主な入力（run_sweep 既定）**
- `radiation.TM_K`, `mars_temperature_driver.table.path`（温度）
- `supply.mixing.epsilon_mix`（供給効率）
- `optical_depth.tau0_target`（光学深度）
- `dynamics.i0`, `dynamics.rng_seed`
- `io.outdir`（出力先）

---

## 1. 全体アーキテクチャ概観

```mermaid
flowchart TB
    subgraph CLI["CLI層"]
        A[python -m marsdisk.run] --> B[load_config]
        B --> C[Config検証]
        C --> D{geometry.mode?}
        D -->|1D| E[run_one_d]
        D -->|0D（補助）| F[run_zero_d]
    end

    subgraph RUN1D["run_one_d（1D・主経路）"]
        E --> I0[半径格子の初期化（Nrセル）]
        I0 --> I1[セル状態の初期化（Σ_surf, PSD, …）]
        I1 --> I2{time < t_end?}
        I2 -->|Yes| I3["Step n: global（T_M, a_blow, s_min など）"]
        I3 --> I4["Step n: for each cell i（局所物理 + Smol）"]
        I4 --> I5[診断記録・ストリーミングflush]
        I5 --> I2
        I2 -->|No| I6[summary/checks 出力]
    end

    subgraph OUT["出力層（各ケース outdir）"]
        I6 --> O1["series/run.parquet（セル×時刻）"]
        I6 --> O2[summary.json]
        I6 --> O3["checks/mass_budget.csv"]
    end
```

---

## 2. 各タイムステップの物理計算順序

`run_sweep.cmd` 既定（**1D + smol**）の 1 ステップ（Δt）を、理解のために 3 つに分けて示します。

> 1) 何を時間発展させるか（状態と格子）  
> 2) その時刻の条件を決める（環境・レート評価）  
> 3) 時間を 1 ステップ進める（更新式・ソルバ）

> 1) 状態と格子: rセル（1D）と size bins（固定）と、各セルの状態 `Σ_surf[i]`, `psd_state[i]`, 損失累積など  
> 2) 条件・レート評価: 温度 → 放射圧（β, a_blow, s_min）→（各セルで）κ/τ/相/昇華 ds/dt/シンク時間/供給レート  
> 3) 更新: `collisions_smol`（IMEX-BDF1）で PSD と `Σ_surf` を Δt 更新し、損失（blowout/sinks）を積算

読み方の注記:
- 縦方向が時間の進行で、横方向は登場モジュール（参加者）の並び（物理空間の軸ではない）。
- 矢印は「計算の依頼」と「結果の返却」で、上から下へ順に追います（左から右へ流れる図ではない）。
- `rect` は概念上の区分で、実装では同一タイムステップ内で連続して実行されます。
- `loop` は「半径セルごとの反復」を表し、実装上はセル並列化される場合があります。

```mermaid
sequenceDiagram
    participant R as run_one_d
    participant TD as tempdriver
    participant RAD as radiation
    participant CELL as cell(i)
    participant PH as phase
    participant SZ as sizes
    participant SK as sinks
    participant SH as shielding
    participant SP as supply
    participant SM as collisions_smol

    Note over R: Step n 開始（1D・run_sweep既定）

    rect rgb(255, 250, 240)
        Note right of R: 1) 状態と格子（このΔtで更新するもの）
        Note right of R: state: Σ_surf[i], psd_state[i], losses_cum など
        Note right of R: grid: radial cells, size bins（いずれも固定）
    end

    rect rgb(240, 248, 255)
        Note right of R: 2) 条件・レート評価（E.042-043, β, a_blow）
        R->>TD: evaluate(time)
        TD-->>R: T_M(time)
        R->>RAD: blowout_radius と beta(s_min)
        RAD-->>R: a_blow, beta, s_min_effective
        loop for each radial cell i
            R->>CELL: load Σ_surf[i], psd_state[i]
            CELL->>CELL: κ_surf = psd.compute_kappa(psd_state)
            CELL->>CELL: τ = κ_surf × Σ_surf × los_factor
            CELL->>PH: evaluate_with_bulk(T, τ)
            PH-->>CELL: phase_state
            CELL->>SZ: ds/dt (HKL, grain T)
            SZ-->>CELL: ds/dt
            CELL->>SK: total_sink_timescale(T, ρ, Ω)
            SK-->>CELL: t_sink
            opt shielding.mode in {psitau, table}
                CELL->>SH: effective_kappa(κ_surf, τ, Φ)
                SH-->>CELL: κ_eff, Σ_tau1
            end
            CELL->>SP: evaluate_supply(time, r, τ, ε_mix, ...)
            SP-->>CELL: prod_rate
            rect rgb(245, 255, 250)
                Note right of CELL: 3) 更新（Smol IMEXでΔt進める）
                CELL->>SM: step_collisions(...)
                SM-->>CELL: psd_state', Σ_surf', losses
            end
            CELL-->>R: record row(s)
        end
    end

    Note over R: Step n 終了 → 診断記録・ストリーミングflush
```

---

## 3. 温度ドライバ解決フロー

`tempdriver.py` による火星温度の動的解決:

```mermaid
flowchart TB
    subgraph RESOLVE["resolve_temperature_driver"]
        A[radiation_cfg] --> B{TM_K 明示?}
        B -->|Yes| C["ConstantDriver(TM_K)"]
        B -->|No| D{driver.mode?}
        
        D -->|"constant"| E["ConstantDriver(driver.constant)"]
        D -->|"table"| F["TableDriver(path)"]
        D -->|"autogen"| G{テーブル存在?}
        
        G -->|No| H["SiO2冷却式でテーブル生成"]
        G -->|Yes| I{時間範囲OK?}
        I -->|No| H
        I -->|Yes| J["既存テーブルをロード"]
        
        H --> K["_write_temperature_table"]
        K --> J
        J --> F
    end
    
    subgraph RUNTIME["TemperatureDriverRuntime"]
        L[source: str]
        M[mode: str]
        N["evaluate(time_s) → T_M"]
    end
    
    C --> RUNTIME
    E --> RUNTIME
    F --> RUNTIME
```

---

## 4. 相判定フロー (PhaseEvaluator)

`phase.py` による固体/蒸気相の判定とシンク選択:

```mermaid
flowchart TB
    subgraph INPUT["入力"]
        A[temperature_K]
        B[pressure_Pa]
        C[tau]
        D[radius_m, time_s]
    end
    
    subgraph EVAL["PhaseEvaluator.evaluate_with_bulk"]
        E{map_fn 利用可能?}
        E -->|Yes| F["_call_map(map_fn, T, P, τ)"]
        E -->|No| G["_threshold_decision(T, P, τ)"]
        
        F --> H["_parse_map_result"]
        G --> I["T_condense/T_vaporize ランプ"]
        
        H --> J[PhaseDecision]
        I --> J
        
        J --> K{state?}
        K -->|"solid"| L["sink_selected = 'rp_blowout'"]
        K -->|"vapor"| M["sink_selected = 'hydro_escape'"]
    end
    
    subgraph OUTPUT["出力"]
        N["PhaseDecision(state, f_vap, method)"]
        O["BulkPhaseState(f_liquid, f_solid, f_vapor)"]
        P["sink_selected ∈ {rp_blowout, hydro_escape, none}"]
    end
    
    A & B & C & D --> EVAL
    J --> N
    EVAL --> O
    L & M --> P
```

---

## 5. 外部供給モード (Supply)

`supply.py` による生成率の評価:

```mermaid
flowchart LR
    subgraph CONFIG["YAML設定"]
        A1["mode: const"]
        A2["mode: powerlaw"]
        A3["mode: table"]
        A4["mode: piecewise"]
    end
    
    subgraph RATE["_rate_basic"]
        B1["prod_area_rate_kg_m2_s"]
        B2["A × (t - t₀)^index"]
        B3["TableData.interp(t, r)"]
        B4["区間ごとに再帰評価"]
    end
    
    subgraph OUTPUT["get_prod_area_rate"]
        C["R_base × ε_mix"]
        D["max(rate, 0)"]
    end
    
    A1 --> B1
    A2 --> B2
    A3 --> B3
    A4 --> B4
    
    B1 & B2 & B3 & B4 --> C
    C --> D
```

### 5.1 供給輸送モード (Transport)

`run_sweep.cmd` の既定は `supply.transport.mode="direct"`（深部リザーバ経路は無効）。

```mermaid
flowchart LR
    A["R_base × ε_mix"] --> B["direct: 表層へ注入"]
    B --> C["Smol 衝突ステップで同時更新"]
    C --> D["Σ_surf^{n+1}, M_out, M_sink"]
```

補足: `deep_mixing` は非既定であり、運用の `run_sweep.cmd` では使用しない（スキーマ上も非推奨候補）。

---

## 6. 表層進化ステップ (S1) の詳細

`surface.collision_solver="surface_ode"` を選んだ場合のみ使われる **非既定**の更新式です。  
`run_sweep.cmd` の既定（`collision_solver=smol`）ではこの節の ODE は使われません（Smol は §7）。

- 目的: 0D/簡易検証で「供給・ブローアウト・シンク」を解析的に追う補助経路。
- 衝突寿命 `t_coll` は Wyatt 型のスケーリング（概算）を用いる（詳細は論文側・`analysis/equations.md` を参照）。

---

## 7. Smoluchowski 衝突積分 (C3) の詳細

IMEX-BDF(1) による粒径分布の時間発展:

```mermaid
flowchart TB
    subgraph INPUT["入力"]
        A["N_k^n (数密度)"]
        B["K_ij (衝突カーネル)"]
        C["F_ijk (破片分布)"]
        D["S_prod (供給)"]
    end
    
    subgraph IMEX["IMEX-BDF(1)"]
        E["Loss項 (陰的): L_k = Σ_j K_kj N_j"]
        F["Gain項 (陽的): G_k = Σ_ij F_ijk K_ij N_i N_j"]
        G["N_k^{n+1} = (N_k^n + Δt×(G_k + S_prod)) / (1 + Δt×L_k)"]
    end
    
    subgraph CONS["質量保存検査 (C4)"]
        H["ΔM = Σ_k m_k (N_k^{n+1} - N_k^n)"]
        I{"| ΔM/M | < 0.5%?"}
        J["OK"]
        K["警告/エラー"]
    end
    
    A & B & C & D --> E & F
    E & F --> G
    G --> H
    H --> I
    I -->|Yes| J
    I -->|No| K
```

---

## 8. 放射圧ブローアウト判定フロー

```mermaid
flowchart TB
    A[粒径 s] --> B{s < s_blow?}
    B -->|Yes| C[β > 0.5]
    B -->|No| D[β ≤ 0.5]
    
    C --> E{phase = solid?}
    E -->|Yes| F{τ < τ_gate?}
    E -->|No| G[ブローアウト無効]
    
    F -->|Yes| H[ブローアウト有効]
    F -->|No| I[τゲートでブロック]
    
    H --> J["outflux = Σ_surf × Ω × gate_factor"]
    G --> K["outflux = 0"]
    I --> K
    D --> L[軌道束縛維持]
```

---

## 参考文献

- [@StrubbeChiang2006_ApJ648_652]: ApJ 648, 652 — 衝突時間スケール t_coll
- [@Wyatt2008]: ARA&A 46, 339 — デブリ円盤の衝突カスケード
- [@Burns1979_Icarus40_1]: Icarus 40, 1 — 放射圧効率 Q_pr と β の定義
- [@Hyodo2017a_ApJ845_125], 2018): ApJ — 火星月形成円盤の放射冷却
- [@Pignatale2018_ApJ853_118]: ApJ 853, 118 — HKL昇華フラックス
- [@Ronnet2016_ApJ828_109]: ApJ 828, 109 — 外縁ガス包絡での凝縮
