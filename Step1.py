import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colors

# MOD: 物理定数
rho = 2500          # kg/m^3
beta_crit = 0.03
AU = 1.496e11       # m
a_Mars = 1.52 * AU
G = 6.674e-11
M_Mars = 6.417e23   # kg
R_Mars = 3.39e6     # m
a_ring = 3 * R_Mars

# MOD: グリッド定義
s_vals = np.logspace(-6, 0, 400)
Sigma_vals = np.logspace(0, 10, 400)
S, SIG = np.meshgrid(s_vals, Sigma_vals)

# MOD: 光学的厚さ・β・タイムスケール計算
Omega = np.sqrt(G * M_Mars / a_ring ** 3)
tau = 3 * SIG / (4 * rho * S)
beta = 5.7e-4 / (rho * S)
t_PR = 400 * (rho / 3000) * (S / 1e-6) * (a_Mars / AU) ** 2
sec_in_year = 365 * 24 * 3600
t_col = 4 * rho * S / (3 * SIG * Omega) / sec_in_year
ratio = t_PR / t_col
log_ratio = np.log10(ratio)

# MOD: 図の準備
fig, ax = plt.subplots(figsize=(8, 6))
abs_max = np.nanmax(np.abs(log_ratio))
norm = colors.TwoSlopeNorm(vcenter=0, vmin=-abs_max, vmax=abs_max)
pcm = ax.pcolormesh(np.log10(S), np.log10(SIG), log_ratio,
                    cmap='RdBu_r', norm=norm, shading='auto')
fig.colorbar(pcm, ax=ax, label=r'$\log_{10}(t_{\rm PR}/t_{\rm col})$')

# MOD: 各境界線を描画
ax.contour(np.log10(S), np.log10(SIG), tau, levels=[1], colors='white',
           linestyles='--', linewidths=1)
ax.contour(np.log10(S), np.log10(SIG), beta, levels=[beta_crit], colors='red',
           linewidths=1)
ax.contour(np.log10(S), np.log10(SIG), t_PR/t_col, levels=[1], colors='cyan',
           linestyles='-.', linewidths=1)

# MOD: 3 条件を満たす領域をハッチ
mask = (tau < 1) & (beta > beta_crit) & (t_PR < t_col)
ax.contourf(np.log10(S), np.log10(SIG), mask.astype(int), levels=[0.5, 1.5],
            hatches=['////'], colors='none', alpha=0)

# MOD: 軸ラベルとタイトル
ax.set_xlabel(r'粒子半径 $\log_{10} s\,[\mathrm{m}]$')
ax.set_ylabel(r'表面密度 $\log_{10} \Sigma\,[\mathrm{kg\,m^{-2}}]$')
ax.set_title('火星周囲の静的タイムスケールマップ')

# MOD: 出力先フォルダを作成して保存
os.makedirs('output', exist_ok=True)
plt.savefig(os.path.join('output', 'fig_static_map.png'), dpi=300)

