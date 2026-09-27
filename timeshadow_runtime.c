/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <legacycpu.h>
#include "timeshadow.h"
#include "timeshadow_account.h"
#include <limits.h>

#if defined(SUPPORT_MULTITHREAD) || defined(SUPPORT_ASYNC_CPU) || defined(SUPPORT_IA32_HAXM)
#error Phase B runtime observer is qualified for the single emulation owner only
#endif

/* Read these from a stopped debugger. No runtime output or guest consumers. */
TIME_SHADOW np2_time_shadow;
uint64_t np2_time_shadow_epochs;
static int64_t committed;
static int ledger_valid = 1;
static SHADOW_CLOCK source = shadow_monotonic;

static int64_t ledger_position(void)
{
    __int128 value = (__int128)committed + (int64_t)CPU_BASECLOCK - CPU_REMCLOCK;
    if (value > INT64_MAX || value < INT64_MIN) {
        ledger_valid = 0;
        return committed;
    }
    return (int64_t)value;
}

void time_shadow_commit(int32_t cycles)
{
    __int128 value = (__int128)committed + cycles;
    if (value > INT64_MAX || value < INT64_MIN) ledger_valid = 0;
    else committed = (int64_t)value;
}

static void observe(uint32_t rate)
{
    int64_t position = ledger_position();
    shadow_observe(&np2_time_shadow, source(NULL), legacy_cpu_device_now(),
                   rate, position, ledger_valid);
}

void time_shadow_service(void)
{
    observe(pccore.realclock);
}

void time_shadow_reset(void)
{
    shadow_reset(&np2_time_shadow);
    np2_time_shadow_epochs++;
    committed = 0;
    ledger_valid = 1;
}

void time_shadow_rate_before(uint32_t rate)
{
    observe(rate);
}

void time_shadow_rate_after(uint32_t rate)
{
    shadow_rate_anchor(&np2_time_shadow, legacy_cpu_device_now(),
                       ledger_position(), rate);
}
