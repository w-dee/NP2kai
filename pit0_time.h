/* SPDX-License-Identifier: MIT */
#ifndef NP2_PIT0_TIME_H
#define NP2_PIT0_TIME_H
#include <stdint.h>

/* Private single-owner compatibility clock; one quantum is 1/5 PIT tick.
 * No physical OUT waveform or queued interrupt count is represented. */
typedef struct { uint64_t ns; int valid; } PIT0_SAMPLE;
typedef struct {
    uint64_t anchor_ns, rejected, services, max_gap_ns, collapsed;
    uint32_t fraction, numerator, remaining, mask_remaining;
    int anchored, mask_first;
} PIT0_TIME;
typedef struct { int irr_effect, armed; } PIT0_EFFECT;
void pit0_time_reset(PIT0_TIME *s, int clock8);
void pit0_time_schedule(PIT0_TIME *s, unsigned count);
void pit0_time_mask(PIT0_TIME *s, unsigned count);
PIT0_EFFECT pit0_time_observe(PIT0_TIME *s, PIT0_SAMPLE now,
                            unsigned count, int periodic, int armed, int masked);
int pit0_time_deadline(const PIT0_TIME *s, uint64_t *ns);
PIT0_SAMPLE pit0_time_source(void);
void pit0_machine_reset(void);
void pit0_machine_service(void);
void pit0_machine_service_at(PIT0_SAMPLE now);
void pit0_machine_schedule(unsigned count);
void pit0_machine_mask(void);
void pit0_machine_ack(void);
unsigned pit0_machine_count(void);
extern PIT0_TIME pit0_machine_time;
#endif
