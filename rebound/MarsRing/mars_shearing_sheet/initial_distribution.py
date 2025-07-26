#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import matplotlib.pyplot as plt
import matplotlib.patches as patches

# C プログラム実行後に生成されたファイル
data_file = "initial_particles.txt"
# problem.c と同じ boxsize を設定
boxsize = 100  # [m]

# データ読み込み
particles = []
with open(data_file, 'r') as f:
    for line in f:
        x, y, r = map(float, line.split())
        particles.append((x, y, r))

# プロット
fig = plt.figure(figsize=(8,8))
ax = fig.add_subplot(111, aspect='equal')
ax.set_xlabel("azimuthal coordinate [m]")
ax.set_ylabel("radial coordinate [m]")
ax.set_xlim(-boxsize/2., boxsize/2.)
ax.set_ylim(-boxsize/2., boxsize/2.)

for x, y, radius in particles:
    circ = patches.Circle((y, x), radius, facecolor='darkgray', edgecolor='black', linewidth=0.5)
    ax.add_patch(circ)

plt.tight_layout()
plt.savefig("particle_distribution.png", dpi=150)
print("Saved particle_distribution.png")