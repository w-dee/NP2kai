/* SPDX-License-Identifier: MIT */
#ifndef NP2_TIMESHADOW_ACCOUNT_H
#define NP2_TIMESHADOW_ACCOUNT_H
#include <stdint.h>

/* Internal diagnostics, never serialized or consumed by guest code. */
typedef struct {
    uint64_t ns;
    int valid;
} SHADOW_HOST_SAMPLE;
typedef SHADOW_HOST_SAMPLE (*SHADOW_CLOCK)(void *context);

enum {
    SHADOW_BAD_LEDGER = 1,
    SHADOW_RATE_UNKNOWN = 2,
    SHADOW_OVERFLOW = 4
};
typedef struct {
    uint64_t samples, epoch_host_ns, last_host_ns, raw_host_ns;
    uint64_t host_target_ns, max_host_interval_ns;
    uint64_t legacy_cycles, legacy_ns;
    uint32_t legacy_fraction, remainder, rate;
    uint32_t epoch_stamp, last_stamp, raw_stamp;
    int64_t epoch_ledger, last_ledger, raw_ledger;
    int64_t divergence_ns, max_positive_ns, max_negative_ns;
    uint64_t max_absolute_ns, observed_wraps;
    uint64_t invalid_host_samples, discontinuities, rate_changes;
    uint32_t discontinuity_reasons;
    uint64_t first_bad_host_ns, first_bad_target_ns, first_bad_legacy_ns;
    int64_t first_bad_ledger;
    uint32_t first_bad_stamp, first_bad_rate, raw_rate;
    int anchored, legacy_valid, comparison_valid;
} TIME_SHADOW;

void shadow_reset(TIME_SHADOW *s);
/* ledger is an independent wide commit witness + in-slice elapsed cycles.
 * Without valid evidence, modulo timestamps cannot exclude hidden wraps. */
void shadow_observe(TIME_SHADOW *s, SHADOW_HOST_SAMPLE host, uint32_t stamp,
                    uint32_t rate, int64_t ledger, int ledger_valid);
/* Called after an observed rate boundary, excluding coordinate rescaling. */
void shadow_rate_anchor(TIME_SHADOW *s, uint32_t stamp, int64_t ledger,
                        uint32_t rate);
SHADOW_HOST_SAMPLE shadow_monotonic(void *context);
uint64_t shadow_monotonic_resolution_ns(void);
#endif
