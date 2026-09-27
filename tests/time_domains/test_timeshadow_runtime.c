/* SPDX-License-Identifier: MIT */
/* Include the production adapter to inject its private clock without exposing
 * a public emulator API. Guest bindings are the existing ledger test stubs. */
#include "timeshadow_runtime.c"
#include <assert.h>
#include <stdio.h>

UINT32 test_committed;
SINT32 test_slice, test_remaining;
struct test_pccore pccore;
struct test_pcstat pcstat;
static uint64_t fake_now;
static SHADOW_HOST_SAMPLE fake(void *unused)
{
    SHADOW_HOST_SAMPLE result = {fake_now, 1};
    (void)unused;
    return result;
}

int main(void)
{
    source = fake;
    pccore.realclock = 1000;
    test_committed = 0xfffffff0u;
    test_slice = test_remaining = 20;
    time_shadow_reset();
    time_shadow_service();
    test_remaining = -12; /* execute 32 cycles, including overshoot */
    fake_now += 32000000;
    time_shadow_service();
    assert(np2_time_shadow.legacy_cycles == 32);
    assert(np2_time_shadow.observed_wraps == 1);
    assert(np2_time_shadow.divergence_ns == 0);
    time_shadow_commit(test_slice);
    legacy_cpu_commit_slice();
    legacy_cpu_continue_slice(30);
    time_shadow_service();
    assert(np2_time_shadow.legacy_cycles == 32);
    assert(np2_time_shadow.comparison_valid);
    time_shadow_rate_before(1000);
    test_slice *= 2; test_remaining *= 2; /* existing rate-coordinate rescale */
    pccore.realclock = 2000;
    time_shadow_rate_after(2000);
    test_remaining -= 20; fake_now += 10000000;
    time_shadow_service();
    assert(np2_time_shadow.legacy_cycles == 52);
    assert(np2_time_shadow.legacy_ns == 42000000);
    assert(np2_time_shadow.comparison_valid && np2_time_shadow.divergence_ns == 0);
    /* Load/reset hook discards only the diagnostic epoch. */
    time_shadow_reset();
    test_committed = 123; test_slice = test_remaining = 100;
    fake_now += 9000000000ULL;
    time_shadow_service();
    assert(np2_time_shadow_epochs == 2 && np2_time_shadow.samples == 1);
    assert(np2_time_shadow.epoch_stamp == 123 && np2_time_shadow.legacy_cycles == 0);
    assert(np2_time_shadow.host_target_ns == 0);
    /* Raw ledger changed without the commit witness: do not invent progress. */
    test_committed += 100;
    time_shadow_service();
    assert(!np2_time_shadow.comparison_valid && np2_time_shadow.discontinuities == 1);
    puts("Production runtime fake source, commit/overshoot/wrap, rate and load/reset hooks: PASS");
    return 0;
}
