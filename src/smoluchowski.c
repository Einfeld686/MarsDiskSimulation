#include "smoluchowski.h"
#include <math.h>

void smol_init(SmolData* d){
    for(int i=0;i<N_BIN;i++){
        d->m[i] = pow(10.0, -3.0 + 0.1*i);
        d->n[i] = 0.0;
        d->v[i] = 0.0;
        d->sigma[i] = 0.0;
    }
}

static double v_rel(const SmolData* d,int i,int j) __attribute__((unused));
static double v_rel(const SmolData* d,int i,int j){
    return sqrt(d->v[i]*d->v[i] + d->v[j]*d->v[j]);
}

void smol_step(SmolData* d, double dt, double t, const char* prefix){
    (void)dt;
    char fname[64];
    snprintf(fname,sizeof(fname),"output/%s_%06d.dat",prefix,(int)t);
    FILE* fp=fopen(fname,"w");
    if(!fp) return;
    for(int i=0;i<N_BIN;i++){
        fprintf(fp,"%e %e\n",d->m[i],d->n[i]);
    }
    fclose(fp);
}
