import numpy as np
import matplotlib.pyplot as plt
import os  # ADD: 画像保存用ディレクトリ作成に使用

rho = 3000               # 粒子密度 [kg m^-3]

s      = np.logspace(-6, 0, 400)   # 粒子半径 1 µm – 1 m
Sigma  = np.logspace(2, 6, 400)    # 表面質量密度 1e2 – 1e6 kg m^-2
S, SIG = np.meshgrid(s, Sigma)

tau = 3*SIG/(4*rho*S)    # 幾何学光学的厚さ

fig, ax = plt.subplots(figsize=(7,5))
pcm = ax.pcolormesh(S, SIG, np.log10(tau), cmap='viridis', shading='auto')
fig.colorbar(pcm, label=r'$\log_{10}\tau_{\rm geo}$')
ax.contour(S, SIG, tau, levels=[1], colors='w', linestyles='--', label=r'$\tau=1$')

# β parameter (Burns et al. 1979)
beta = 5.7e-4 / (rho * S)                # S in m, rho in kg/m^3
Omega = 3.986e14 / (2.28e11)**3          # Mars GM/a^3, a=2.28e11 m

# Hill critical beta
beta_crit = (1/3)*(6.42e23/1.99e30)*(2.28e11/(3*3.39e6))**3   # ~0.03

# PR vs collision times
t_col = 4*rho*S / (3*SIG*Omega)          # Omega from Mars GM/a^3
t_PR  = 550*(rho/3000)*(S/1e-6)*(1.52)**2  # yr

# Plot boundaries
ax.contour(S, SIG, beta, levels=[beta_crit], colors='r', label='β=βcrit')
ax.contour(S, SIG, t_col/t_PR, levels=[1], colors='cyan', linestyles='-.', label='t_col=t_PR')

ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlabel('Particle radius $s$ [m]')
ax.set_ylabel('Surface density $\\Sigma$ [kg m$^{-2}$]')
ax.set_title('Optical depth map ($\\rho$=3000 kg m$^{-3}$)')
os.makedirs("output", exist_ok=True)  # ADD: 出力フォルダを自動作成
plt.savefig("output/fig_optical_depth_map.png", dpi=300)  # ADD: 画像保存
plt.show()
