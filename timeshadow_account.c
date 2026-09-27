/* SPDX-License-Identifier: MIT */
#include "timeshadow_account.h"
#include <limits.h>
#include <string.h>

static void discontinuity(TIME_SHADOW *s, uint32_t reason)
{
    if (!s->discontinuities) {
        s->first_bad_host_ns = s->raw_host_ns;
        s->first_bad_stamp = s->raw_stamp;
        s->first_bad_ledger = s->raw_ledger;
        s->first_bad_rate = s->raw_rate;
        s->first_bad_target_ns = s->host_target_ns;
        s->first_bad_legacy_ns = s->legacy_ns;
    }
    s->discontinuities++;
    s->discontinuity_reasons |= reason;
    s->legacy_valid = 0;
    s->comparison_valid = 0;
}

void shadow_reset(TIME_SHADOW *s)
{
    memset(s, 0, sizeof(*s));
    s->legacy_valid = 1;
}

static void accumulate(TIME_SHADOW *s, uint64_t cycles)
{
    /* Q32 nanoseconds; retain division remainder at a fixed rate. The
     * largest uint64 cycle input times 1e9 times 2^32 fits uint128. */
    __uint128_t numerator = ((__uint128_t)cycles * 1000000000u << 32)
                            + s->remainder;
    __uint128_t duration = ((__uint128_t)s->legacy_ns << 32)
                           + s->legacy_fraction + numerator / s->rate;
    if (cycles > UINT64_MAX - s->legacy_cycles ||
        (duration >> 32) > UINT64_MAX) {
        discontinuity(s, SHADOW_OVERFLOW);
        return;
    }
    s->legacy_cycles += cycles;
    s->legacy_ns = (uint64_t)(duration >> 32);
    s->legacy_fraction = (uint32_t)duration;
    s->remainder = (uint32_t)(numerator % s->rate);
}

static void compare(TIME_SHADOW *s)
{
    __int128 difference = (__int128)s->host_target_ns - s->legacy_ns;
    uint64_t magnitude;
    if (difference > INT64_MAX || difference < -(__int128)INT64_MAX) {
        discontinuity(s, SHADOW_OVERFLOW);
        return;
    }
    s->divergence_ns = (int64_t)difference;
    if (s->divergence_ns > s->max_positive_ns)
        s->max_positive_ns = s->divergence_ns;
    if (s->divergence_ns < s->max_negative_ns)
        s->max_negative_ns = s->divergence_ns;
    magnitude = (uint64_t)(difference < 0 ? -difference : difference);
    if (magnitude > s->max_absolute_ns) s->max_absolute_ns = magnitude;
    s->comparison_valid = 1;
}

void shadow_observe(TIME_SHADOW *s, SHADOW_HOST_SAMPLE host, uint32_t stamp,
                    uint32_t rate, int64_t ledger, int ledger_valid)
{
    int host_ok = host.valid && (!s->anchored || host.ns >= s->last_host_ns);
    s->samples++;
    s->raw_host_ns = host.ns;
    s->raw_stamp = stamp;
    s->raw_ledger = ledger;
    s->raw_rate = rate;
    s->comparison_valid = 0;
    if (!host_ok) s->invalid_host_samples++;
    if (!s->anchored) {
        if (!host_ok) return;
        s->anchored = 1;
        s->epoch_host_ns = s->last_host_ns = host.ns;
        s->epoch_stamp = s->last_stamp = stamp;
        s->epoch_ledger = s->last_ledger = ledger;
        s->rate = rate;
        if (!ledger_valid) discontinuity(s, SHADOW_BAD_LEDGER);
        if (!rate) discontinuity(s, SHADOW_RATE_UNKNOWN);
    } else {
        __int128 delta = (__int128)ledger - s->last_ledger;
        if (host_ok) {
            uint64_t interval = host.ns - s->last_host_ns;
            if (interval > s->max_host_interval_ns)
                s->max_host_interval_ns = interval;
            s->last_host_ns = host.ns;
            s->host_target_ns = host.ns - s->epoch_host_ns;
        }
        if (rate != s->rate || !rate) discontinuity(s, SHADOW_RATE_UNKNOWN);
        if (!ledger_valid || delta < 0 || delta > UINT64_MAX ||
            (uint32_t)delta != (uint32_t)(stamp - s->last_stamp)) {
            discontinuity(s, SHADOW_BAD_LEDGER);
        } else if (s->legacy_valid) {
            /* Independent witness resolves even multiple wraps. Host time
             * and configured rate are NOT an upper bound on CPU progress. */
            s->observed_wraps += (uint64_t)(((__uint128_t)s->last_stamp
                                           + (uint64_t)delta) >> 32);
            accumulate(s, (uint64_t)delta);
        }
        s->last_stamp = stamp;
        s->last_ledger = ledger;
    }
    if (host_ok && s->legacy_valid) compare(s);
}

void shadow_rate_anchor(TIME_SHADOW *s, uint32_t stamp, int64_t ledger,
                        uint32_t rate)
{
    if (!s->anchored) return;
    s->raw_stamp = stamp;
    s->raw_ledger = ledger;
    s->raw_rate = rate;
    if (!s->rate || !rate) {
        discontinuity(s, SHADOW_RATE_UNKNOWN);
        s->remainder = 0;
    } else {
        /* Carry the fractional Q32-unit remainder into the next rate.
         * Truncation loses less than one 2^-32 ns unit per rate change. */
        s->remainder = (uint32_t)((uint64_t)s->remainder * rate / s->rate);
    }
    s->rate_changes += rate != s->rate;
    s->rate = rate;
    s->last_stamp = stamp;
    s->last_ledger = ledger;
}
