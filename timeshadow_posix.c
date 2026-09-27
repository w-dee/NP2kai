/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "timeshadow_account.h"
#include <time.h>

SHADOW_HOST_SAMPLE shadow_monotonic(void *context)
{
    struct timespec ts;
    SHADOW_HOST_SAMPLE sample = {0, 0};
    (void)context;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) == 0 && ts.tv_sec >= 0 &&
        ts.tv_nsec >= 0 && ts.tv_nsec < 1000000000L &&
        (uint64_t)ts.tv_sec <= (UINT64_MAX - (uint64_t)ts.tv_nsec) / 1000000000u) {
        sample.ns = (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
        sample.valid = 1;
    }
    return sample;
}

uint64_t shadow_monotonic_resolution_ns(void)
{
    struct timespec ts;
    if (clock_getres(CLOCK_MONOTONIC, &ts) != 0) return 0;
    return (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
}
