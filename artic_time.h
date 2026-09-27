/* SPDX-License-Identifier: MIT */
#ifndef NP2_ARTIC_TIME_H
#define NP2_ARTIC_TIME_H
#include <stdint.h>

/* Private, single-owner ARTIC source. No CPU or shadow-time dependency.
 * A future platform provider supplies monotonic ns plus validity here. */
typedef struct { uint64_t ns; int valid; } ARTIC_SAMPLE;
typedef struct {
    uint64_t anchor_ns;
    uint64_t rejected; /* Saturating diagnostic count, never guest authority. */
    uint32_t phase;    /* modulo 2^24 */
    uint32_t remainder; /* fractional tick: remainder / 78125 */
    int anchored;
} ARTIC_TIME;
void artic_time_reset(ARTIC_TIME *state);
int artic_time_observe(ARTIC_TIME *state, ARTIC_SAMPLE sample);
ARTIC_SAMPLE artic_time_source(void);
void artic_machine_reset(void);
uint32_t artic_machine_read(void);
extern ARTIC_TIME artic_machine_time; /* private debugger evidence */
#endif
