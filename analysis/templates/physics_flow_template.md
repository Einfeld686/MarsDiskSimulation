# 物理計算フローのシーケンス図

> **文書種別**: リファレンス（Diátaxis: Reference）
> **自動生成**: このドキュメントは `{{TOOL_PATH}}` により自動生成されます。
> 手動編集しないでください。
> **情報源**:
> - run.py セクション表: `{{RUN_SECTIONS_PATH}}`
> - schema 参照: `{{SCHEMA_PATH}}`
> - dataflow 参照: `{{DATAFLOW_PATH}}`

本ドキュメントは火星ダスト円盤シミュレーションの物理計算フローを Mermaid 図で可視化し、
モジュール間の依存関係と計算順序を明確化します。

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
    I --> J["run_zero_d / run_one_d"]
    J --> K["per-step physics (Section 2)"]
    I --> L[hooks: plot/eval (optional)]
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
    end
    
    subgraph INIT["初期化フェーズ"]
        C --> D[温度ドライバ解決]
        D --> E[Q_pr テーブル読込]
        E --> F[Φ遮蔽テーブル読込]
        F --> G[PSD初期化]
        G --> H[表層Σ_surf初期化]
        H --> H2[PhaseEvaluator初期化]
        H2 --> H3[SupplySpec解決]
    end
    
    subgraph LOOP["時間積分ループ"]
        H3 --> I{step_no < n_steps?}
        I -->|Yes| J[物理ステップ]
        J --> K[診断記録]
        K --> I
        I -->|No| L[出力書込]
    end
    
    subgraph OUT["出力層"]
        L --> M[run.parquet]
        L --> N[summary.json]
        L --> O[mass_budget.csv]
        L --> P[psd_hist.parquet]
        L --> Q[diagnostics.parquet]
    end
```

---

## 2. 各タイムステップの物理計算順序

AGENTS.md で規定された結合順序:

> ⟨Q_pr⟩ → β → s_blow → sublimation ds/dt → τ & Φ → phase → supply → surface sink fluxes

```mermaid
sequenceDiagram
    participant M as main loop
    participant TD as tempdriver
    participant RAD as radiation
    participant SZ as sizes
    participant PSD as psd
    participant SH as shielding
    participant PH as phase
    participant SP as supply
    participant SK as sinks
    participant SF as surface
    participant SM as smol

    Note over M: Step n 開始
    
    rect rgb(240, 248, 255)
        Note right of M: 1. 温度評価 (E.042-043)
        M->>TD: driver.evaluate(t)
        TD-->>M: T_M(t)
    end
    
    rect rgb(255, 250, 240)
        Note right of M: 2. 放射圧パラメータ (R1-R3)
        M->>RAD: qpr_lookup(s, T_M)
        RAD-->>M: ⟨Q_pr⟩
        M->>RAD: beta(s, ρ, T_M, Q_pr)
        RAD-->>M: β
        M->>RAD: blowout_radius(ρ, T_M, Q_pr)
        RAD-->>M: s_blow
    end
    
    rect rgb(240, 255, 240)
        Note right of M: 3. サイズ下限更新
        M->>SZ: eval_ds_dt_sublimation(T_grain, ρ)
        SZ-->>M: ds/dt
        M->>M: s_min_effective = max(s_min_config, s_blow)
    end
    
    rect rgb(255, 245, 238)
        Note right of M: 4. PSD & 不透明度 (PSD)
        M->>PSD: update_psd_state(s_min, s_max, α)
        PSD-->>M: psd_state
        M->>PSD: compute_kappa(psd_state)
        PSD-->>M: κ_surf
    end
    
    rect rgb(248, 248, 255)
        Note right of M: 5. 光学深度 & 遮蔽 (S0)
        M->>M: τ = κ_surf × Σ_surf
        M->>SH: effective_kappa(κ, τ, Φ_fn)
        SH-->>M: κ_eff
        M->>SH: sigma_tau1(κ_eff)
        SH-->>M: Σ_τ=1
    end
    
    rect rgb(255, 240, 245)
        Note right of M: 6. 相判定 (Phase)
        M->>PH: evaluate_with_bulk(T_M, P, τ)
        PH-->>M: PhaseDecision, BulkPhaseState
        Note right of M: solid → rp_blowout
        Note right of M: vapor → hydro_escape
    end

    rect rgb(240, 255, 255)
        Note right of M: 7. 外部供給 (Supply)
        M->>SP: get_prod_area_rate(t, r, spec)
        SP-->>M: Σ_prod
    end
    
    rect rgb(245, 255, 250)
        Note right of M: 8. シンク時間スケール
        M->>SK: total_sink_timescale(T, ρ, Ω)
        SK-->>M: t_sink, components
    end
    
    rect rgb(255, 255, 240)
        Note right of M: 9. 表層進化 (S1) or Smol (C3)
        alt collision_solver = "surface_ode"
            M->>SF: step_surface(Σ, prod, dt, Ω, τ, t_sink)
            SF-->>M: Σ_new, outflux, sink_flux
        else collision_solver = "smol"
            M->>SM: step_collisions_smol_0d(psd, Σ, dt, ...)
            SM-->>M: psd_new, Σ_new, losses
        end
    end
    
    Note over M: Step n 終了 → 記録
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

`supply.transport.mode` による表層／深部経路の分岐:

```mermaid
flowchart TB
    subgraph INPUT["供給レート評価"]
        A["R_base × ε_mix"]
        B["温度/フィードバック/リザーバ倍率"]
    end
    
    subgraph TRANSPORT["transport.mode"]
        C{"mode?"}
        D["direct: 表層直接注入"]
        E["deep_mixing: 深部経由"]
    end
    
    subgraph DIRECT["direct モード"]
        D1["prod_rate_applied"]
    end
    
    subgraph DEEP["deep_mixing モード"]
        E1["σ_deep リザーバ蓄積"]
        E2["t_mix_orbits で混合"]
        E3["deep→surf flux"]
        E4["prod_rate_applied"]
    end
    
    A --> B --> C
    C -->|"direct"| D --> D1
    C -->|"deep_mixing"| E --> E1 --> E2 --> E3 --> E4
    D1 --> F["表層 Σ_surf 更新"]
    E4 --> F
```

---

## 6. 表層進化ステップ (S1) の詳細

[@StrubbeChiang2006_ApJ648_652] / [@Wyatt2008] に基づく表層 ODE:

```mermaid
flowchart LR
    subgraph INPUT["入力"]
        A[Σ_surf^n]
        B[prod_rate]
        C["Ω, τ, t_sink"]
    end
    
    subgraph CALC["計算"]
        D["t_blow = χ/Ω"]
        E["t_coll = 1/(Ω×τ)"]
        F["λ = 1/t_blow + I_coll/t_coll + I_sink/t_sink"]
        G["Σ^{n+1} = (Σ^n + Δt×prod) / (1 + Δt×λ)"]
    end
    
    subgraph OUTPUT["出力"]
        I["outflux = Σ^{n+1} × Ω"]
        J["sink_flux = Σ^{n+1} / t_sink"]
    end
    
    A --> G
    B --> G
    C --> D & E & F
    D & E --> F
    F --> G
    G --> I & J
```

補足: `Σ_{τ=1}` は診断用に保持し、表層 ODE の更新式で `Σ_surf` を直接クリップしない。

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

## 9. モジュール依存関係

```mermaid
graph TD
    subgraph CLI
        RUN[run_zero_d.py]
    end
    
    subgraph PHYSICS["physics/"]
        RAD[radiation.py]
        SH[shielding.py]
        PSD[psd.py]
        SF[surface.py]
        SM[smol.py]
        SK[sinks.py]
        SUB[sublimation.py]
        SZ[sizes.py]
        TD[tempdriver.py]
        PH[phase.py]
        DY[dynamics.py]
        COL[collide.py]
        CSMO[collisions_smol.py]
        SP[supply.py]
        FRAG[fragments.py]
        QSTAR[qstar.py]
    end
    
    subgraph IO["io/"]
        WR[writer.py]
        TB[tables.py]
    end
    
    subgraph CORE
        GR[grid.py]
        SC[schema.py]
        CN[constants.py]
    end
    
    RUN --> RAD & SH & PSD & SF & SM & SK & TD & PH & CSMO & SP
    RUN --> WR & TB
    RUN --> GR & SC & CN
    
    RAD --> TB & CN
    SH --> TB
    PSD --> CN
    SF --> CN
    SM --> CN
    SK --> SUB & RAD & CN
    SUB --> CN
    SZ --> SUB & CN
    CSMO --> SM & COL & DY & PSD & FRAG & QSTAR
    TD --> TB
    PH --> CN & SC
    SP --> SC
```

---

## 10. 出力データフロー

```mermaid
flowchart LR
    subgraph COLLECT["データ収集"]
        A[records リスト]
        B[psd_hist_records]
        C[diagnostics]
        D[mass_budget]
        E[orbit_rollup_rows]
    end
    
    subgraph WRITE["書き出し"]
        F[write_parquet]
        G[write_summary]
        H[write_mass_budget]
        I[write_orbit_rollup]
        J[write_run_config]
    end
    
    subgraph FILES["出力ファイル"]
        K[series/run.parquet]
        L[series/psd_hist.parquet]
        M[series/diagnostics.parquet]
        N[summary.json]
        O[checks/mass_budget.csv]
        P[orbit_rollup.csv]
        Q[run_config.json]
    end
    
    A --> F --> K
    B --> F --> L
    C --> F --> M
    D --> H --> O
    E --> I --> P
    A --> G --> N
    A --> J --> Q
```

---

## 11. 式番号とモジュールの対応表

| 式番号 | 式名 | モジュール | 関数/行番号 |
|--------|------|-----------|-------------|
| (E.001) | v_kepler | grid.py | `v_kepler` L34 |
| (E.002) | omega | grid.py | `omega` L90 |
| (E.004) | interp_qpr | io/tables.py | `interp_qpr` L259-270 |
| (E.006) | t_coll | surface.py | `wyatt_tcoll_S1` L62-73 |
| (E.007) | step_surface_density_S1 | surface.py | `step_surface_density_S1` L96-163 |
| (E.010) | IMEX-BDF(1) | smol.py | `step_imex_bdf1_C3` L18-101 |
| (E.011) | mass_budget_error | smol.py | `compute_mass_budget_error_C4` L104-131 |
| (E.013) | β | radiation.py | `beta` L220-241 |
| (E.014) | s_blow | radiation.py | `blowout_radius` L274-288 |
| (E.015) | effective_kappa | shielding.py | `effective_kappa` L90-120 |
| (E.016) | sigma_tau1 | shielding.py | `sigma_tau1` L123-130 |
| (E.018) | mass_flux_hkl | sublimation.py | `mass_flux_hkl` L534-584 |
| (E.027) | get_prod_area_rate | supply.py | `get_prod_area_rate` L93-98 |
| (E.042-043) | T_M(t) | tempdriver.py | `resolve_temperature_driver` L275-341 |
| — | PhaseDecision | phase.py | `PhaseEvaluator.evaluate` L120-138 |
| — | hydro_escape_timescale | phase.py | `hydro_escape_timescale` L564-593 |

---

## 12. 設定キー → 物理モジュールのマッピング

```mermaid
flowchart LR
    subgraph CONFIG["YAML設定"]
        C1[radiation.TM_K]
        C2[radiation.qpr_table_path]
        C3[shielding.mode]
        C4[sinks.enable_sublimation]
        C5[surface.collision_solver]
        C6[blowout.enabled]
        C7[numerics.dt_init]
        C8["mars_temperature_driver.*"]
        C9[phase.mode]
        C10[supply.mode]
    end
    
    subgraph MODULE["物理モジュール"]
        M1[tempdriver]
        M2[radiation / tables]
        M3[shielding]
        M4[sinks / sublimation]
        M5[surface / collisions_smol]
        M6["surface (outflux)"]
        M7[time loop dt]
        M8[phase]
        M9[supply]
    end
    
    C1 --> M1
    C2 --> M2
    C3 --> M3
    C4 --> M4
    C5 --> M5
    C6 --> M6
    C7 --> M7
    C8 --> M1
    C9 --> M8
    C10 --> M9
```

---

## 13. 流体逃亡スケーリング (hydro_escape)

相が `vapor` の場合に適用される流体力学的散逸:

```mermaid
flowchart LR
    subgraph INPUT["入力"]
        A[HydroEscapeConfig]
        B[temperature_K]
        C[f_vap]
    end
    
    subgraph CALC["hydro_escape_timescale"]
        D["ΔT = T - T_ref"]
        E["g(ΔT) = exp(-ΔT/scale)"]
        F["t_escape = 1 / (strength × f_vap × g)"]
    end
    
    subgraph OUTPUT["出力"]
        G[t_escape_s]
    end
    
    A & B & C --> CALC
    D --> E --> F
    F --> G
```

---

## 14. バルク相状態 (BulkPhaseState)

`PhaseEvaluator.evaluate_with_bulk` が返す詳細な相情報:

| フィールド | 型 | 意味 |
|-----------|----|----|
| `state` | `solid_dominated`/`liquid_dominated`/`mixed` | 支配相 |
| `f_liquid` | float | 液相分率 [0,1] |
| `f_solid` | float | 固相分率 [0,1] |
| `f_vapor` | float | 蒸気分率 [0,1] |
| `method` | str | 判定手法 (`map`/`threshold`) |
| `used_map` | bool | マップ関数使用の有無 |
| `temperature_K` | float | 評価温度 |
| `tau` | float | 光学深度 |

---

## 参考文献

- [@StrubbeChiang2006_ApJ648_652]: ApJ 648, 652 — 衝突時間スケール t_coll
- [@Wyatt2008]: ARA&A 46, 339 — デブリ円盤の衝突カスケード
- [@Burns1979_Icarus40_1]: Icarus 40, 1 — 放射圧効率 Q_pr と β の定義
- [@Hyodo2017a_ApJ845_125], 2018): ApJ — 火星月形成円盤の放射冷却
- [@Pignatale2018_ApJ853_118]: ApJ 853, 118 — HKL昇華フラックス
- [@Ronnet2016_ApJ828_109]: ApJ 828, 109 — 外縁ガス包絡での凝縮
