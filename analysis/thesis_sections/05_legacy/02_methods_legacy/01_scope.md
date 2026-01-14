## 1. 研究対象と基本仮定

本モデルは gas-poor 条件下の**軸対称・鉛直積分**ディスクを対象とし、半径方向に分割した 1D 計算を基準とする（[@Hyodo2017a_ApJ845_125; @CanupSalmon2018_SciAdv4_eaar6887; @Olofsson2022_MNRAS513_713]）。粒径分布 $n(s)$ をサイズビンで離散化し、Smoluchowski 衝突カスケード（collisional cascade）と表層の放射圧・昇華による流出を同一ループで結合する（[@Dohnanyi1969_JGR74_2531; @Krivov2006_AA455_509; @StrubbeChiang2006_ApJ648_652]）。

- 標準の物理経路は Smoluchowski 経路（C3/C4）を各半径セルで解く 1D 手法で、実装の計算順序は図 3.2 に従う。放射圧〜流出の依存関係のみを抜粋すると ⟨$Q_{\rm pr}$⟩→β→$s_{\rm blow}$→遮蔽Φ→Smol IMEX→外向流束となる。半径方向の粘性拡散（radial viscous diffusion; C5）は演算子分割で追加可能とする（[@Krivov2006_AA455_509; @Wyatt2008]）。  
  > **参照**: analysis/overview.md §1, analysis/physics_flow.md §2「各タイムステップの物理計算順序」
- 運用スイープの既定は 1D とし、C5 は必要時のみ有効化する。具体的な run_sweep 手順と環境変数は付録 A、設定→物理対応は付録 B を参照する。
- [@TakeuchiLin2003_ApJ593_524] に基づく gas-rich 表層 ODE は `ALLOW_TL2003=false` が既定で無効。gas-rich 感度試験では環境変数を `true` にして `surface.collision_solver=surface_ode`（例: `configs/scenarios/gas_rich.yml`）を選ぶ。  
  > **参照**: analysis/equations.md（冒頭注記）, analysis/overview.md §1「gas-poor 既定」

1D は $r_{\rm in}$–$r_{\rm out}$ を $N_r$ セルに分割し、各セルの代表半径 $r_i$ で局所量を評価する。角速度 $\Omega(r_i)$ とケプラー速度 $v_K(r_i)$ は (E.001)–(E.002) に従い、$t_{\rm blow}$ や $t_{\rm coll}$ の基準時間に用いる。C5 を無効化した場合はセル間結合を行わず、半径方向の流束を解かない局所進化として扱う。

### 1.1 物性モデル (Hybrid Basalt/SiO₂)

物性は **Hybrid Basalt/SiO₂** を採用する。力学パラメータ（密度・$Q_D^*$）は玄武岩、放射圧効率 $\langle Q_{\rm pr}\rangle$ は SiO₂ テーブル、昇華は SiO 蒸気圧を用いる（[@BenzAsphaug1999_Icarus142_5; @LeinhardtStewart2012_ApJ745_79; @BohrenHuffman1983_Wiley; @Melosh2007_MPS42_2079]）。混合物近似であるため、$\rho$ と $\langle Q_{\rm pr}\rangle$ の感度掃引を想定し、実行時の採用値は `run_config.json` に保存する。

$\langle Q_{\rm pr}\rangle$ はテーブル入力（CSV/NPZ）を標準とし、Planck 平均の評価に用いる（[@BohrenHuffman1983_Wiley]）。遮蔽係数 $\Phi(\tau,\omega_0,g)$ もテーブル入力を基本とし、双線形補間で適用する（[@Joseph1976_JAS33_2452; @HansenTravis1974_SSR16_527; @CogleyBergstrom1979_JQSRT21_265]）。これらのテーブルは `run_config.json` にパスが保存され、再現実行時の参照点となる。

> **参照**: analysis/equations.md（Hybrid Basalt/SiO₂ の前提）

---
