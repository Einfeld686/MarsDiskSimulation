/**
 * Shearing sheet with diagnostics
 *
 * This example simulates a small patch of Saturn's
 * Rings in shearing sheet coordinates. It also calculated
 * various quantities which can be used as diagnostics for
 * dynamical models of the rings. Diagnostics include
 * the midplane filling factor, the mean normal optical 
 * depth, the velocity dispersion tensor, the 
 * translational viscosity and the collisional viscosity.
 */

#include <stdio.h>               /* 標準入出力のためのヘッダ */
#include <stdlib.h>              /* malloc、randなどの標準ライブラリ関数 */
#include <math.h>                /* 数学関数(M_PIなど)を使用するためのヘッダ */
#include "src/rebound.h"         /* REBOUNDのメインライブラリをインクルード */
// #include "fragmentation.c"       /* フラグメンテーションモデルの関数をインクルード */

/*
 * この例では、衝突時の相対速度に依存した反発係数 (coefficient of restitution) をBridgesらの式に基づいて定義する。
 */
double coefficient_of_restitution_bridges(const struct reb_simulation* const r, double v){ls -l shearing_sheet.c
    // vを[m/s]として仮定
    double eps = 0.32*pow(fabs(v)*100.,-0.234);    /* v[m/s]をcm/sに換算して、経験式に当てはめ */
    if (eps>1) eps=1;                             /* 反発係数は最大1 */
    if (eps<0) eps=0;                             /* 反発係数は最小0 */
    return eps;
}

/* タイムステップごとや一定間隔ごとに呼ばれるコールバック関数のプロトタイプ宣言 */
void heartbeat(struct reb_simulation* const r);

int main(int argc, char* argv[]) {
    /* REBOUNDのシミュレーション構造体を作成 */
    struct reb_simulation* r = reb_simulation_create();
    
    /*
     * REBOUNDの可視化サーバを起動して、ブラウザで http://localhost:1234 にアクセスすることで
     * リアルタイムにシミュレーションを可視化できるようにする
     */
    reb_simulation_start_server(r, 1234);

    // 各種定数・パラメータの設定
    r->opening_angle2     = .5;                /* ツリーコード重力計算の精度(開口角^2)を設定 */
    r->integrator         = REB_INTEGRATOR_SEI;/* シアリングシートに適した積分器SEIを使用 */
    r->boundary           = REB_BOUNDARY_SHEAR; /* シアリングシート境界条件を使用 */
    r->gravity            = REB_GRAVITY_TREE;   /* 重力計算にツリーコードを使用 */
    r->collision          = REB_COLLISION_TREE; /* 衝突判定もツリーを用いて行う */
    r->collision_resolve  = reb_collision_resolve_hardsphere; /* 衝突解決: ハードスフィアモデル */
    double OMEGA          = 0.00013143527;     /* シアリングシートの回転角速度 [1/s] */
    r->ri_sei.OMEGA       = OMEGA;             /* SEI積分器用に角速度をセット */
    r->G                  = 6.67428e-11;       /* 重力定数 [m^3/(kg·s^2)] */
    r->softening          = 0.1;               /* ソフトニング長さ [m] */
    r->dt                 = 1e-3*2.*M_PI/OMEGA;/* タイムステップ [s] */
    r->heartbeat          = heartbeat;         /* タイムステップごとに呼ばれる関数を指定 */

    /*
     * この例では x, y 方向に2つずつのroot boxを使用。
     * (並列化などで利点がある; Rein & Liu参照)
     */
    double surfacedensity         = 400;       /* 面密度 [kg/m^2] */
    double particle_density       = 400;       /* 粒子内部密度 [kg/m^3] */
    double particle_radius_min    = 1;         /* 粒子半径の最小値 [m] */
    double particle_radius_max    = 4;         /* 粒子半径の最大値 [m] */
    double particle_radius_slope  = -3;        /* 粒子半径のパワーロー指数 */
    double boxsize                = 100;       /* シアリングシート領域の一辺 [m] */
    reb_simulation_configure_box(r, boxsize, 2, 2, 1); /* boxsizeを使い、x,y方向に2分割 */
    r->N_ghost_x = 2;    /* ゴーストボックスの数(周期境界やシア境界に必要) */
    r->N_ghost_y = 2;    
    r->N_ghost_z = 0;

    // Bridgesらの経験式に基づく反発係数を使うよう設定
    r->coefficient_of_restitution = coefficient_of_restitution_bridges;
    /*
     * 相対速度が0に近い衝突の場合、次のステップで粒子がめり込むのを防ぐために
     * 最小衝突速度を設定して微小な反発を与える
     */
    r->minimum_collision_velocity = particle_radius_min*OMEGA*0.001;  /* シアによる速度の極小部分を付与 */

    /* リング中の粒子を追加していく */
    double total_mass = surfacedensity*r->boxsize.x*r->boxsize.y; /* シート面積×面密度から総質量を算出 */
    double mass = 0;
    while(mass<total_mass){
        struct reb_particle pt;
        /* 粒子位置をシアリングシート領域内にランダム配置 */
        pt.x         = reb_random_uniform(r, -r->boxsize.x/2.,r->boxsize.x/2.);
        pt.y         = reb_random_uniform(r, -r->boxsize.y/2.,r->boxsize.y/2.);
        pt.z         = reb_random_normal(r, 1.);        /* z方向は正規分布でランダムに */
        
        /* 速度はシアリングシート特有の -1.5*OMEGA*x (y方向) を与える */
        pt.vx        = 0;
        pt.vy        = -1.5*pt.x*OMEGA;
        pt.vz        = 0;

        /* 加速度(初期値は0) */
        pt.ax        = 0;
        pt.ay        = 0;
        pt.az        = 0;

        /* 粒子半径をパワーロー分布でサンプリング */
        double radius = reb_random_powerlaw(r, particle_radius_min, particle_radius_max, particle_radius_slope);
        pt.r = radius;  /* [m] */

        /* 粒子質量 = 体積×密度 */
        double particle_mass = particle_density*4./3.*M_PI*radius*radius*radius;
        pt.m = particle_mass;   /* [kg] */

        /* シミュレーションへ粒子を追加 */
        reb_simulation_add(r, pt);
        mass += particle_mass;  /* 累積質量を足して制限に達するまで繰り返す */
    }

    /* シミュレーションを無制限に積分開始(実際にはheartbeat内で途中出力) */
    reb_simulation_integrate(r, INFINITY);
}

/* 平均法線方向の幾何学的光学的厚みを計算 */
double mean_normal_geometric_optical_depth(const struct reb_simulation* const r){
    double area = 0.;
    for (int i=0;i<r->N;i++){
        struct reb_particle p = r->particles[i];
        area += M_PI*p.r*p.r;  /* 粒子の断面積(πr^2)を合計 */
    }
    return area/(r->boxsize.x*r->boxsize.y);   /* シート面積で割ってτを求める */
}

/* z=0付近での充填率を計算する関数 */
double midplane_fillingfactor(const struct reb_simulation* const r){
    double area = 0.;
    for (int i=0;i<r->N;i++){
        struct reb_particle p = r->particles[i];
        double R2 = p.r*p.r - p.z*p.z;
        /*
         * 粒子中心のz座標が半径以内にあれば中面を通過しているとみなし、断面積を合計
         *  (p.r^2 - p.z^2) が正であれば円形断面の一部がmidplaneを貫く
         */
        if (R2>0.){
            area += M_PI*R2;
        }
    }
    return area/(r->boxsize.x*r->boxsize.y);
}

/* 速度分散を計算するための関数。シア速度分を補正して分散を求める */
struct reb_vec3d velocity_dispersion(const struct reb_simulation* const r){
    // 安定した平均・分散計算アルゴリズム (丸め誤差低減)
    struct reb_vec3d A = {.x=0, .y=0, .z=0}; /* 平均速度(シア補正込み) */
    struct reb_vec3d Q = {.x=0, .y=0, .z=0}; /* 分散の累積計算用 */

    for (int i=0;i<r->N;i++){
        struct reb_vec3d Aim1 = A;
        struct reb_particle p = r->particles[i];
        // x速度はそのまま、 y速度は +1.5*OMEGA*x を加算した相対速度
        A.x = A.x + (p.vx-A.x)/(double)(i+1);
        A.y = A.y + (p.vy+1.5*r->ri_sei.OMEGA*p.x-A.y)/(double)(i+1);
        A.z = A.z + (p.vz-A.z)/(double)(i+1);

        Q.x = Q.x + (p.vx-Aim1.x)*(p.vx-A.x);
        Q.y = Q.y + (p.vy+1.5*r->ri_sei.OMEGA*p.x-Aim1.y)*(p.vy+1.5*r->ri_sei.OMEGA*p.x-A.y);
        Q.z = Q.z + (p.vz-Aim1.z)*(p.vz-A.z);
    }
    // 分散(標準偏差)を求める
    Q.x = sqrt(Q.x/(double)r->N);
    Q.y = sqrt(Q.y/(double)r->N);
    Q.z = sqrt(Q.z/(double)r->N);

    return Q; 
}

/* 並進粘度(translational viscosity)を計算する関数 */
double translational_viscosity(const struct reb_simulation* const r){
    double Wxy = 0.;
    for (int i=0;i<r->N;i++){
        struct reb_particle p = r->particles[i];
        double vx = p.vx;
        double vy = p.vy+1.5*r->ri_sei.OMEGA*p.x; /* シア補正 */
        Wxy += vx*vy;  /* x方向速度×(補正後のy方向速度) を積算 */
    }
    return 2./3.*Wxy/r->N/r->ri_sei.OMEGA; /* 2/3 ×(平均xy積) / Ω で並進粘度を見積もる */
}

/* 衝突による角運動量散逸から粘度を見積もる関数 (衝突粘度) */
double collisional_viscosity(const struct reb_simulation* const r){
    // 時間平均で計算される (リセットにはr->collisions_plog=0;を行う)
    double Mtotal = 0.;
    for (int i=0;i<r->N;i++){
        Mtotal += r->particles[i].m;
    }
    /* collisions_plog は衝突モデルで蓄積された角運動量散逸量などを記録する変数 */
    return 2./3./r->ri_sei.OMEGA/Mtotal/r->t* r->collisions_plog;
}

/* タイムステップ(または指定間隔)ごとに呼ばれるコールバック関数 */
void heartbeat(struct reb_simulation* const r){
    // 指定したステップ間隔でチェック(ここでは1e-3*2π/Ω)
    if (reb_simulation_output_check(r, 1e-3*2.*M_PI/r->ri_sei.OMEGA)){
        /* midplaneの充填率を表示 */
        printf("Midplane FF=  %5.3f\t",midplane_fillingfactor(r));
        /* 法線方向の幾何学的光学的厚み(τ)を表示 */
        printf("Mean normal tau=  %5.3f \t",mean_normal_geometric_optical_depth(r));
        /* 速度分散を計算 */
        struct reb_vec3d Q = velocity_dispersion(r);
        /* x, y, z各方向の分散を出力 */
        printf("<vxvx>,<vyvy>,<vzvz>= %5.3e %5.3e %5.3e\t",Q.x, Q.y, Q.z);
        /* 並進粘度 */
        printf("nu_trans= %5.3e\t",translational_viscosity(r));
        /* 衝突粘度 */
        printf("nu_col= %5.3e\t",collisional_viscosity(r));

        printf("\n");
    }
}