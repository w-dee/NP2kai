/* SPDX-License-Identifier: MIT */
#include "opna_timer_time.h"
/* Private stopped-debugger source, following the ARTIC/PIT/GDC fixture ABI. */
OPNA_TIMER_SAMPLE opna_timer_fake_sample = {0, 1};
OPNA_TIMER_SAMPLE opna_timer_time_source(void) { return opna_timer_fake_sample; }
