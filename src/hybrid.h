#ifndef HYBRID_H
#define HYBRID_H

#include "smoluchowski.h"
#include "../rebound/src/rebound.h"

void hybrid_step(struct reb_simulation* r, SmolData* d);

#endif /* HYBRID_H */
