/* SPDX-License-Identifier: MIT */
#ifndef NP2_MOUSE_MACHINE_H
#define NP2_MOUSE_MACHINE_H
#if defined(NP2_MOUSE_MACHINE_TIME)
#include "mouse_time.h"
extern MOUSE_TIME mouse_machine;
/* Private fake source: monotonic rational machine coordinate, never CPU work. */
extern uint64_t mouse_fake_now;
extern int mouse_machine_ready;
void mouse_machine_reset(void);
void mouse_machine_service(void);
void mouse_machine_control(unsigned portc);
void mouse_machine_import_live(void);
void mouse_machine_reject(void);
#define MOUSE_MACHINE_SERVICE() mouse_machine_service()
#else
#define MOUSE_MACHINE_SERVICE() ((void)0)
#endif
#endif
