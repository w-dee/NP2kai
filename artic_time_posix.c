/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "artic_time.h"
#include <time.h>

/* Fresh Linux diagnostic sample. No product pause/stall policy is implied. */
ARTIC_SAMPLE artic_time_source(void)
{
    struct timespec ts;
    ARTIC_SAMPLE sample = {0, 0};
    if (clock_gettime(CLOCK_MONOTONIC, &ts) == 0 && ts.tv_sec >= 0 &&
        ts.tv_nsec >= 0 && ts.tv_nsec < 1000000000L &&
        (uint64_t)ts.tv_sec <= (UINT64_MAX - (uint64_t)ts.tv_nsec) / 1000000000u) {
        sample.ns = (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
        sample.valid = 1;
    }
    return sample;
}
