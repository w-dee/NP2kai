/* SPDX-License-Identifier: MIT */
#ifndef NP2_OPNA_TIMER_MACHINE_H
#define NP2_OPNA_TIMER_MACHINE_H
#if defined(NP2_OPNA_TIMER_MACHINE_TIME)
#include "opna_timer_time.h"
#if defined(NP2_OPNA_CSM_HISTORY)
/* Experimental host/SDL qualification buffer, not a product debt limit. */
#define OPNA_CSM_HISTORY_TEST_CAPACITY 256u
#define OPNA_CSM_PAIR_KIND 1u
typedef struct {
    uint64_t epoch, sequence, deadline_ns, service_ns, timer_a_ordinal;
    unsigned kind, key_off_subindex, key_on_subindex;
} OPNA_CSM_HISTORY_RECORD;
#endif
typedef struct {
    OPNA_TIMER_TIME time;
    int ready, servicing, admission_error;
#if defined(NP2_OPNA_CSM_HISTORY)
    OPNA_CSM_HISTORY_RECORD history[OPNA_CSM_HISTORY_TEST_CAPACITY];
    uint64_t history_epoch, history_next_sequence, accepted_frontier_ns;
    uint64_t rejection_required, rejection_target_ns;
    unsigned history_count, history_finalized_count;
#endif
} OPNA_TIMER_MACHINE;
extern OPNA_TIMER_MACHINE opna_timer_machine;
void opna_timer_machine_discard(void);
void opna_timer_machine_reset(void);
void opna_timer_machine_service(void);
void opna_timer_machine_service_at(OPNA_TIMER_SAMPLE now);
void opna_timer_machine_control(unsigned data);
void opna_timer_machine_admit(unsigned soundid);
void opna_timer_machine_write(unsigned address, unsigned data);
#define OPNA_TIMER_SERVICE() opna_timer_machine_service()
#else
#define OPNA_TIMER_SERVICE() ((void)0)
#endif
#endif
