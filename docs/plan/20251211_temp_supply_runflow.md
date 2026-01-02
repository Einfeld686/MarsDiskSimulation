# temp_supply 系シミュレーションの現状フロー（T=2000/4000/6000, ε_mix=1/0.1）

ステータス: 整理メモ

## 背景と目的
- temp_supply_* の感度スイープ（T=2000/4000/6000, ε_mix=1/0.1）で `out/<run_id>` が揃ったため、現状の実行手順と挙動を整理し、次の改善ポイント（遮蔽・昇華カウント）を共有する。
- 詳細仕様や式は analysis/ を唯一の参照源とし、ここでは流れと懸念点のみを記載する。

## 実行フロー（0D, marsdisk.run）
- コマンド例: `python -m marsdisk.run --config configs/sweep_temp_supply/temp_supply_T4000_eps1.yml`（outdir は設定依存で run_card/series/summary/checks を生成）。
- 幾何: 0D, r_in=1.0 R_M, r_out=2.7 R_M, n_bins=40, s_min=1e-7 m, s_max=3 m。
- 物理トグル: blowout.enabled=true, blowout.layer=surface_tau_le_1, shielding.mode=psitau（Phi テーブルなし）, PSD wavy_strength=0, supply.mode=const (1e-10 kg m^-2 s^-1)。
- 衝突・表層: surface.collision_solver=smol, surface.use_tcoll=true（Wyatt t_coll=1/(Omega*tau) を使用）, Sigma_tau1 クリップは psd.kappa 由来で ∼2e8 kg m^-2。
- 昇華・シンク: sinks.mode=sublimation, sublimation_location=smol, sub_params.mass_conserving=true のため ds/dt で a_blow を跨いだ分はブローアウト側に合算され、mass_lost_by_sinks は常に 0。
- 時間積分: dt_init=2 s, safety=0.1, dt_over_t_blow_max=0.1, orbit_rollup+streaming (snappy) 有効。

## 観測された挙動（T=4000, ε=1 代表例）
- 〜99 day まで prod_subblow_area_rate=1e-10 が表層に蓄積し、outflux_surface=0（遮蔽強め）。
- 99–110 day に衝突+昇華で sub-blow 在庫が a_blow に到達し、M_out_dot_avg が 2.4e-8 M_Mars/s へスパイク。mass_lost_by_blowout が 0→4.8e-3 M_Mars まで階段的に上がり、その後はほぼ水平。
- mass_lost_by_sinks=0 は mass_conserving_sublimation=true に由来し、昇華分がブローアウトカウントへ移譲されている。
- shielding.mode=psitau だが Phi テーブル未指定のため遮蔽が弱く、表層全体が吹き飛び対象になっている点が段差の一因。

## 懸念・改善アイデア
- 光学的厚さのクリップ不足: Phi テーブル導入または shielding.mode=fixed_tau1 で Σ_tau1 を明示し、表層全体の一斉吹き飛びを抑制する。
- 昇華フラックスの可視化: sub_params.mass_conserving=false で純粋シンクとして分離、または sublimation_location=surface に切り替え、mass_lost_by_sinks に記録させる。
- 挙動再現性: surface.collision_solver=surface_ode で同条件を再実行し、Smol 特有のステップかを比較。
- 可視化: 各 `out/<run_id>/plots` に overview.png, supply_surface.png を生成済み。比較図（M_out_dot, M_loss バー）を追加するとレビューが容易。

## 直近の TODO（提案）
- [ ] shielding テーブルまたは fixed_tau1_sigma を与えた再走で段差が消えるか確認。
- [ ] mass_conserving_sublimation=false の試験で mass_lost_by_sinks が立つかをチェック。
- [ ] surface_ode モードとの比較実行（同じ config を override で切替）。
