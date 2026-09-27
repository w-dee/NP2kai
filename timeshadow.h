/* SPDX-License-Identifier: MIT */
#ifndef NP2_TIMESHADOW_H
#define NP2_TIMESHADOW_H

/* Private diagnostic hooks. Disabled arguments are not evaluated. */
#if defined(NP2_TIME_SHADOW)
#include <stdint.h>
void time_shadow_service(void);
void time_shadow_commit(int32_t cycles);
void time_shadow_reset(void);
void time_shadow_rate_before(uint32_t rate);
void time_shadow_rate_after(uint32_t rate);
#else
#define time_shadow_service() ((void)0)
#define time_shadow_commit(cycles) ((void)0)
#define time_shadow_reset() ((void)0)
#define time_shadow_rate_before(rate) ((void)0)
#define time_shadow_rate_after(rate) ((void)0)
#endif
#endif
