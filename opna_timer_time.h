/* SPDX-License-Identifier: MIT */
#ifndef NP2_OPNA_TIMER_TIME_H
#define NP2_OPNA_TIMER_TIME_H
#include <stdint.h>
typedef struct { uint64_t ns; int valid; } OPNA_TIMER_SAMPLE;
typedef struct {
    uint32_t remaining, fraction;
    int active;
} OPNA_TIMER_CHANNEL;
typedef struct {
    OPNA_TIMER_CHANNEL timer[2];
    uint64_t anchor_ns, rejected, services, expired[2], max_gap_ns;
    uint32_t numerator;
    int anchored;
} OPNA_TIMER_TIME;
void opna_timer_time_reset(OPNA_TIMER_TIME *s, int clock8);
/* period[] contains positive legacy integer counts.
 * Fresh starts are relative delays. They start a new fractional phase;
 * repeated starts and register-value writes do not reload a running timer. */
void opna_timer_time_control(OPNA_TIMER_TIME *s, unsigned control, const uint32_t period[2]);
unsigned opna_timer_time_observe(OPNA_TIMER_TIME *s, OPNA_TIMER_SAMPLE now, const uint32_t period[2]);
int opna_timer_time_deadline(const OPNA_TIMER_TIME *s, unsigned timer, uint64_t *ns);
/* Pure exact-rational preview for bounded CSM-history admission. */
uint64_t opna_timer_time_expiries_until(const OPNA_TIMER_TIME *s, OPNA_TIMER_SAMPLE now, unsigned timer, uint32_t period);
int opna_timer_time_nth_deadline(const OPNA_TIMER_TIME *s, unsigned timer, uint32_t period, uint64_t nth, uint64_t *ns);
OPNA_TIMER_SAMPLE opna_timer_time_source(void);
#endif
