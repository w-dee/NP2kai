/* SPDX-License-Identifier: MIT */
#include "artic_time.h"

/* Qualification-only source. Set by a stopped private debugger or host test.
 * No guest port, command line, config file, or production runtime switch. */
ARTIC_SAMPLE artic_fake_sample = {0, 1};
ARTIC_SAMPLE artic_time_source(void)
{
    return artic_fake_sample;
}
