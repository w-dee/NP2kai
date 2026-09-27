/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <legacycpu.h>
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
UINT32 test_committed;
SINT32 test_slice, test_remaining;

int main(void)
{
    UINT32 clocks[] = {0, 1, 0x7fffffff, 0xfffffff0, 0xffffffff};
    SINT32 slices[] = {0, 1, 100, 0x400000, -19};
    SINT32 remaining[] = {100, 0, -1, -23, -0x400000};
    UINT32 rates[] = {0, 999, 1001, 1996800, 2457600, 2457600*64u,
                      0x7fffffff, 0x80000000u, 0xffffffff};
    SINT32 millis[] = {0, 1, 166, 1001, INT_MAX, -1, INT_MIN};
    size_t i,j,k;
    for(i=0;i<sizeof(clocks)/sizeof(*clocks);i++)
        for(j=0;j<sizeof(slices)/sizeof(*slices);j++)
            for(k=0;k<sizeof(remaining)/sizeof(*remaining);k++) {
                UINT32 before;
                test_committed=clocks[i];test_slice=slices[j];test_remaining=remaining[k];
                before=legacy_cpu_device_now();
                assert(before == test_committed + test_slice - test_remaining);
                assert(legacy_cpu_slice_elapsed()==test_slice-test_remaining);
                legacy_cpu_rebase_slice(37);
                assert(legacy_cpu_device_now()==before);
                legacy_cpu_forceexit();
                assert(legacy_cpu_device_now()==before);
                legacy_cpu_commit_slice();
                legacy_cpu_continue_slice(91);
                assert(legacy_cpu_device_now()==before);
            }
    test_committed=UINT32_MAX;test_slice=1;test_remaining=-1;
    assert(legacy_cpu_device_now()==1);
    /* Widen only AFTER the original 32-bit timestamp wraps. */
    { UINT64 wide=legacy_cpu_device_now(); assert(wide==1); }
    legacy_cpu_begin_slice(10);
    legacy_cpu_charge(13);
    assert(test_remaining==-3 && legacy_cpu_slice_elapsed()==13);
    /* Preserve mixed signed/unsigned and size_t promotions at external debits. */
    { size_t charge=7; legacy_cpu_charge(charge); assert(test_remaining==-10); }
    for(i=0;i<sizeof(rates)/sizeof(*rates);i++)
        for(j=0;j<sizeof(millis)/sizeof(*millis);j++) {
            UINT64 old=(UINT64)(rates[i]/1000)*millis[j];
            SINT32 expected;
            if(old>INT_MAX-rates[i]) expected=INT_MAX-rates[i];
            else expected=(SINT32)old;
            assert(legacy_deadline_from_ms(rates[i],millis[j])==expected);
        }
    assert(legacy_deadline_from_ms(1001,1000)==1000); /* no rounding rewrite */
    assert(legacy_configured_rate(2457600,64)==157286400);
    assert(legacy_configured_rate(UINT32_MAX,2)==UINT32_MAX-1);
    puts("PASS helper arithmetic: wrap, signed overshoot, rebase, charge, configured rate, ms truncation/clamp");
    return 0;
}
