# 物理計算フローのシーケンス図

> **文書種別**: リファレンス（Diátaxis: Reference）

本ドキュメントは火星ダスト円盤シミュレーションの物理計算フローを Mermaid 図で可視化し、
モジュール間の依存関係と計算順序を明確化します。

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
    end
    
    subgraph LOOP["時間積分ループ"]
        H --> I{step_no < n_steps?}
        I -->|Yes| J[物理ステップ]
        J --> K[診断記録]
        K --> I
        I -->|No| L[出力書込]
    end
    
    subgraph OUT["出力層"]
        L --> M[run.parquet]
        L --> N[summary.json]
        L --> O[mass_budget.csv]
    end
```

---

## 2. 各タイムステップの物理計算順序

AGENTS.md で規定された結合順序:

> ⟨Q_pr⟩ → β → a_blow → sublimation ds/dt → τ & Φ → surface sink fluxes

```mermaid
sequenceDiagram
    participant M as main loop
    participant TD as tempdriver
    participant RAD as radiation
    participant SZ as sizes
    participant PSD as psd
    participant SH as shielding
    participant PH as phase
    participant SK as sinks
    participant SF as surface
    participant SM as smol

    Note over M: Step n 開始
    
    rect rgb(240, 248, 255)
        Note right of M: 1. 温度評価 (E.042-043)
        M->>TD: evaluate(t)
        TD-->>M: T_M(t)
    end
    
    rect rgb(255, 250, 240)
        Note right of M: 2. 放射圧パラメータ (R1-R3)
        M->>RAD: qpr_lookup(s, T_M)
        RAD-->>M: ⟨Q_pr⟩
        M->>RAD: beta(s, ρ, T_M, Q_pr)
        RAD-->>M: β
        M->>RAD: blowout_radius(ρ, T_M, Q_pr)
        RAD-->>M: a_blow
    end
    
    rect rgb(240, 255, 240)
        Note right of M: 3. サイズ下限更新
        M->>SZ: eval_ds_dt_sublimation(T_grain, ρ)
        SZ-->>M: ds/dt
        M->>M: s_min_effective = max(s_min_config, a_blow)
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
        M->>PH: evaluate(T_M, P, τ)
        PH-->>M: phase_state, f_vap
    end
    
    rect rgb(245, 255, 250)
        Note right of M: 7. シンク時間スケール
        M->>SK: total_sink_timescale(T, ρ, Ω)
        SK-->>M: t_sink, components
    end
    
    rect rgb(255, 255, 240)
        Note right of M: 8. 表層進化 (S1) or Smol (C3)
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

## 3. 表層進化ステップ (S1) の詳細

Strubbe & Chiang (2006) / Wyatt (2008) に基づく表層 ODE:

```mermaid
flowchart LR
    subgraph INPUT["入力"]
        A[Σ_surf^n]
        B[prod_rate]
        C[Ω, τ, t_sink]
    end
    
    subgraph CALC["計算"]
        D["t_blow = χ/Ω"]
        E["t_coll = 1/(Ω×τ)"]
        F["λ = 1/t_blow + I_coll/t_coll + I_sink/t_sink"]
        G["Σ^{n+1} = (Σ^n + Δt×prod) / (1 + Δt×λ)"]
        H["Σ^{n+1} = min(Σ^{n+1}, Σ_τ=1)"]
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
    G --> H
    H --> I & J
```

---

## 4. Smoluchowski 衝突積分 (C3) の詳細

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

## 5. 放射圧ブローアウト判定フロー

```mermaid
flowchart TB
    A[粒径 s] --> B{s < a_blow?}
    B -->|Yes| C[β > 0.5]
    B -->|No| D[β ≤ 0.5]
    
    C --> E{phase = solid?}
    E -->|Yes| F{τ < τ_gate?}
    E -->|No| G[ブローアウト無効]
    
    F -->|Yes| H[ブローアウト有効]
    F -->|No| I[τゲートでブロック]
    
    H --> J["outflux = Σ_surf × Ω"]
    G --> K["outflux = 0"]
    I --> K
    D --> L[軌道束縛維持]
```

---

## 6. モジュール依存関係

```mermaid
graph TD
    subgraph CLI
        RUN[run.py]
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
    
    RUN --> RAD & SH & PSD & SF & SM & SK & TD & PH & CSMO
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
    CSMO --> SM & COL & DY & PSD
    TD --> TB
    PH --> CN
```

---

## 7. 出力データフロー

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
    end
    
    subgraph FILES["出力ファイル"]
        J[series/run.parquet]
        K[series/psd_hist.parquet]
        L[series/diagnostics.parquet]
        M[summary.json]
        N[checks/mass_budget.csv]
        O[orbit_rollup.csv]
    end
    
    A --> F --> J
    B --> F --> K
    C --> F --> L
    D --> H --> N
    E --> I --> O
    A --> G --> M
```

---

## 8. 式番号とモジュールの対応表

| 式番号 | 式名 | モジュール | 関数/行番号 |
|--------|------|-----------|-------------|
| (E.001) | v_kepler | grid.py | `v_kepler` L34 |
| (E.002) | omega | grid.py | `omega` L90 |
| (E.004) | interp_qpr | io/tables.py | `interp_qpr` L259-270 |
| (E.006) | t_coll | surface.py | `wyatt_tcoll_S1` L62-73 |
| (E.007) | step_surface_density_S1 | surface.py | `step_surface_density_S1` L96-163 |
| (E.013) | β | radiation.py | `beta` |
| (E.014) | a_blow | radiation.py | `blowout_radius` L274-288 |
| (C3) | IMEX-BDF(1) | smol.py | `step_imex_bdf1_C3` L18-101 |
| (C4) | mass_budget_error | smol.py | `compute_mass_budget_error_C4` L104-131 |
| (S0) | effective_kappa | shielding.py | `effective_kappa` L90-120 |
| (S1) | step_surface | surface.py | `step_surface` L185-208 |

---

## 9. 設定キー → 物理モジュールのマッピング

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
    end
    
    subgraph MODULE["物理モジュール"]
        M1[tempdriver]
        M2[radiation / tables]
        M3[shielding]
        M4[sinks / sublimation]
        M5[surface / collisions_smol]
        M6[surface (outflux)]
        M7[time loop dt]
    end
    
    C1 --> M1
    C2 --> M2
    C3 --> M3
    C4 --> M4
    C5 --> M5
    C6 --> M6
    C7 --> M7
```

---

## 参考文献

- Strubbe & Chiang (2006): ApJ 648, 652 — 衝突時間スケール t_coll
- Wyatt (2008): ARA&A 46, 339 — デブリ円盤の衝突カスケード
- Burns et al. (1979): Icarus 40, 1 — 放射圧効率 Q_pr と β の定義
- Hyodo et al. (2017, 2018): ApJ — 火星月形成円盤の放射冷却
