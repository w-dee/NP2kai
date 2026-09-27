/* SPDX-License-Identifier: MIT */
#include "pit0_time.h"
/* Private stopped-debugger/host-test source, no guest or runtime protocol. */
PIT0_SAMPLE pit0_fake_sample = {0, 1};
PIT0_SAMPLE pit0_time_source(void) { return pit0_fake_sample; }
