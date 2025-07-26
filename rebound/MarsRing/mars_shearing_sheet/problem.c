/**
 * Shearing sheet（せん断シート）シミュレーション
 *
 * このプログラムは、局所領域をシミュレーションするものです。
 * Hill近似を用いたせん断シート座標系で、粒子の運動・衝突・重力相互作用・せん断流を再現します。
 *
 * OpenGLを有効化すると計算領域が画面に表示され、
 * 'g'キーを押すとゴーストボックス（補助領域）を可視化できます。
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <math.h>
#include <stdint.h>    // for int64_t
#include <assert.h>    // for runtime sanity checks
#include "rebound.h"

/**
 * ここから先は、fragmentation.cの内容。
 */
double min_frag_mass = 1.0e-8; // 破片の最小質量（これ以上小さい破片は生成しない）（1e-1で数cmレベル）
int tot_no_frags = 0;  // シミュレーション開始時点での累積破片数

#define MIN(a, b) ((a) > (b) ? (b) : (a))    // aとbの小さい方を返す
#define MAX(a, b) ((a) > (b) ? (a) : (b))    // aとbの大きい方を返す

// --- 破片生成に必要なパラメータを格納する構造体 ---
struct collision_params
{
    int target;
    int projectile;
    double dx;
    double dy;
    double dz;
    double b;
    double Vix;
    double Viy;
    double Viz;
    double Vi;
    double l;
    double rho1;
    double cstar;
    double mu;
    double QR;
    double QpRD;
    double V_esc;
    double separation_distance;
    double Mlr;
    double Mslr;
    double Q;
    double Mlr_dag;
    double Q_star;
    double vrel;
    double xrel;
    int collision_type;
    int no_frags;
};

// --- ベクトルを生成する関数（ガリレイ変換） ---
void make_vector(double x1, double y1, double z1, double x2, double y2, double z2, double *x, double*y, double*z){
    *x = x1-x2;
    *y = y1-y2;
    *z = z1-z2;
}

// --- 2つのベクトルの内積を計算する関数 ---
double get_dot(double x1, double y1, double z1, double x2, double y2, double z2){
    return (x1*x2)+(y1*y2)+(z1*z2);
}

// -- 2つのベクトルの大きさを計算する関数 ---
double get_mag(double x, double y, double z){
    return sqrt(pow(x,2)+pow(y,2)+pow(z,2));
}

// --- 質量と密度から半径を計算する関数 ---
double get_radii(double m, double rho){
    return pow((3*m)/(4*M_PI*rho),1./3.);
}

// --- 破片生成処理を行う関数 ---
void add_fragments(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){
    // 粒子構造体の取得
    struct reb_particle* target = &(r->particles[params->target]);
    struct reb_particle* projectile = &(r->particles[params->projectile]);
    // 衝突系の重心位置・速度
    struct reb_particle com = reb_particle_com_of_pair(*target, *projectile);
    // 初期総質量・残存質量の計算
    double initial_mass = target -> m + projectile -> m;
    double remaining_mass = initial_mass - params->Mlr;
    // ターゲット密度と合計半径
    double rho = target->m/(4./3*M_PI*pow(target->r, 3));
    double rtot = target -> r + projectile -> r;

    // 二次最大破片質量 Mslr が 0 より大きければ，大破片を一つ生成する前提で残存質量を差し引き
    int big_frags = 0;
    if (params->Mslr > 0){
        remaining_mass = remaining_mass -  params->Mslr;
        big_frags = 1;
    }

    // 最小破片質量 min_frag_mass を用い、残存質量を等配分した破片数を計算
    /* --- sanity checks to avoid overflow / zero‑division --- */
    assert(min_frag_mass > 0.0);          /* min fragment mass must be positive            */
    assert(remaining_mass  > 0.0);        /* remaining mass must be positive               */

    int no_frags = (int)(remaining_mass / min_frag_mass);

    /* no_frags must stay within a reasonable range to prevent integer overflow
       and runaway memory allocation. 1e6 is an arbitrary safety cap; adjust as needed. */
    assert(no_frags > 0 && no_frags < 1000000);

    double frag_mass = remaining_mass / no_frags;

    // 総生成体数を計算
    int new_bodies = no_frags + big_frags;
    params->no_frags = new_bodies;

    char hash[20];
    double mxsum[3] = {0,0,0};
    double mvsum[3] = {0,0,0};
    //target gets mass of Mlr and is assigned COM position and velocity;
    target -> last_collision = r->t;
    target -> m = params->Mlr;
    target -> r = get_radii(params->Mlr, rho);
    target->x = com.x;
    target->y = com.y;
    target->z = com.z;

    target->vx = com.vx;
    target->vy = com.vy;
    target->vz = com.vz;

    if (no_frags == 1 && params->Mlr <= frag_mass){
        target -> m = frag_mass;
        target -> r = get_radii(frag_mass, rho);
        frag_mass = params -> Mlr;
    }

    mxsum[0] = mxsum[0] + target->m*target->x;
    mxsum[1] = mxsum[1] + target->m*target->y;
    mxsum[2] = mxsum[2] + target->m*target->z;

    mvsum[0] = mvsum[0] + target->m*target->vx;
    mvsum[1] = mvsum[1] + target->m*target->vy;
    mvsum[2] = mvsum[2] + target->m*target->vz;

    double theta_inc = (2.*M_PI)/new_bodies;

    double unit_vix, unit_viy, unit_viz, zx, zy, zz, z, ox, oy, oz, o;

    unit_vix = params->Vix/params->vrel;  //unit vector parallel to target velocity
    unit_viy = params->Viy/params->vrel;
    unit_viz = params->Viz/params->vrel;

    zx = (params->Viy*params->dz - params->Viz*params->dy);                     // vector normal to the collision plane; vrel cross xrel
    zy = (params->Viz*params->dx - params->Vix*params->dz);
    zz = (params->Vix*params->dy - params->Viy*params->dx);

    z = get_mag(zx, zy, zz);

    zx = zx/z;          //unit vector
    zy = zy/z;
    zz = zz/z;


    ox = (zy*params->Viz - zz*params->Viy);                   // vector normal to target velocity in collision plane; z cross vrel
    oy = (zz*params->Vix - zx*params->Viz);
    oz = (zx*params->Viy - zy*params->Vix);

    o = get_mag(ox, oy, oz);

    ox = ox/o;      //unit vector
    oy = oy/o;
    oz = oz/o;

    double fragment_velocity = sqrt(1.1*pow(params->V_esc,2) - 2*r->G*initial_mass*(1./rtot - 1./params->separation_distance));

    if (big_frags == 1){  //assign radii, positions and velocities to second largest remnant, theta=0
        struct reb_particle Slr1 = {0};
        Slr1.m = params->Mslr;
        Slr1.x = com.x + params->separation_distance*unit_vix;
        Slr1.y = com.y + params->separation_distance*unit_viy;
        Slr1.z = com.z + params->separation_distance*unit_viz;

        Slr1.vx = com.vx + fragment_velocity*unit_vix;
        Slr1.vy = com.vy + fragment_velocity*unit_viy;
        Slr1.vz = com.vz + fragment_velocity*unit_viz;

        Slr1.r = get_radii(Slr1.m, rho);
        snprintf(hash, sizeof(hash), "FRAG%d", tot_no_frags+1);
        Slr1.hash = reb_hash(hash);
        printf("%s hash, mass:      %llu %e\n", hash, (unsigned long long)Slr1.hash, Slr1.m);
        mxsum[0] += Slr1.m*Slr1.x;
        mxsum[1] += Slr1.m*Slr1.y;
        mxsum[2] += Slr1.m*Slr1.z;

        mvsum[0] += Slr1.m*Slr1.vx;
        mvsum[1] += Slr1.m*Slr1.vy;
        mvsum[2] += Slr1.m*Slr1.vz;
        Slr1.last_collision = r->t;
        /* wrap Slr1 into box */
        {
            double Lx = r->boxsize.x;
            double Ly = r->boxsize.y;
            Slr1.x -= Lx * floor((Slr1.x + 0.5*Lx)/Lx);
            Slr1.y -= Ly * floor((Slr1.y + 0.5*Ly)/Ly);
        }
        reb_simulation_add(r, Slr1);
    }

    int new_beginning_frag_index = tot_no_frags+big_frags+1;
    for (int i=(new_beginning_frag_index); i<(new_beginning_frag_index+no_frags); i++){          //add fragments
        struct reb_particle fragment = {0};
        int j = i - new_beginning_frag_index+1;
        fragment.m = frag_mass;
        fragment.x = com.x + params->separation_distance*(cos(theta_inc*j)*unit_vix + sin(theta_inc*j)*ox);
        fragment.y = com.y + params->separation_distance*(cos(theta_inc*j)*unit_viy + sin(theta_inc*j)*oy);
        fragment.z = com.z + params->separation_distance*(cos(theta_inc*j)*unit_viz + sin(theta_inc*j)*oz);
        fragment.vx = com.vx + fragment_velocity*(cos(theta_inc*j)*unit_vix + sin(theta_inc*j)*ox);
        fragment.vy = com.vy + fragment_velocity*(cos(theta_inc*j)*unit_viy + sin(theta_inc*j)*oy);
        fragment.vz = com.vz + fragment_velocity*(cos(theta_inc*j)*unit_viz + sin(theta_inc*j)*oz);

        fragment.r = get_radii(frag_mass, rho);
        fragment.last_collision = r->t;
        snprintf(hash, sizeof(hash), "FRAG%d", i);
        fragment.hash = reb_hash(hash);
        printf("%s hash, mass:      %llu %e\n", hash, (unsigned long long)fragment.hash, fragment.m);
        mxsum[0] +=fragment.m*fragment.x;
        mxsum[1] += fragment.m*fragment.y;
        mxsum[2] += fragment.m*fragment.z;

        mvsum[0] += fragment.m*fragment.vx;
        mvsum[1] += fragment.m*fragment.vy;
        mvsum[2] += fragment.m*fragment.vz;
        /* wrap fragment into box */
        {
            double Lx = r->boxsize.x;
            double Ly = r->boxsize.y;
            fragment.x -= Lx * floor((fragment.x + 0.5*Lx)/Lx);
            fragment.y -= Ly * floor((fragment.y + 0.5*Ly)/Ly);
        }
        reb_simulation_add(r, fragment);
    }
    tot_no_frags += big_frags+no_frags;

    //Ensure momentum is conserved
    double xoff[3] = {com.x - mxsum[0]/initial_mass, com.y - mxsum[1]/initial_mass, com.z - mxsum[2]/initial_mass};
    double voff[3] = {com.vx - mvsum[0]/initial_mass, com.vy - mvsum[1]/initial_mass, com.vz - mvsum[2]/initial_mass};

    target -> x  += xoff[0]*target->m/initial_mass;
    target -> y  += xoff[1]*target->m/initial_mass;
    target -> z  += xoff[2]*target->m/initial_mass;
    target -> vx += voff[0]*target->m/initial_mass;
    target -> vy += voff[1]*target->m/initial_mass;
    target -> vz += voff[2]*target->m/initial_mass;

    for (int i=(tot_no_frags-new_bodies)+1; i<(tot_no_frags+1); i++){
        char frag[20];
        snprintf(frag, sizeof(frag), "FRAG%d", i);
        struct reb_particle* p = reb_simulation_particle_by_hash(r, reb_hash(frag));
        if (!p) continue;                      /* skip missing hash safely */
        double mass_fraction = p->m / initial_mass;
        p->x  += xoff[0] * mass_fraction;
        p->y  += xoff[1] * mass_fraction;
        p->z  += xoff[2] * mass_fraction;
        p->vx += voff[0] * mass_fraction;
        p->vy += voff[1] * mass_fraction;
        p->vz += voff[2] * mass_fraction;
    }
    return;
}

// --- 合体処理を行う関数（衝突による粒子の合体） ---
void merge(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){
    struct reb_particle* pi = &(r->particles[params->target]);
    struct reb_particle* pj = &(r->particles[params->projectile]);

    double invmass = 1.0/(pi->m + pj->m);
    double targ_rho = pi->m/(4./3*M_PI*pow(pi->r,3));  //new body recieves density of the target
    // Merge by conserving mass, volume and momentum
    pi->vx = (pi->vx*pi->m + pj->vx*pj->m)*invmass;
    pi->vy = (pi->vy*pi->m + pj->vy*pj->m)*invmass;
    pi->vz = (pi->vz*pi->m + pj->vz*pj->m)*invmass;
    pi->x  = (pi->x*pi->m + pj->x*pj->m)*invmass;
    pi->y  = (pi->y*pi->m + pj->y*pj->m)*invmass;
    pi->z  = (pi->z*pi->m + pj->z*pj->m)*invmass;
    pi->m  = pi->m + pj->m;
    pi->r  = pow((3*pi->m)/(4*M_PI*targ_rho),1./3.);
    pi->last_collision = r->t;


    return; //
}

// --- Hit-and-Run 衝突処理（部分的な付着・侵食を含む） ---
int hit_and_run(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){  //also includes partial accretion.  Mlr = M_target.  Projectile is erroded.
        struct reb_particle* target = &(r->particles[params->target]);
        struct reb_particle* projectile = &(r->particles[params->projectile]);


        int swap = 2;
        int i = c.p1;
        int j = c.p2;   //make sure projectile is the particle being removed
        struct reb_particle* pi = &(r->particles[i]);
        struct reb_particle* pj = &(r->particles[j]);
        if (pi->m < pj->m){
            swap = 1;
        }

        double phi = 2*acos((params->l-projectile->r)/projectile->r);
        double A_interact = pow(projectile->r, 2)*((M_PI-(phi-sin(phi))/2.));  //Leinhardt Eq. 46;
        double L_interact = 2.*pow(pow(target->r,2)-(pow(target->r-params->l/2.,2)), .5);   //Leinhardt Eq. 47
        double beta = (A_interact*L_interact)/target->m;  //Chambers Eq. 11
        double Rc1 = pow(3./(4.*M_PI*params->rho1)*(beta*target->m + projectile->m), 1./3.); 
        double Q0 = .8*params->cstar*M_PI*params->rho1*r->G*pow(Rc1, 2);
        double gamma = (beta*target->m)/projectile->m;
        double Q_star = (pow(1+gamma, 2)/4*gamma)* Q0;

        double mu = (beta*target->m*projectile->m)/(beta*target->m+projectile->m);  //Chambers Eq. 13
        double Q = .5*(mu*pow(params->Vi,2))/(beta*target->m+projectile->m); //Chambers Eq. 12

        double c1 = 2.43;
        double c2 = -0.0408;
        double c3 = 1.86;
        double c4 = 1.08;

        double targ_m = target->m;
        double imp_m = projectile->m;
        double zeta = pow((targ_m - imp_m)/(targ_m + imp_m),2);
        double fac = pow(1-params->b/(target->r + projectile->r),2.5);
        double v_crit = params->V_esc*(c1*zeta*fac + c2*zeta +c3*fac + c4);

        if (params->Vi <= v_crit){             //if impact velocity is low, the hit-and-run results in a merger.
            printf("GRAZE AND MERGE\n");
            params->collision_type = 1;
            merge(r,c,params);
            return swap;
        }
        else{ //vi>v_crit
            params->Mlr = MAX(params->Mlr, min_frag_mass); //Cannot be smaller than min fragment mass
            if (params->Mlr<targ_m){ //Target is being eroded, projectile should also fragment
                if (targ_m+imp_m - params->Mlr <= min_frag_mass){ //not enough mass to produce new fragments
                    printf("ELASTIC BOUNCE\n");
                    params->collision_type=0;
                    reb_collision_resolve_hardsphere(r,c);
                    swap = 0;
                }
                else{
                    printf("GRAZING PARTIAL EROSION\n");
                    params->collision_type = 3;
                    add_fragments(r,c,params);
                }
            }
            else{ //Mlr > Mt, either a hit and run or an elastic bounce
                double Mlr_dag = (beta*target->m + projectile->m)/10 * pow(Q/(1.8*Q_star), -1.5);
                if (Q < 1.8*Q_star){
                    Mlr_dag = (beta*targ_m + imp_m)*(1 - Q/ (2*Q_star));
                }
            double projectile_mass_accreted = params->Mlr - targ_m;
            double new_projectile_mass = projectile->m - projectile_mass_accreted;
            Mlr_dag = MAX(Mlr_dag, min_frag_mass);
            if (new_projectile_mass-Mlr_dag < min_frag_mass){
                    printf("ELASTIC BOUNCE\n");
                    params->collision_type=0;
                    reb_collision_resolve_hardsphere(r,c);
                    swap = 0;
                }
                else{
                    params->Mslr = Mlr_dag;
                    printf("HIT AND RUN\n");
                    params->collision_type = 2;
                    add_fragments(r,c,params);
                }
            }
    return swap;
    }
}

// --- 衝突ログをファイルに出力する関数 ---
void print_collision_array(struct reb_simulation* const r, struct reb_collision c, struct collision_params *params){
//0=elastic bounce, 1=merger, 2=partial accretion, 3=partial erosion, 4=supercat
    FILE* of = fopen("collision_report.txt","a+");
    fprintf(of, "%e\t", r->t);
    fprintf(of, "%d\t", params->collision_type);
    fprintf(of, "%llu\t", (unsigned long long)(r->particles[params->target].hash));
    fprintf(of, "%e\t", (r->particles[params->target].m));
    fprintf(of, "%llu\t", (unsigned long long)(r->particles[params->projectile].hash));
    for(int i=(r->N - params->no_frags);i<r->N;i++){        //assuming Fragments are added to end of particle array
        fprintf(of, "%llu\t", (unsigned long long)(r->particles[i].hash));
        fprintf(of, "%e\t", (r->particles[i].m));
    }
    fprintf(of, "\n");
    fclose(of);                        // close file
}

// --- 衝突パラメータ構造体の初期化関数 ---
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

// --- 衝突パラメータ構造体を動的に生成・初期化する関数 ---
struct collision_params* create_collision_params(){
    struct collision_params* params = calloc(1, sizeof(struct collision_params));
    init_collision_params(params);
    return params;
}


// --- 衝突検出後に破片生成・合体処理を呼び出すコールバック関数 ---
int reb_collision_resolve_fragment(struct reb_simulation* const r, struct reb_collision c){
    if (r->particles[c.p1].last_collision==r->t || r->particles[c.p2].last_collision==r->t) return 0;
    int i = c.p1;
    int j = c.p2;
    if (i<j) return 0;      //衝突コールバックを1つ返す

    int swap = 2;
    if (r->particles[i].m < r->particles[j].m){        //unless swap is redfined as 0, projectile is going to be removed.
        swap =1;
        i = c.p2;
        j = c.p1;
    }

    struct reb_particle* particles = r->particles;
    struct collision_params* params = create_collision_params();

    double imp_r = particles[j].r;
    double targ_r = particles[i].r;
    double R_tot = imp_r + targ_r;

    double imp_m = particles[j].m;
    double targ_m = particles[i].m;

    printf("TIME OF COLLISION: %e\n", r->t);
    printf("Target hash, mass = %llu %e\n", (unsigned long long)particles[i].hash, targ_m);
    printf("Projectile hash, mass = %llu %e\n", (unsigned long long)particles[j].hash, imp_m);

    // 相対位置・速度の計算
    double M_tot = imp_m + targ_m;
    double G = r->G;
    double Mlr,dx,dy,dz,Vix,Viy,Viz;
    double x2rel, xrel, v2rel, v2imp, Vi;
    double hx,hy,hz,h2,b;
    make_vector(particles[i].x, particles[i].y, particles[i].z, particles[j].x, particles[j].y, particles[j].z, &dx,&dy,&dz);  // dx, dy, dzの相対座標を計算
    x2rel = get_dot(dx,dy,dz,dx,dy,dz);
    make_vector(particles[i].vx, particles[i].vy, particles[i].vz, particles[j].vx, particles[j].vy, particles[j].vz, &Vix,&Viy,&Viz);  // 相対速度を計算
    v2rel = get_dot(Vix,Viy,Viz,Vix,Viy,Viz); // 相対速度の二乗

    xrel = sqrt(x2rel);  // 被衝突物体と衝突物体との中心間の距離

    // 角運動量ベクトル
    hx = (dy*Viz - dz*Viy);
    hy = (dz*Vix - dx*Viz);
    hz = (dx*Viy - dy*Vix);

    h2 = get_dot(hx,hy,hz,hx,hy,hz);

    v2imp = v2rel + 2*G*M_tot*(1./R_tot - 1./xrel); //impact velocity with gravitational focusing at time of detected collision

    if (1./R_tot - 1./xrel < 0){v2imp = v2rel;}  //if collision is detected after physical contact

    Vi = sqrt(v2imp);  //magnitude of impact velocity vector
    b = sqrt(h2/v2imp);  //impact parameter, b=R_tot*sin(theta)
    if (b != b){
        printf("NAN b \n");
        exit(0);}
    //Stewart & Leinhardt 2012 parameters
    double mu = (targ_m*imp_m)/M_tot;  //Chambers Eq. 2, reduced mass
    double l = R_tot-b;  //Leinhardt Eq. 7, the projected length of the projectile overlapping the target
    l = MIN(l, 2*imp_r);
    double alpha = (pow(l,2)*(3*imp_r-l))/(4*pow(imp_r, 3)); //Leinhardt Eq. 11, interacting mass fraction
    alpha = MIN(1., alpha);
    double Q = .5*v2imp*targ_m*imp_m/pow(M_tot,2);  //specific energy per unit mass
    double V_esc = pow(2.*G*M_tot/R_tot, .5); //mutal escape velocity as defined in Wallace et al 2018 and Chambers 2013
    double alphamu = (alpha*targ_m*imp_m)/(alpha*imp_m + targ_m);  //Leinhardt Eq. 12, reduced interacting mass for fraction alpha.
    double gamma = imp_m/targ_m;  //Chambers Eq. 6

    const double cstar = 1.8;      //may be a user defined variable, default taken from paper

    double rho1;         //constant density

    if (G==6.674e-8){rho1 =1;} //CGS
    if (G==6.674e-11){rho1 =1000;} //SI
    if (G==39.476926421373 || G==1){rho1 = 1.684e6;}  //Msun/AU^3
    double Rc1 = pow((M_tot*3)/(4.*M_PI*rho1), 1./3.);  //Chambers Eq. 4, combined radius of target and projectile with constant density
    double Q0 = .8*cstar*M_PI*rho1*G*pow(Rc1,2);  //Chambers Eq. 3, critical value of impact energy for head-on collisions
    double Q_star = pow(mu/alphamu, 1.5)*(pow(1+gamma, 2)/ (4*gamma))*Q0;  //Chambers Eq. 5, critical value for oblique or different mass collisons.
    if (alpha == 0.0){Q_star = 6364136223846793005.0;}
    if (b == 0 && imp_m == targ_m){
        Q_star = Q0;
    }
    double qratio = Q/Q_star;
    if (qratio < 1.8){
        Mlr = M_tot*(1.0-.5*qratio);
    }
    else{
        Mlr = .1*M_tot*pow(qratio/1.8, -1.5);  //Chambers Eq.8
    }

    double separation_distance = 4 * R_tot;  //非常に議論の余地がある

///POPULATE STRUCT OBJECTS
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
    params->Mlr = Mlr; //Mlr cannot be smaller the minimum fragment mass

    printf("Mp/Mt:    %0.4f\n", imp_m/targ_m);
    printf("Mlr/Mt:    %0.4f\n", Mlr/targ_m);
    printf("Mlr/Mtot:    %0.4f\n", Mlr/M_tot);
    printf("b/Rtarg:     %0.4f\n", b/targ_r);
    printf("Vimp/Vesc:     %0.4f\n",  Vi/V_esc);
    printf("Q/Qstar:     %0.4f\n", Q/Q_star);
    printf("COLLISION TYPE: ");

    if (Vi <= V_esc){
        params->collision_type = 1;
        // printf("SIMPLY MERGED\n");
        merge(r,c, params);
                    }
    else{  //Vi > V_esc
        if (b<targ_r){ //non-grazing regime
            if (M_tot - params->Mlr < min_frag_mass){
                params->collision_type = 1;
                printf("EFFECTIVELY MERGED\n");
                merge(r,c,params);
            }
            else{ // M_tot - params->Mlr >= min_frag_mass; fragments will be produced unless it is a graze and merge or elastic bounce 
                if (params->Mlr < targ_m){
                    if (params->Mlr <= 0.1*targ_m){
                        printf("SUPER-CATASTROPHIC\n");
                        params->collision_type = 4;
                        params->Mlr = MAX(Mlr, min_frag_mass);
                        add_fragments(r,c,params);
                    }
                    else{
                        printf("PARTIAL EROSION\n");
                        params->collision_type = 3;
                        params->Mlr = MAX(Mlr, min_frag_mass);
                        add_fragments(r,c,params);
                        }
                }
                else{  //(params->Mlr >= targ_m)
                            printf("PARTIAL ACCRETION\n");
                            params->collision_type = 2;
                            add_fragments(r,c,params);
                    }
            }
        }
        else{ // b > b_crit, grazing regime
            swap = hit_and_run(r,c,params); //swap gets redefined here as it may be set to 0 in the case of a bounce
        }
    }


print_collision_array(r,c,params);
return swap;
}

// --- Bridgesらの実験に基づく速度依存反発係数計算関数 ---
double coefficient_of_restitution_bridges(const struct reb_simulation* const r, double v); // 衝突時の速度依存反発係数を計算する関数
// --- 一定時間ごとにシミュレーション状態を出力する関数 ---
void heartbeat(struct reb_simulation* const r); // シミュレーション中に定期的に呼ばれる関数

int main(int argc, char* argv[]) {
    struct reb_simulation* r = reb_simulation_create();
    // ウェブブラウザからシミュレーションに接続できるようにサーバーを起動
    // ブラウザで http://localhost:8000 にアクセスするとシミュレーションの状態を確認可能
    reb_simulation_start_server(r, 8000);

    // 各種パラメータ設定
    const double G       = 6.67430e-11;       // 万有引力定数 [m^3 kg^-1 s^-2]
    const double M_mars  = 6.4171e23;         // 火星質量 [kg]
    const double R_mars  = 3.3895e6;          // 火星半径 [m]
    r->opening_angle2    = .5;                  // 重力計算の精度を決めるパラメータ（木構造法のためのopening angleの2乗）
    r->integrator        = REB_INTEGRATOR_SEI;  // 積分器
    r->boundary          = REB_BOUNDARY_SHEAR;  // 境界条件
    r->gravity           = REB_GRAVITY_TREE;    // 重力計算
    r->collision         = REB_COLLISION_DIRECT;  // 衝突検出
    r->collision_resolve = reb_collision_resolve_fragment;
    double radius_factor = 2.0;               // 火星半径の倍率
    double R_loc         = radius_factor * R_mars;
    double OMEGA         = sqrt(G * M_mars / (R_loc * R_loc * R_loc));       // 1/s（GPTによる仮説）
    r->ri_sei.OMEGA      = OMEGA;
    r->G                 = 6.674e-11;         // N / (1e-5 kg)^2 m^2
    r->softening         = 1.0;                 // m （GPTとの議論）
    r->dt                = 1e-3*2.*M_PI/OMEGA;  // s
    r->heartbeat         = heartbeat;           // function pointer for heartbeat
    // This example uses two root boxes in the x and y direction.
    // Although not necessary in this case, it allows for the parallelization using MPI.
    // See Rein & Liu for a description of what a root box is in this context.
    double surface_density          = 1.0e4;     // 表面密度 (kg/m^2)
    double particle_density        = 2500;     // 粒子の密度 (kg/m^3)
    double particle_radius_min     = 1.4;       // 粒子半径の最小値 (m)
    double particle_radius_max     = 1.6;       // 粒子半径の最大値 (m)
    double particle_radius_slope   = -3;
    double boxsize             = 50;         // シミュレーション領域のサイズ (m)
    if (argc>1){                              // コマンドライン引数が与えられた場合は、boxsizeを上書きする
        boxsize = atof(argv[1]);
    }
    reb_simulation_configure_box(r, boxsize, 2, 2, 1);
    r->N_ghost_x = 2;
    r->N_ghost_y = 2;
    r->N_ghost_z = 2;

    // 初期条件
    printf("Toomre wavelength: %f\n",4.*M_PI*M_PI*surface_density/OMEGA/OMEGA*r->G);
    // 衝突時の反発係数は Bridges et al. に基づく速度依存の関数を使用
    r->coefficient_of_restitution = coefficient_of_restitution_bridges;
    // 衝突後、粒子の相対速度がゼロになると次のタイムステップで粒子が重なってしまうため、
    // 粒子に小さな反発速度を与えて重なりを防止するための最小衝突速度を設定
    r->minimum_collision_velocity = 0.; // 過剰な反発を避けるため、最小衝突速度を除去。元々はparticle_radius_min*OMEGA*0.001;  （せん断流による粒子間の速度のごく一部）


    // 初速度の範囲 (m/s): 1 km/s から 5 km/s
    double min_initial_velocity = 1000.0;
    double max_initial_velocity = 5000.0;
    double v_coll = (min_initial_velocity + max_initial_velocity)/2.;

    // 粒子の生成と追加
    double total_mass = surface_density*r->boxsize.x*r->boxsize.y;    // 全体の質量 = 表面密度 × (ボックスの x × y 面積)
    double mass = 0;

    // Open output file for initial particle positions
    FILE *particle_fp = fopen("initial_particles.txt", "w");
    if(particle_fp == NULL){
        perror("fopen");
        exit(EXIT_FAILURE);
    }
    // Generate initial particles with unique hash IDs
    for(int idx = 0; mass < total_mass; idx++){
        struct reb_particle pt;
        // x, y, z coordinates
        pt.x = reb_random_uniform(r, -r->boxsize.x/2., r->boxsize.x/2.);
        pt.y = reb_random_uniform(r, -r->boxsize.y/2., r->boxsize.y/2.);
        pt.z = reb_random_normal(r, 1.);
        // initial velocities
        pt.vx = reb_random_normal(r, v_coll/sqrt(2));
        pt.vy = -1.5*pt.x*OMEGA + reb_random_normal(r, v_coll/sqrt(2));
        pt.vz = 0;
        pt.ax = 0;
        pt.ay = 0;
        pt.az = 0;
        // radius and mass
        double radius = reb_random_powerlaw(r, particle_radius_min, particle_radius_max, particle_radius_slope);
        pt.r = radius;
        double particle_mass = particle_density*4./3.*M_PI*radius*radius*radius;
        pt.m = particle_mass;
        // assign a unique hash based on index
        char name[32];
        snprintf(name, sizeof(name), "INIT%05d", idx);
        pt.hash = reb_hash(name);
        reb_simulation_add(r, pt);
        // write to file and update mass
        fprintf(particle_fp, "%f %f %f\n", pt.x, pt.y, pt.r);
        mass += particle_mass;
    }
    // Close the file after writing all initial particles
    fclose(particle_fp);
    // シミュレーション時間
    double Torb = 2.9 * M_PI / OMEGA;
    double Tsim = 1.0 * Torb;
    reb_simulation_integrate(r, Tsim);
    reb_simulation_free(r);
}

// ------------------------------------------------
// 衝突時の反発係数を計算する関数
// Bridges らの結果に基づいており、衝突速度 v (m/s) に依存して変化する
// 速度が大きいほど反発係数 eps は小さくなり、非弾性的な衝突を表現
// eps の値は 0～1 の範囲にクランプされる
// ------------------------------------------------
double coefficient_of_restitution_bridges(const struct reb_simulation* const r, double v){
    // v の単位は [m/s] とする
    double eps = 0.32*pow(fabs(v)*100.,-0.234);
    if (eps>1) eps=1;
    if (eps<0) eps=0;
    return eps;
}

// ------------------------------------------------
// heartbeat 関数
// シミュレーションの進行状況を一定間隔でチェックし、
// 出力やタイミング情報を更新するために呼び出される
// ------------------------------------------------
void heartbeat(struct reb_simulation* const r){
    if (reb_simulation_output_check(r, 1e-1*2.*M_PI/r->ri_sei.OMEGA)){
        reb_simulation_output_timing(r, 0);
        //reb_output_append_velocity_dispersion("veldisp.txt");
    }
    if (reb_simulation_output_check(r, 2.*M_PI/r->ri_sei.OMEGA)){
        reb_simulation_output_ascii(r, "position.txt");
    }
}