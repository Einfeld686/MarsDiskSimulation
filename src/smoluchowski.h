#ifndef SMOLUCHOWSKI_H
#define SMOLUCHOWSKI_H

#include <stdio.h>

#define N_BIN 36

typedef struct {
    double m[N_BIN];
    double n[N_BIN];
    double v[N_BIN];
    double sigma[N_BIN];
} SmolData;

void smol_init(SmolData* d);
void smol_step(SmolData* d, double dt, double t, const char* prefix);

#endif /* SMOLUCHOWSKI_H */
