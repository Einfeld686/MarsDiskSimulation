#!/usr/bin/env python

import numpy as np
import time
import sys

# スクリプトの開始時間を記録
start_time = time.time()

def track_composition():
    # まず "composition_input.txt" を開いて、初期の組成情報（ハッシュ、質量、各化学種の相対存在量）を読み込む
    f = open("composition_input.txt", 'r')
    init_compositions = [line.split() for line in f.readlines()]
    
    # 各行について、2列目より後ろ(化学種の存在量)が必ず合計1になるかを確認
    for line in init_compositions:
        try:
            sum([float(x) for x in line[2:]]) == 1.0
        except:
            print ('ERROR: Realative abundances do not add up to 1.0')
            sys.exit(1)

    # 1列目(ハッシュ値)を整数として取り出すが、エラーが出る場合は x[0].value から取得（再現性のためにトライしている模様）
    try:
        init_hashes = [int(x[0]) for x in init_compositions]
    except:
        init_hashes = [x[0].value for x in init_compositions]

    # 化学種の数(no_species)を、初期入力の行の要素数から割り出す(最初2列は ハッシュ と 質量 なので、それ以外を化学種とみなす)
    no_species = len(init_compositions[0]) - 2

    # 衝突情報が書かれたファイル "collision_report.txt" を開き、行単位に読み込む
    file = open("collision_report.txt", 'r')
    blocks = file.read().split("\n")
    # 空行(文字数が0の行)は除去
    blocks = [block for block in blocks if len(block) > 0]

    # compositions に初期組成情報を格納
    compositions = init_compositions

    # 衝突記録ファイルの各行(block)を順に処理
    for i in range(len(blocks)):
        block = blocks[i].split()
        time = float(block[0])             # 衝突が起きた時刻
        collision_type = int(block[1])     # 衝突タイプ

        # 衝突タイプが 0 (ELASTIC BOUNCE) の場合は何もせず次へ
        if collision_type == 0:
            continue

        # ターゲットのハッシュ、質量
        target_hash = int(block[2])
        target_mass = float(block[3])
        # 衝突体（プロジェクタイル）のハッシュ
        projectile_hash = int(block[4])

        # compositions リストの中からターゲット/衝突体のインデックスを探索
        targ_idx = [i for i in range(len(compositions)) if int(compositions[i][0]) == target_hash][0]
        proj_idx = [i for i in range(len(compositions)) if int(compositions[i][0]) == projectile_hash][0]

        # ターゲットと衝突体それぞれの「直前の」質量を参照
        last_target_mass = float(compositions[targ_idx][1])
        last_proj_mass = float(compositions[proj_idx][1])
        # ターゲットと衝突体の化学種の存在量を取得
        last_target_abundances = compositions[targ_idx][-no_species:]
        last_projectile_abundances = compositions[proj_idx][-no_species:]

        # block の残りから破片の情報（ハッシュと質量）を取り出す
        # 衝突記録は [time, collision_type, target_hash, target_mass, projectile_hash, (frag_hash, frag_mass), (frag_hash, frag_mass), ...]
        # なので、(len(block)-5)/2 個の破片があると判断
        no_frags = int((len(block) - 5)/2)
        frag_hashes = [int(block[i*2+3]) for i in range(1, no_frags+1)]
        frag_masses = [float(block[i*2+4]) for i in range(1, no_frags+1)]

        # 各衝突タイプ別に組成を更新
        # 1 => 完全合体 (perfect merger)
        if collision_type == 1:
            # 新しいターゲット質量が target_mass で、ターゲット＋衝突体の組成を質量加重平均
            for i in range(no_species):
                compositions[targ_idx][i+2] = (float(last_target_abundances[i]) * last_target_mass
                                               + float(last_projectile_abundances[i]) * last_proj_mass) / target_mass

        # 2 => 部分的合体 (partial accretion)
        if collision_type == 2:
            # ターゲット側は "質量が増えたぶん" を衝突体から取り込む
            mass_accreted = target_mass - last_target_mass
            for i in range(no_species):
                compositions[targ_idx][i+2] = (float(last_target_abundances[i]) * last_target_mass
                                               + float(last_projectile_abundances[i]) * mass_accreted) / target_mass
            # 残りの衝突体質量は破片として生成される -> 破片を compositions に新規追加
            for j in range(no_frags):
                frag_data = [frag_hashes[j], frag_masses[j]] + last_projectile_abundances
                compositions.append(frag_data)
                # 負の値がないか安全チェック
                try:
                    any(n < 0 for n in frag_data) == False
                except:
                    print ('ERROR: Negative value encountered in frag data at', time)
                    sys.exit(1)

        # 3,4 => 部分的侵食 or 超破壊 (partial erosion, super-catastrophicなど)
        # (collision_type == 3 or 4 の場合はターゲットの質量が減る)
        if collision_type == 3 or collision_type == 4:
            # ターゲットが失った質量
            mass_lost = last_target_mass - target_mass
            # 破片の組成は「失われたターゲット分 + 衝突体の全質量」に基づく加重平均
            # 破片の合計質量は frag_masses の合計(= project + 失われたtarget分?)
            frag_abundances = [
                ( float(last_target_abundances[i]) * mass_lost
                  + float(last_projectile_abundances[i]) * last_proj_mass )
                / np.sum(frag_masses)
                for i in range(no_species)
            ]
            # 破片を追加
            for j in range(no_frags):
                frag_data = [frag_hashes[j], frag_masses[j]] + frag_abundances
                try:
                    any(n < 0 for n in frag_data) == False
                except:
                    print ('ERROR: Negative value encountered in frag data at', time)
                    sys.exit(1)
                compositions.append(frag_data)

        # ターゲットの質量を更新 (合体や侵食後の新しい質量)
        compositions[targ_idx][1] = target_mass

        # ターゲットの組成配列に負の値がないか検証
        try: 
            any(n < 0 for n in compositions[targ_idx]) == False
        except:
            print ('ERROR: Negative value encountered at', time)
            sys.exit(1)

    return compositions

def write_output(compositions):
    # 最終的な組成情報を "composition_output.txt" に書き込む
    f = open("composition_output.txt", "w")
    for body in compositions:
        proper = '[%s]' % ' '.join(map(str, body))  # リストをスペース区切り文字列へ
        f.write(proper[1:-1] + "\n")                # 先頭と末尾の[] は削除して書き込む
    f.close()

# 上記の関数を使って組成追跡 → 書き出し
write_output(track_composition())

# スクリプトの実行時間を表示
print("--- %s seconds ---" % (time.time() - start_time))