/* SPDX-License-Identifier: MIT */
#ifndef NP2_OPNA_TIMER_MACHINE_H
#define NP2_OPNA_TIMER_MACHINE_H
#if defined(NP2_OPNA_TIMER_MACHINE_TIME)
#include "opna_timer_time.h"
typedef struct {
    OPNA_TIMER_TIME time;
    int ready, servicing, admission_error;
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
