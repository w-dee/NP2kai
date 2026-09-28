/* SPDX-License-Identifier: MIT */
#ifndef NP2_GDC_MACHINE_H
#define NP2_GDC_MACHINE_H
#if defined(NP2_GDC_MACHINE_TIME)
#include "gdc_time.h"
typedef struct {
    GDC_TIME time;
    uint64_t generation, presented, coalesced, presentations, finite_steps;
    uint32_t heartbeat_display, heartbeat_vertical;
    uint8_t committed_sync[8], committed_class;
    int ready, servicing, admission_error;
    /* Emulated work, independent of renderer GDCSCRN_EXT consumption. */
    unsigned clock_pending;
} GDC_MACHINE;
extern GDC_MACHINE gdc_machine;
void gdc_machine_reset(void);
void gdc_machine_service(void);
void gdc_machine_service_at(GDC_SAMPLE now);
void gdc_machine_pic_service(void);
unsigned gdc_machine_status(void);
unsigned gdc_machine_wait(unsigned kind, unsigned legacy);
void gdc_machine_clock_commit(void);
void gdc_machine_blink(uint64_t frames);
void gdc_machine_present(void);
int gdc_machine_present_allowed(void);
void gdc_machine_present_done(void);
#define GDC_CLOCK_DIRTY() (gdc_machine.clock_pending=1)
#define GDC_CLOCK_RESET() (gdc_machine.clock_pending=0)
#define GDC_SERVICE() gdc_machine_service()
#define GDC_WAIT(kind, legacy) gdc_machine_wait(kind, legacy)
#else
#define GDC_CLOCK_DIRTY() ((void)0)
#define GDC_CLOCK_RESET() ((void)0)
#define GDC_SERVICE() ((void)0)
#define GDC_WAIT(kind, legacy) (legacy)
#endif
#endif
