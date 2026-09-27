/* SPDX-License-Identifier: MIT */
#include "timeshadow_account.h"
#include <assert.h>
#include <inttypes.h>
#include <stdio.h>

typedef struct { uint64_t now; int valid; } FAKE_CLOCK;
static SHADOW_HOST_SAMPLE fake_clock(void *context)
{
    FAKE_CLOCK *clock = context;
    SHADOW_HOST_SAMPLE sample = {clock->now, clock->valid};
    return sample;
}
static void sample(TIME_SHADOW *s, FAKE_CLOCK *f, int64_t cycles, uint32_t rate)
{
    SHADOW_CLOCK clock = fake_clock;
    shadow_observe(s, clock(f), (uint32_t)cycles, rate, cycles, 1);
}

int main(void)
{
    TIME_SHADOW s;
    FAKE_CLOCK f = {123456789, 1};
    uint64_t anchor = f.now;
    int64_t cycles = 0;
    uint32_t seed = 0x980286;
    unsigned i;
    shadow_reset(&s);
    sample(&s, &f, 0, 1000000000);
    for (i = 0; i < 1000; ++i) {
        f.now += 1000000; cycles += 1000000;
        sample(&s, &f, cycles, 1000000000);
        assert(s.comparison_valid && s.divergence_ns == 0);
    }
    f.now += 5000000; sample(&s, &f, cycles, 1000000000);
    assert(s.divergence_ns == 5000000 && s.max_host_interval_ns == 5000000);
    puts("5 ms: divergence=5000000 ns, no guest advancement");
    f.now += 20000000; sample(&s, &f, cycles, 1000000000);
    assert(s.divergence_ns == 25000000 && s.max_host_interval_ns == 20000000);
    puts("20 ms: cumulative divergence=25000000 ns");
    for (i = 0; i < 10000; ++i) {
        uint32_t delta;
        seed = seed * 1664525u + 1013904223u;
        delta = seed % 30000001u;
        f.now += delta; cycles += delta / 2;
        sample(&s, &f, cycles, 1000000000);
        assert(s.comparison_valid);
        assert(s.divergence_ns == (int64_t)(f.now - anchor) - cycles);
    }
    puts("random: 10000 seeded forward jumps PASS");
    sample(&s, &f, cycles, 1000000000); /* identical host timestamp */
    assert(s.comparison_valid);
    f.now--; cycles += 123;
    sample(&s, &f, cycles, 1000000000);
    assert(s.invalid_host_samples == 1 && !s.comparison_valid);
    f.valid = 0; sample(&s, &f, cycles, 1000000000);
    assert(s.invalid_host_samples == 2);
    f.valid = 1; f.now += 1000; sample(&s, &f, cycles, 1000000000);
    assert(s.comparison_valid && s.legacy_cycles == (uint64_t)cycles);

    shadow_reset(&s); f.now = 0;
    sample(&s, &f, 0xfffffff0LL, 1000000000);
    f.now = 32; sample(&s, &f, 0x100000010LL, 1000000000);
    assert(s.observed_wraps == 1 && s.legacy_cycles == 32 && s.divergence_ns == 0);
    f.now += 0x200000000ULL;
    sample(&s, &f, 0x300000010LL, 1000000000);
    assert(s.observed_wraps == 3 && s.comparison_valid);
    /* With no independent evidence, the same modulo stamp hides wraps. */
    f.now += 0x300000000ULL;
    shadow_observe(&s, fake_clock(&f), 0x10, 1000000000, 0x600000010LL, 0);
    assert(s.discontinuities == 1 && !s.comparison_valid);
    assert(s.raw_ledger == 0x600000010LL && s.raw_host_ns == f.now);
    assert(s.max_host_interval_ns == 0x300000000ULL);
    {
        uint64_t bad_host = f.now;
        f.now += 100;
        sample(&s, &f, 0x600000010LL, 1000000000);
        assert(s.raw_host_ns == f.now && s.first_bad_host_ns == bad_host);
        assert(s.first_bad_stamp == 0x10 && s.first_bad_ledger == 0x600000010LL);
        assert(s.first_bad_rate == 1000000000 && !s.comparison_valid);
    }

    shadow_reset(&s); f.now = 100; cycles = 0;
    sample(&s, &f, cycles, 3);
    for (i = 1; i <= 3; ++i) { f.now += 333333333; sample(&s, &f, i, 3); }
    assert(s.legacy_ns == 1000000000 && s.legacy_fraction == 0 && s.remainder == 0);
    /* Piecewise rates with fractional remnants and coordinate rescaling. */
    shadow_reset(&s); sample(&s, &f, 0, 3);
    cycles = 0;
    for (i = 0; i < 21000; ++i) {
        uint32_t rate = (i & 1) ? 7 : 3;
        shadow_rate_anchor(&s, (uint32_t)cycles, cycles, rate);
        cycles++; f.now += 100000000;
        sample(&s, &f, cycles, rate);
    }
    /* 10500/3 + 10500/7 = 5000 seconds. Loss <21000*2^-32 ns. */
    assert(s.legacy_ns == 4999999999999ULL || s.legacy_ns == 5000000000000ULL);
    assert(s.legacy_ns == 5000000000000ULL || s.legacy_fraction > 0xffff0000u);
    assert(s.legacy_cycles == 21000 && s.rate_changes == 20999);
    assert(s.max_negative_ns < 0 && s.max_absolute_ns == (uint64_t)-s.max_negative_ns);
    shadow_rate_anchor(&s, 123, 123, 10); /* rescale is not executed work */
    f.now += 100000000; sample(&s, &f, 124, 10);
    assert(s.legacy_cycles == 21001 && s.comparison_valid);

    /* Unannounced rate change, reset/backward ledger, and modulo mismatch. */
    sample(&s, &f, 125, 11);
    assert(!s.legacy_valid && s.discontinuity_reasons & SHADOW_RATE_UNKNOWN);
    assert(s.legacy_cycles == 21001); /* unknown-rate interval was not guessed */
    shadow_reset(&s); sample(&s, &f, 100, 10); sample(&s, &f, 0, 10);
    assert(s.discontinuity_reasons & SHADOW_BAD_LEDGER);
    shadow_reset(&s); sample(&s, &f, 0, 10);
    shadow_observe(&s, fake_clock(&f), 2, 10, 1, 1);
    assert(s.discontinuity_reasons & SHADOW_BAD_LEDGER);

    /* Very large host gap is recorded, never clamped to a stall policy. */
    shadow_reset(&s); f.now = 0; sample(&s, &f, 0, 10);
    f.now = UINT64_MAX; sample(&s, &f, 0, 10);
    assert(s.host_target_ns == UINT64_MAX && s.max_host_interval_ns == UINT64_MAX);
    assert(s.discontinuity_reasons & SHADOW_OVERFLOW && !s.comparison_valid);
    shadow_reset(&s); f.now = 0; sample(&s, &f, 0, 1);
    sample(&s, &f, INT64_MAX, 1);
    assert(s.discontinuity_reasons & SHADOW_OVERFLOW);
    shadow_reset(&s); sample(&s, &f, 0, 0);
    assert(s.discontinuity_reasons & SHADOW_RATE_UNKNOWN);

    shadow_reset(&s); f.now = 444; f.valid = 0;
    sample(&s, &f, 10, 1000); assert(!s.anchored);
    f.valid = 1; sample(&s, &f, 500, 1000);
    assert(s.anchored && s.epoch_host_ns == 444 && s.epoch_stamp == 500);
    assert(s.host_target_ns == 0 && s.legacy_cycles == 0 && s.comparison_valid);
    puts("epoch, wrap/witness ambiguity, rates/fractions, invalid samples, overflow: PASS");
    {
        SHADOW_HOST_SAMPLE previous = shadow_monotonic(NULL), current;
        uint64_t resolution = shadow_monotonic_resolution_ns();
        assert(previous.valid && resolution > 0);
        for (i = 0; i < 100000; ++i) {
            current = shadow_monotonic(NULL);
            assert(current.valid && current.ns >= previous.ns);
            previous = current;
        }
        printf("CLOCK_MONOTONIC: frequency=1000000000 units/s resolution=%" PRIu64
               " ns; 100000 ordered reads PASS\n", resolution);
    }
    return 0;
}
