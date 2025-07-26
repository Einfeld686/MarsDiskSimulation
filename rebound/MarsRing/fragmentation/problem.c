#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <math.h>
#include "src/rebound.h"


// 最小の破片質量
double min_frag_mass = 1.4e-8;
// 破片数の合計（リスタートする場合などに再設定が必要）
int tot_no_frags = 0;

// 最小値と最大値を返すマクロ
#define MIN(a, b) ((a) > (b) ? (b) : (a))    ///< aとbのうち小さいほうを返す
#define MAX(a, b) ((a) > (b) ? (a) : (b))    ///< aとbのうち大きいほうを返す

// 衝突に関するパラメータをまとめた構造体
struct collision_params
{
    int target;                 // 衝突対象となる粒子のインデックス
    int projectile;             // 衝突してくる粒子のインデックス
    double dx;                  // 相対座標(x方向)
    double dy;                  // 相対座標(y方向)
    double dz;                  // 相対座標(z方向)
    double b;                   // 衝突パラメータ(インパクトパラメータ)
    double Vix;                 // 相対速度ベクトル(x方向)
    double Viy;                 // 相対速度ベクトル(y方向)
    double Viz;                 // 相対速度ベクトル(z方向)
    double Vi;                  // 相対速度ベクトルの大きさ
    double l;                   // 重なりの長さのようなパラメータ
    double rho1;                // 定数密度を想定するときの密度
    double cstar;               // 衝突エネルギー評価に使う定数
    double mu;                  // 二体衝突における還元質量や関数で使われるパラメータ
    double QR;                  // (使用されていない？) 衝突エネルギー関連パラメータの候補
    double QpRD;                // (使用されていない？) 同上
    double V_esc;               // 逃亡速度(相互重力による二体の脱出速度) 
    double separation_distance; // 衝突後に破片を配置する初期分離距離
    double Mlr;                 // Largest Remnant (最大の残骸の質量) 
    double Mslr;                // Second Largest Remnant (2番目に大きな残骸の質量)
    double Q;                   // 衝突エネルギー/単位質量のような値
    double Mlr_dag;             // Chambersの式で使う補正後のMlr候補
    double Q_star;              // 臨界衝突エネルギーに相当するパラメータ
    double vrel;                // 相対速度の大きさ
    double xrel;                // 衝突時の相対距離
    int collision_type;         // 衝突のタイプを表すためのフラグ（0～4）
    int no_frags;               // 新規に追加された破片数
}; 


// 2点の座標から相対ベクトル(x, y, z)を求める関数（ガリレイ変換に相当）
void make_vector(double x1, double y1, double z1, double x2, double y2, double z2, double *x, double*y, double*z){
    *x = x1-x2;
    *y = y1-y2;
    *z = z1-z2;
}

// 2つのベクトルのドット積を求める
double get_dot(double x1, double y1, double z1, double x2, double y2, double z2){
    return (x1*x2)+(y1*y2)+(z1*z2);
}

// ベクトル(x, y, z)の大きさ（ノルム）を返す
double get_mag(double x, double y, double z){
    return sqrt(pow(x,2)+pow(y,2)+pow(z,2));
}

// 質量mと密度rhoから球半径を求める（(3m)/(4πρ))^(1/3)
double get_radii(double m, double rho){
    return pow((3*m)/(4*M_PI*rho),1./3.);
}

// 衝突後の破片を追加する関数
void add_fragments(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){
    // 衝突対象と衝突粒子のポインタを取得
    struct reb_particle* target = &(r->particles[params->target]);
    struct reb_particle* projectile = &(r->particles[params->projectile]);
    // 衝突対象と衝突粒子から重心を求める
    struct reb_particle com = reb_particle_com_of_pair(*target, *projectile);

    // 最初の合計質量
    double initial_mass = target -> m + projectile -> m;
    // Mlr（最大残骸）を除いた残りの質量
    double remaining_mass = initial_mass - params->Mlr;
    // ターゲットの密度（半径や質量から逆算）
    double rho = target->m/(4./3*M_PI*pow(target ->r, 3));
    // 衝突時の合体半径
    double rtot = target -> r + projectile -> r;

    // 大きな破片があるかどうかを示すフラグ
    int big_frags = 0;
    if (params->Mslr > 0){
        // 2番目に大きい破片Mslrを減らす
        remaining_mass = remaining_mass -  params->Mslr;
        big_frags = 1;
    }

    // 上記から計算した残り質量を、最小の破片質量で割って破片の個数を決める
    int no_frags = remaining_mass/min_frag_mass;
    double frag_mass = remaining_mass/no_frags;

    // 合計で追加する新しい粒子数（破片数 + 2番目に大きい破片があるならそれも含む）
    int new_bodies = no_frags + big_frags;
    params->no_frags = new_bodies;

    // 文字列用バッファ、運動量合計用の変数を用意
    char hash[20];
    double mxsum[3] = {0,0,0};    // 質量×位置の合計
    double mvsum[3] = {0,0,0};    // 質量×速度の合計

    // ターゲットがMlrの質量を持ち、重心位置と速度を引き継ぐ
    target -> last_collision = r->t;
    target -> m = params->Mlr;
    target -> r = get_radii(params->Mlr, rho);
    target->x = com.x;
    target->y = com.y;
    target->z = com.z;

    target->vx = com.vx;
    target->vy = com.vy;
    target->vz = com.vz;

    // もし破片数が1個で、それがtargetより大きい場合の処理（fragmentとtargetを入れ替えるような感じ）
    if (no_frags == 1 && params->Mlr <= frag_mass){
        target->m = frag_mass;
        target -> r = get_radii(frag_mass, rho);
        frag_mass = params->Mlr;
    }

    // 運動量合計を更新（ターゲット分）
    mxsum[0] = mxsum[0] + target->m*target->x;
    mxsum[1] = mxsum[1] + target->m*target->y;
    mxsum[2] = mxsum[2] + target->m*target->z;

    mvsum[0] = mvsum[0] + target->m*target->vx;
    mvsum[1] = mvsum[1] + target->m*target->vy;
    mvsum[2] = mvsum[2] + target->m*target->vz;

    // 破片を配置する角度間隔
    double theta_inc = (2.*M_PI)/new_bodies;

    // 衝突面に関連する単位ベクトルや正規ベクトルなどを用意する計算
    double unit_vix, unit_viy, unit_viz, zx, zy, zz, z, ox, oy, oz, o;

    // 衝突方向の単位ベクトル
    unit_vix = params->Vix/params->vrel;
    unit_viy = params->Viy/params->vrel;
    unit_viz = params->Viz/params->vrel;

    // 衝突面の法線ベクトル (vrel × xrel)
    zx = (params->Viy*params->dz - params->Viz*params->dy);
    zy = (params->Viz*params->dx - params->Vix*params->dz);
    zz = (params->Vix*params->dy - params->Viy*params->dx);

    // zは衝突面の法線ベクトルの大きさ
    z = get_mag(zx, zy, zz);

    // 衝突面の法線ベクトルの単位化
    zx = zx/z;
    zy = zy/z;
    zz = zz/z;

    // 衝突面内の、衝突速度に直交する方向のベクトルを計算 (z × vrel)
    ox = (zy*params->Viz - zz*params->Viy);
    oy = (zz*params->Vix - zx*params->Viz);
    oz = (zx*params->Viy - zy*params->Vix);

    // 上記ベクトルを単位化
    o = get_mag(ox, oy, oz);
    ox = ox/o;
    oy = oy/o;
    oz = oz/o;

    // 破片の初期速度を決定するための速度（Chambersのようなモデルを想定）
    double fragment_velocity = sqrt(1.1*pow(params->V_esc,2) - 2*r->G*initial_mass*(1./rtot - 1./params->separation_distance));

    // 2番目に大きい破片がある場合、最初に追加する
    if (big_frags == 1){
        struct reb_particle Slr1 = {0};
        Slr1.m = params->Mslr;
        // 破片を衝突方向に分離
        Slr1.x = com.x + params->separation_distance*unit_vix;
        Slr1.y = com.y + params->separation_distance*unit_viy;
        Slr1.z = com.z + params->separation_distance*unit_viz;

        Slr1.vx = com.vx + fragment_velocity*unit_vix;
        Slr1.vy = com.vy + fragment_velocity*unit_viy;
        Slr1.vz = com.vz + fragment_velocity*unit_viz;

        // 半径を密度から計算
        Slr1.r = get_radii(Slr1.m, rho);

        // ハッシュ名（ID相当）を生成
        snprintf(hash,"FRAG%d", tot_no_frags+1);
        Slr1.hash = reb_hash(hash);
        printf("%s hash, mass:      %u %e\n", hash, Slr1.hash, Slr1.m);

        // 運動量合計を更新
        mxsum[0] += Slr1.m*Slr1.x;
        mxsum[1] += Slr1.m*Slr1.y;
        mxsum[2] += Slr1.m*Slr1.z;

        mvsum[0] += Slr1.m*Slr1.vx;
        mvsum[1] += Slr1.m*Slr1.vy;
        mvsum[2] += Slr1.m*Slr1.vz;

        // 衝突時間を記録
        Slr1.last_collision = r->t;
        // シミュレーションに追加
        reb_simulation_add(r, Slr1);
    }

    // 破片群を追加（no_frags個）
    int new_beginning_frag_index = tot_no_frags+big_frags+1;
    for (int i=(new_beginning_frag_index); i<(new_beginning_frag_index+no_frags); i++){
        struct reb_particle fragment = {0};
        int j = i - new_beginning_frag_index+1;
        fragment.m = frag_mass;

        // 破片の初期位置: (衝突面で等間隔に配置)
        fragment.x = com.x + params->separation_distance*(cos(theta_inc*j)*unit_vix + sin(theta_inc*j)*ox);
        fragment.y = com.y + params->separation_distance*(cos(theta_inc*j)*unit_viy + sin(theta_inc*j)*oy);
        fragment.z = com.z + params->separation_distance*(cos(theta_inc*j)*unit_viz + sin(theta_inc*j)*oz);

        // 破片の初期速度
        fragment.vx = com.vx + fragment_velocity*(cos(theta_inc*j)*unit_vix + sin(theta_inc*j)*ox);
        fragment.vy = com.vy + fragment_velocity*(cos(theta_inc*j)*unit_viy + sin(theta_inc*j)*oy);
        fragment.vz = com.vz + fragment_velocity*(cos(theta_inc*j)*unit_viz + sin(theta_inc*j)*oz);

        // 破片の半径
        fragment.r = get_radii(frag_mass, rho);

        // 衝突時間を記録
        fragment.last_collision = r->t;

        // ハッシュ名(固有ID)の設定
        sprintf(hash, "FRAG%d", i);
        fragment.hash = reb_hash(hash);
        printf("%s hash, mass:      %u %e\n", hash, fragment.hash, fragment.m);

        // 運動量合計を更新
        mxsum[0] += fragment.m*fragment.x;
        mxsum[1] += fragment.m*fragment.y;
        mxsum[2] += fragment.m*fragment.z;

        mvsum[0] += fragment.m*fragment.vx;
        mvsum[1] += fragment.m*fragment.vy;
        mvsum[2] += fragment.m*fragment.vz;

        // シミュレーションに追加
        reb_simulation_add(r, fragment);
    }
    // トータルの破片数を更新
    tot_no_frags += big_frags+no_frags;

    // 運動量保存を満たすように位置と速度を微調整
    double xoff[3] = {com.x - mxsum[0]/initial_mass, com.y - mxsum[1]/initial_mass, com.z - mxsum[2]/initial_mass};
    double voff[3] = {com.vx - mvsum[0]/initial_mass, com.vy - mvsum[1]/initial_mass, com.vz - mvsum[2]/initial_mass};

    // ターゲットの修正
    target -> x +=  xoff[0]*target->m/initial_mass;
    target -> y += xoff[1]*target->m/initial_mass;
    target -> z += xoff[2]*target->m/initial_mass;
    target -> vx += voff[0]*target->m/initial_mass;
    target -> vy += voff[1]*target->m/initial_mass;
    target -> vz += voff[2]*target->m/initial_mass;

    // 新規に追加された全ての破片の位置速度をそれぞれの質量比で修正する
    for (int i=(tot_no_frags-new_bodies)+1; i<(tot_no_frags+1); i++){
        char frag[10];
        sprintf(frag, "FRAG%d", i);
        double mass_fraction = reb_simulation_particle_by_hash(r, reb_hash(frag))->m/initial_mass;

        reb_simulation_particle_by_hash(r, reb_hash(frag))->x += xoff[0]*mass_fraction;
        reb_simulation_particle_by_hash(r, reb_hash(frag))->y += xoff[1]*mass_fraction;
        reb_simulation_particle_by_hash(r, reb_hash(frag))->z += xoff[2]*mass_fraction;

        reb_simulation_particle_by_hash(r, reb_hash(frag))->vx += voff[0]*mass_fraction;
        reb_simulation_particle_by_hash(r, reb_hash(frag))->vy += voff[1]*mass_fraction;
        reb_simulation_particle_by_hash(r, reb_hash(frag))->vz += voff[2]*mass_fraction;
    }

    return;
}

// 質量や運動量を保存しつつターゲットに衝突粒子をマージする関数
void merge(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){
    struct reb_particle* pi = &(r->particles[params->target]);
    struct reb_particle* pj = &(r->particles[params->projectile]);

    // 合体後の1/(質量) を計算
    double invmass = 1.0/(pi->m + pj->m);
    // ターゲットの密度から合体後の半径を計算（ターゲットの密度を維持）
    double targ_rho = pi->m/(4./3*M_PI*pow(pi->r,3));

    // 運動量保存則を満たすように速度・位置を合成
    pi->vx = (pi->vx*pi->m + pj->vx*pj->m)*invmass;
    pi->vy = (pi->vy*pi->m + pj->vy*pj->m)*invmass;
    pi->vz = (pi->vz*pi->m + pj->vz*pj->m)*invmass;
    pi->x  = (pi->x*pi->m + pj->x*pj->m)*invmass;
    pi->y  = (pi->y*pi->m + pj->y*pj->m)*invmass;
    pi->z  = (pi->z*pi->m + pj->z*pj->m)*invmass;

    // 質量と半径の更新
    pi->m  = pi->m + pj->m;
    pi->r  = pow((3*pi->m)/(4*M_PI*targ_rho),1./3.);
    pi->last_collision = r->t;

    return;
}

// "hit_and_run"（すれ違い衝突）の場合の処理や、"partial erosion"（部分的な侵食）などを扱う
int hit_and_run(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){
    // ターゲット・衝突粒子へのポインタを確保
    struct reb_particle* target = &(r->particles[params->target]);
    struct reb_particle* projectile = &(r->particles[params->projectile]);

    // swapフラグ(どちらをremoveするか)の初期値
    int swap = 2;
    int i = c.p1;
    int j = c.p2;
    struct reb_particle* pi = &(r->particles[i]);
    struct reb_particle* pj = &(r->particles[j]);

    // 質量が小さい方を最終的にremoveすることが多いので、必要に応じてiとjを入れ替える
    if (pi->m < pj->m){
        swap = 1;
    }

    // Stewart & Leinhardt 2012 に基づく衝突パラメータの計算
    double phi = 2*acos((params->l-projectile->r)/projectile->r);
    // 射影面積(Leinhardt Eq.46)
    double A_interact = pow(projectile->r, 2)*((M_PI-(phi-sin(phi))/2.));
    // Leinhardt Eq. 47: 相互作用長さ
    double L_interact = 2.*pow(pow(target->r,2)-(pow(target->r-params->l/2.,2)), .5);
    // Chambers Eq.11:
    double beta = (A_interact*L_interact)/target->m;
    // 合体した天体の半径(仮定)
    double Rc1 = pow(3./(4.*M_PI*params->rho1)*(beta*target->m + projectile->m), 1./3.);
    double Q0 = .8*params->cstar*M_PI*params->rho1*r->G*pow(Rc1, 2);
    double gamma = (beta*target->m)/projectile->m;
    // 新たに計算される臨界衝突エネルギー
    double Q_star = (pow(1+gamma, 2)/4*gamma)* Q0;

    // Chambers Eq.13
    double mu = (beta*target->m*projectile->m)/(beta*target->m+projectile->m);
    // Chambers Eq.12
    double Q = .5*(mu*pow(params->Vi,2))/(beta*target->m+projectile->m);

    // いくつかの経験的定数
    double c1 = 2.43;
    double c2 = -0.0408;
    double c3 = 1.86;
    double c4 = 1.08;

    double targ_m = target->m;
    double imp_m = projectile->m;
    double zeta = pow((targ_m - imp_m)/(targ_m + imp_m),2);
    double fac = pow(1-params->b/(target->r + projectile->r),2.5);
    double v_crit = params->V_esc*(c1*zeta*fac + c2*zeta +c3*fac + c4);

    // 衝突速度が閾値v_crit以下なら合体する(Chambersなどのモデル: Graze and Merge)
    if (params->Vi <= v_crit){
        printf("GRAZE AND MERGE\n");
        params->collision_type = 1;
        merge(r,c,params);
        return swap;
    } else {
        // v_critを超えている場合
        // ターゲットが侵食される場合の処理
        params->Mlr = MAX(params->Mlr, min_frag_mass);
        if (params->Mlr<targ_m){
            // ターゲットがかなり削れるが、破片を作るほど質量があるか？
            if (targ_m+imp_m - params->Mlr <= min_frag_mass){
                // 破片に回す質量が足りないので「弾性的なすれ違い衝突(bounce)」とみなす
                printf("ELASTIC BOUNCE\n");
                params->collision_type=0;
                reb_collision_resolve_hardsphere(r,c);
                swap = 0;
            } else {
                // 「部分的な侵食」
                printf("GRAZING PARTIAL EROSION\n");
                params->collision_type = 3;
                add_fragments(r,c,params);
            }
        } else {
            // Mlrがターゲット質量を超えているなら、ヒットアンドラン系
            double Mlr_dag = (beta*target->m + projectile->m)/10 * pow(Q/(1.8*Q_star), -1.5);
            if (Q < 1.8*Q_star){
                Mlr_dag = (beta*targ_m + imp_m)*(1 - Q/ (2*Q_star));
            }

            double projectile_mass_accreted = params->Mlr - targ_m;
            double new_projectile_mass = projectile->m - projectile_mass_accreted;
            Mlr_dag = MAX(Mlr_dag, min_frag_mass);

            if (new_projectile_mass-Mlr_dag < min_frag_mass){
                // 破片として存続するには質量が足りず、弾性的すれ違い衝突に
                printf("ELASTIC BOUNCE\n");
                params->collision_type=0;
                reb_collision_resolve_hardsphere(r,c);
                swap = 0;
            } else {
                // 2番目に大きい破片 Mslr として定義
                params->Mslr = Mlr_dag;
                printf("HIT AND RUN\n");
                params->collision_type = 2;
                add_fragments(r,c,params);
            }
            return swap;
        }
    }
    return swap;
}

// 衝突イベントをファイル"collision_report.txt"に書き込む
void print_collision_array(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){
    // collision_typeや使われたハッシュ、各粒子の質量などを記録
    FILE* of = fopen("collision_report.txt","a+");
    fprintf(of, "%e\t", r->t);
    fprintf(of, "%d\t", params->collision_type);
    fprintf(of, "%u\t", (r->particles[params->target].hash));
    fprintf(of, "%e\t", (r->particles[params->target].m));
    fprintf(of, "%u\t", (r->particles[params->projectile].hash));
    for(int i=(r->N - params->no_frags);i<r->N;i++){
        fprintf(of, "%u\t", (r->particles[i].hash));
        fprintf(of, "%e\t", (r->particles[i].m));
    }
    fprintf(of, "\n");
    fclose(of);
}

// collision_params構造体を初期化する
void init_collision_params(struct collision_params* params){
    params->target=0;
    params->projectile=0;
    params->dx=0;
    params->dy=0;
    params->dz=0;
    params->b=0;
    params->Vix=0;
    params->Viy=0;
    params->Viz=0;
    params->Vi=0;
    params->l=0;
    params->rho1=0;
    params->cstar=0;
    params->mu=0;
    params->QR=0;
    params->QpRD=0;
    params->V_esc=0;
    params->separation_distance=0;
    params->Mlr=0;
    params->Mslr=0;
    params->Q=0;
    params->Mlr_dag=0;
    params->Q_star=0;
    params->vrel=0;
    params->xrel=0;
    params->collision_type=0;
    params->no_frags = 0;
}

// collision_params構造体を動的に確保し、初期化して返す
struct collision_params* create_collision_params(){
    // 注意: sizeofの引数が struct reb_simulation になっているが、本来はstruct collision_params の誤記と思われる
    //       ここではそのままにしている
    struct collision_params* params = calloc(1,sizeof(struct reb_simulation));
    init_collision_params(params);
    return params;
}

// メインの衝突解決関数
int reb_collision_resolve_fragment(struct reb_simulation* const r, struct reb_collision c){
    // もし同じタイムステップで同じ粒子が衝突していたら処理しない
    if (r->particles[c.p1].last_collision==r->t || r->particles[c.p2].last_collision==r->t) return 0;

    int i = c.p1;
    int j = c.p2;
    // i < j の場合のみ衝突を処理し、重複を防ぐ
    if (i<j) return 0;

    // swapフラグの初期値。2は「標準的にj(軽いほう)を除去する」という意味
    int swap = 2;
    if (r->particles[i].m < r->particles[j].m){
        swap =1;
        // i, jを入れ替える: iを重いほうに
        i = c.p2;
        j = c.p1;
    }

    // コード内で使いやすい配列ポインタを用意
    struct reb_particle* particles = r->particles;
    // 衝突パラメータを格納する構造体を作成
    struct collision_params* params = create_collision_params();

    // それぞれの半径を取得し、合計半径R_totを求める
    double imp_r = particles[j].r;
    double targ_r = particles[i].r;
    double R_tot = imp_r + targ_r;

    double imp_m = particles[j].m;
    double targ_m = particles[i].m;

    printf("TIME OF COLLISION: %e\n", r->t);
    printf("Target hash, mass = %u %e\n", particles[i].hash, targ_m);
    printf("Projectile hash, mass = %u %e\n", particles[j].hash, imp_m);

    double M_tot = imp_m + targ_m;
    double G = r->G;
    double Mlr,dx,dy,dz,Vix,Viy,Viz;
    double x2rel, xrel, v2rel, v2imp, Vi;
    double hx,hy,hz,h2,b;

    // 相対座標(dx, dy, dz)と相対速度(Vix, Viy, Viz)を計算
    make_vector(particles[i].x, particles[i].y, particles[i].z, particles[j].x, particles[j].y, particles[j].z, &dx,&dy,&dz);
    x2rel = get_dot(dx,dy,dz,dx,dy,dz);
    make_vector(particles[i].vx, particles[i].vy, particles[i].vz, particles[j].vx, particles[j].vy, particles[j].vz, &Vix,&Viy,&Viz);
    v2rel = get_dot(Vix,Viy,Viz,Vix,Viy,Viz);

    xrel = sqrt(x2rel);

    // 衝突時の角運動量ベクトル h = (xrel × vrel)
    hx = (dy*Viz - dz*Viy);
    hy = (dz*Vix - dx*Viz);
    hz = (dx*Viy - dy*Vix);

    h2 = get_dot(hx,hy,hz,hx,hy,hz);

    // 重力集束を考慮した衝突速度 v2imp
    v2imp = v2rel + 2*G*M_tot*(1./R_tot - 1./xrel);
    // 衝突タイミングが物理的接触を過ぎているなら補正
    if (1./R_tot - 1./xrel < 0){
        v2imp = v2rel;
    }

    Vi = sqrt(v2imp);
    // インパクトパラメータ b = h / vimp
    b = sqrt(h2/v2imp);
    if (b != b){
        // bがNaNの場合
        printf("NAN b \n");
        exit(0);
    }

    // Q = 衝突エネルギー/単位質量, V_esc = 二体の相互重力での逃亡速度
    double mu = (targ_m*imp_m)/M_tot;
    double l = R_tot-b;
    l = MIN(l, 2*imp_r); // 重なりが衝突体の直径を超えないように調整
    double alpha = (pow(l,2)*(3*imp_r-l))/(4*pow(imp_r, 3));
    alpha = MIN(1., alpha);
    double Q = .5*v2imp*targ_m*imp_m/pow(M_tot,2);
    double V_esc = pow(2.*G*M_tot/R_tot, .5);
    double alphamu = (alpha*targ_m*imp_m)/(alpha*imp_m + targ_m);
    double gamma = imp_m/targ_m;

    // cstarは1.8を想定
    const double cstar = 1.8;

    // Gの値でrho1を切り替えている(単位系の違いに合わせる)
    double rho1;
    if (G==6.674e-8){rho1 =1;}
    if (G==6.674e-11){rho1 =1000;}
    if (G==39.476926421373 || G==1){rho1 = 1.684e6;}

    // Chambers Eq.4 で示される総合体の代表半径
    double Rc1 = pow((M_tot*3)/(4.*M_PI*rho1), 1./3.);
    // Chambers Eq.3
    double Q0 = .8*cstar*M_PI*rho1*G*pow(Rc1,2);
    // Chambers Eq.5
    double Q_star = pow(mu/alphamu, 1.5)*(pow(1+gamma, 2)/ (4*gamma))*Q0;
    if (alpha == 0.0){
        // alpha=0の場合に非常に大きい値(実質無限大)にする
        Q_star = 6364136223846793005.0;
    }
    // b=0かつ同質量の場合はQ0に
    if (b == 0 && imp_m == targ_m){
        Q_star = Q0;
    }

    // qratio = Q/Q_star
    double qratio = Q/Q_star;

    // Mlr計算: Chambers Eq.8
    if (qratio < 1.8){
        Mlr = M_tot*(1.0-.5*qratio);
    } else {
        Mlr = .1*M_tot*pow(qratio/1.8, -1.5);
    }

    // 破片を配置するための分離距離
    double separation_distance = 4 * R_tot;

    // params構造体に値を代入
    params->target = i;
    params->projectile =j;
    params->dx = dx;
    params->dy = dy;
    params->dz = dz;
    params->b = b;
    params->Vix = Vix;
    params->Viy = Viy;
    params->Viz = Viz;
    params->Vi = Vi;
    params->l = l;
    params->rho1 = rho1;
    params->cstar = cstar;
    params->mu = mu;
    params->Q = Q;
    params->separation_distance = separation_distance;
    params->V_esc = V_esc;
    params->vrel = sqrt(v2rel);
    params->Mslr = 0;
    params->xrel = xrel;
    params->Mlr = Mlr; 

    // 各パラメータを出力してみる
    printf("Mp/Mt:    %0.4f\n", imp_m/targ_m);
    printf("Mlr/Mt:    %0.4f\n", Mlr/targ_m);
    printf("Mlr/Mtot:    %0.4f\n", Mlr/M_tot);
    printf("b/Rtarg:     %0.4f\n", b/targ_r);
    printf("Vimp/Vesc:     %0.4f\n",  Vi/V_esc);
    printf("Q/ Qstar:     %0.4f\n", Q/Q_star);
    printf("COLLISION TYPE: ");

    // 衝突速度が逃亡速度以下なら単純合体
    if (Vi <= V_esc){
        params->collision_type = 1;
        printf("SIMPLY MERGED\n");
        merge(r,c, params);
    } else {
        // Vi > V_esc
        if (b<targ_r){
            // 中心付近に当たっている（グレージングではない）衝突
            if (M_tot - params->Mlr < min_frag_mass){
                // 残差質量が小さすぎて破片が作れないなら事実上合体
                params->collision_type = 1;
                printf("EFFECTIVELY MERGED\n");
                merge(r,c,params);
            } else {
                // 十分に破片を作れる
                if (params->Mlr < targ_m){
                    // ターゲットが侵食される場合
                    if (params->Mlr <= 0.1*targ_m){
                        printf("SUPER-CATASTROPHIC\n");
                        params->collision_type = 4;
                        params->Mlr = MAX(Mlr, min_frag_mass);
                        add_fragments(r,c,params);
                    } else {
                        printf("PARTIAL EROSION\n");
                        params->collision_type = 3;
                        params->Mlr = MAX(Mlr, min_frag_mass);
                        add_fragments(r,c,params);
                    }
                } else {
                    // ターゲット質量を大きく維持→部分的合体
                    printf("PARTIAL ACCRETION\n");
                    params->collision_type = 2;
                    add_fragments(r,c,params);
                }
            }
        } else {
            // b > b_crit (ターゲット半径より大きい) ⇒ グレージング衝突
            swap = hit_and_run(r,c,params);
        }
    }

    // 衝突情報をファイルへ出力
    print_collision_array(r,c,params);

    return swap;
}