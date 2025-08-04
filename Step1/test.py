import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colors

# Physical constants
rho = 2500          # kg/m^3
beta_crit = 0.03
AU = 1.496e11       # m
a_Mars = 1.52 * AU
G = 6.674e-11
M_Mars = 6.417e23   # kg
R_Mars = 3.39e6     # m
M_Sun = 1.989e30    # kg
a_ring = 3 * R_Mars
r_mars = 5 * R_Mars  # representative distance from Mars' center

# Grid definition
s_vals = np.logspace(-6, 0, 400)
Sigma_vals = np.logspace(0, 10, 400)
S, SIG = np.meshgrid(s_vals, Sigma_vals)

# Optical depth, beta, and timescale calculations
Omega = np.sqrt(G * M_Mars / a_ring ** 3)
tau = 3 * SIG / (4 * rho * S)
beta = (5.7e-4 / (rho * S)) * (M_Sun / M_Mars) * (r_mars / a_Mars) ** 2
t_PR = 400 * (rho / 3000) * (S / 1e-6) * (a_Mars / AU) ** 2
sec_in_year = 365 * 24 * 3600
t_col = 4 * rho * S / (3 * SIG * Omega) / sec_in_year
ratio = t_PR / t_col
log_ratio = np.log10(ratio)

# Figure setup
fig, ax = plt.subplots(figsize=(8, 6))
abs_max = np.nanmax(np.abs(log_ratio))
norm = colors.TwoSlopeNorm(vcenter=0, vmin=-abs_max, vmax=abs_max)
pcm = ax.pcolormesh(np.log10(S), np.log10(SIG), log_ratio,
                    cmap='RdBu_r', norm=norm, shading='auto')
fig.colorbar(pcm, ax=ax, label=r'$\log_{10}(t_{\rm PR}/t_{\rm col})$')

# Draw boundaries
ax.contour(np.log10(S), np.log10(SIG), tau, levels=[1], colors='white',
           linestyles='--', linewidths=1)
ax.contour(np.log10(S), np.log10(SIG), beta, levels=[beta_crit], colors='red',
           linewidths=1)
ax.contour(np.log10(S), np.log10(SIG), t_PR/t_col, levels=[1], colors='cyan',
           linestyles='-.', linewidths=1)

# Hatch region satisfying three conditions
mask = (tau < 1) & (beta > beta_crit) & (t_PR < t_col)
ax.contourf(np.log10(S), np.log10(SIG), mask.astype(int), levels=[0.5, 1.5],
            hatches=['////'], colors='none', alpha=0)

# Axis labels and title
ax.set_xlabel(r'Particle radius $\log_{10} s\, [\mathrm{m}]$')
ax.set_ylabel(r'Surface density $\log_{10} \Sigma\, [\mathrm{kg\,m^{-2}}]$')
ax.set_title('Static timescale map around Mars')

# Save figure
os.makedirs('output', exist_ok=True)
plt.savefig(os.path.join('output', 'fig_static_map.png'), dpi=300)
import os  # ADD: 画像保存用ディレクトリ作成に使用

rho = 3000               # 粒子密度 [kg m^-3]
AU = 1.496e11           # m
a_Mars = 1.52 * AU
G = 6.674e-11
M_Mars = 6.42e23        # kg
R_Mars = 3.39e6         # m
a_ring = 3 * R_Mars
M_Sun = 1.989e30        # kg
sigma_sb = 5.670374419e-8
T_Mars = 210            # K
L_Mars = 4 * np.pi * R_Mars ** 2 * sigma_sb * T_Mars ** 4
c = 2.99792458e8        # m/s

# 火星の放射圧パラメータ
T_mars = 2000            # 火星の有効温度 [K]
Q_pr = 1.0               # 放射圧係数

R_mars = 3.39e6          # 火星半径 [m]
M_mars = 6.42e23         # 火星質量 [kg]
sigma_sb = 5.670374419e-8  # Stefan-Boltzmann 定数 [W m^-2 K^-4]
G = 6.67430e-11          # 万有引力定数 [m^3 kg^-1 s^-2]
c = 2.99792458e8         # 光速 [m s^-1]

s      = np.logspace(-6, 0, 400)   # 粒子半径 1 µm – 1 m
Sigma  = np.logspace(2, 6, 400)    # 表面質量密度 1e2 – 1e6 kg m^-2
S, SIG = np.meshgrid(s, Sigma)

tau = 3*SIG/(4*rho*S)    # 幾何学光学的厚さ

fig, ax = plt.subplots(figsize=(7,5))
pcm = ax.pcolormesh(S, SIG, np.log10(tau), cmap='viridis', shading='auto')
fig.colorbar(pcm, label=r'$\log_{10}\tau_{\rm geo}$')
ax.contour(S, SIG, tau, levels=[1], colors='w', linestyles='--', label=r'$\tau=1$')

# β_eff = β_Mars + β⊙-Mars (Burns et al. 1979)
beta_sun_mars = (5.7e-4 / (rho * S)) * (M_Sun / M_Mars) * (a_ring ** 2 / a_Mars ** 2)
beta_mars = 3 * L_Mars / (16 * np.pi * c * G * M_Mars * rho * S)
beta_eff = beta_mars + beta_sun_mars
# β parameter (Burns et al. 1979)
beta_sun = 5.7e-4 / (rho * S)            # 太陽による放射圧
L_mars = 4 * np.pi * R_mars**2 * sigma_sb * T_mars**4
beta_mars = (3 * L_mars * Q_pr) / (16 * np.pi * G * M_mars * c * rho * S)
beta_tot = beta_sun + beta_mars
Omega = 3.986e14 / (2.28e11)**3          # Mars GM/a^3, a=2.28e11 m

# Hill critical beta
beta_crit = (1/3)*(6.42e23/1.99e30)*(2.28e11/(3*3.39e6))**3   # ~0.03

# PR vs collision times
t_col = 4*rho*S / (3*SIG*Omega)          # Omega from Mars GM/a^3
t_PR_sun = 550*(rho/3000)*(S/1e-6)*(1.52)**2  # yr
t_PR = t_PR_sun * (beta_sun / beta_tot)

# Plot boundaries
ax.contour(S, SIG, beta_eff, levels=[beta_crit], colors='r', label='β=βcrit')
ax.contour(S, SIG, beta_tot, levels=[beta_crit], colors='r', label='β=βcrit')
ax.contour(S, SIG, t_col/t_PR, levels=[1], colors='cyan', linestyles='-.', label='t_col=t_PR')

ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlabel('Particle radius $s$ [m]')
ax.set_ylabel('Surface density $\\Sigma$ [kg m$^{-2}$]')
ax.set_title('Optical depth map ($\\rho$=3000 kg m$^{-3}$)')
os.makedirs("output", exist_ok=True)  # ADD: 出力フォルダを自動作成
plt.savefig("output/fig_optical_depth_map.png", dpi=300)  # ADD: 画像保存
plt.show()

