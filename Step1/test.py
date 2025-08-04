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
plt.show()

