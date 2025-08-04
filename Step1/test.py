import numpy as np
import matplotlib.pyplot as plt
import os  # ADD: 画像保存用ディレクトリ作成に使用

rho = 3000               # 粒子密度 [kg m^-3]

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
ax.contour(S, SIG, beta_tot, levels=[beta_crit], colors='r', label='β=βcrit')
ax.contour(S, SIG, t_col/t_PR, levels=[1], colors='cyan', linestyles='-.', label='t_col=t_PR')

ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlabel('Particle radius $s$ [m]')
ax.set_ylabel('Surface density $\\Sigma$ [kg m$^{-2}$]')
ax.set_title('Optical depth map ($\\rho$=3000 kg m$^{-3}$)')
os.makedirs("output", exist_ok=True)  # ADD: 出力フォルダを自動作成
plt.savefig("output/fig_optical_depth_map.png", dpi=300)  # ADD: 画像保存
plt.show()
