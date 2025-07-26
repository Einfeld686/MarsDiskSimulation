#!/usr/bin/env python

import numpy as np
import time
import sys

start_time = time.time()
def track_composition():
    import sys
    # 初期データを読み込み、型変換と検証を行う
    with open("composition_input.txt", 'r') as f:
        init_lines = [line.strip().split() for line in f if line.strip()]
    compositions = []
    for line in init_lines:
        hash_id = int(line[0])
        mass = float(line[1])
        abundances = [float(x) for x in line[2:]]
        if abs(sum(abundances) - 1.0) > 1e-6:
            print(f"ERROR: Relative abundances for hash {hash_id} do not sum to 1.0")
            sys.exit(1)
        compositions.append([hash_id, mass] + abundances)
    # ハッシュIDからインデックスへのマッピングを作成
    comp_index = {comp[0]: idx for idx, comp in enumerate(compositions)}

    # 衝突レポートを読み込み
    with open("collision_report.txt", 'r') as file:
        blocks = [b for b in file.read().splitlines() if b]
    for block_line in blocks:
        parts = block_line.split()
        t = float(parts[0])
        collision_type = int(parts[1])
        if collision_type == 0:
            continue
        target_hash = int(parts[2])
        target_mass = float(parts[3])
        projectile_hash = int(parts[4])
        # 安全にインデックスを取得
        if target_hash not in comp_index:
            print(f"ERROR: Target hash {target_hash} not found at time {t}")
            continue
        if projectile_hash not in comp_index:
            print(f"ERROR: Projectile hash {projectile_hash} not found at time {t}")
            continue
        targ_idx = comp_index[target_hash]
        proj_idx = comp_index[projectile_hash]
        last_target_mass = compositions[targ_idx][1]
        last_proj_mass = compositions[proj_idx][1]
        last_target_abund = compositions[targ_idx][2:]
        last_proj_abund = compositions[proj_idx][2:]
        no_frags = (len(parts) - 5) // 2
        # 断片データを正しく取得
        frag_hashes = [int(parts[5 + i*2]) for i in range(no_frags)]
        frag_masses = [float(parts[6 + i*2]) for i in range(no_frags)]
        # 衝突タイプごとの処理
        if collision_type == 1:
            # 完全合体
            new_abund = [
                (last_target_abund[i] * last_target_mass + last_proj_abund[i] * last_proj_mass) / target_mass
                for i in range(len(last_target_abund))
            ]
            compositions[targ_idx][1] = target_mass
            compositions[targ_idx][2:] = new_abund
        elif collision_type == 2:
            # 部分合体
            mass_accreted = target_mass - last_target_mass
            new_abund = [
                (last_target_abund[i] * last_target_mass + last_proj_abund[i] * mass_accreted) / target_mass
                for i in range(len(last_target_abund))
            ]
            compositions[targ_idx][1] = target_mass
            compositions[targ_idx][2:] = new_abund
            # 断片をリストに追加し、インデックスマッピングを更新
            for j, fh in enumerate(frag_hashes):
                frag_data = [fh, frag_masses[j]] + last_proj_abund
                compositions.append(frag_data)
                comp_index[fh] = len(compositions) - 1
        elif collision_type in (3, 4):
            # 部分侵食
            mass_lost = last_target_mass - target_mass
            denom = sum(frag_masses)
            frag_abund = [
                (last_target_abund[i] * mass_lost + last_proj_abund[i] * last_proj_mass) / denom
                for i in range(len(last_target_abund))
            ]
            compositions[targ_idx][1] = target_mass
            for j, fh in enumerate(frag_hashes):
                frag_data = [fh, frag_masses[j]] + frag_abund
                compositions.append(frag_data)
                comp_index[fh] = len(compositions) - 1
    return compositions

def write_output(compositions):
    f = open("composition_output.txt", "w")
    for body in compositions:
        proper = '[%s]' % ' '.join(map(str, body))
        f.write(proper[1:-1]+"\n")
    f.close()

write_output(track_composition())


print("--- %s seconds ---" % (time.time() - start_time))
