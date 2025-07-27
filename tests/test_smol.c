#include "smoluchowski.h"
#include <assert.h>
#include <math.h>

int main(void){
    SmolData d;
    smol_init(&d);

    assert(fabs(d.m[0] - pow(10.0, -3.0)) < 1e-12);
    assert(fabs(d.m[N_BIN-1] - pow(10.0, -3.0 + 0.1*(N_BIN-1))) < 1e-12);

    for(int i=0;i<N_BIN;i++){
        assert(d.n[i] == 0.0);
        assert(d.v[i] == 0.0);
        assert(d.sigma[i] == 0.0);
    }

    return 0;
}
