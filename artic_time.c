/* SPDX-License-Identifier: MIT */
#include "artic_time.h"
#include <string.h>

#if defined(SUPPORT_MULTITHREAD) || defined(SUPPORT_ASYNC_CPU) || defined(SUPPORT_IA32_HAXM)
#error ARTIC pilot requires one emulation owner
#endif

ARTIC_TIME artic_machine_time;

void artic_time_reset(ARTIC_TIME *state)
{
    memset(state, 0, sizeof(*state));
}

int artic_time_observe(ARTIC_TIME *state, ARTIC_SAMPLE sample)
{
    uint64_t delta, ticks, z;
    if (!sample.valid || (state->anchored && sample.ns < state->anchor_ns)) {
        if (state->rejected != UINT64_MAX) state->rejected++;
        return 0;
    }
    if (!state->anchored) {
        state->anchor_ns = sample.ns;
        state->anchored = 1;
        return 1;
    }
    delta = sample.ns - state->anchor_ns;
    /* Split before multiply: even UINT64_MAX ns fits every intermediate. */
    z = (delta % 78125u) * 24u + state->remainder;
    ticks = (delta / 78125u) * 24u + z / 78125u;
    state->remainder = (uint32_t)(z % 78125u);
    state->phase = (uint32_t)((state->phase + ticks) & 0x00ffffffu);
    state->anchor_ns = sample.ns;
    return 1;
}

void artic_machine_reset(void)
{
    /* Zero phase is legacy compatibility, not a physical reset assertion. */
    artic_time_reset(&artic_machine_time);
    (void)artic_time_observe(&artic_machine_time, artic_time_source());
}

uint32_t artic_machine_read(void)
{
    (void)artic_time_observe(&artic_machine_time, artic_time_source());
    return artic_machine_time.phase;
}
