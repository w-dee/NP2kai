/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <pccore.h>
#include <io/iocore.h>
#include "pit0_time.h"

#if defined(SUPPORT_ASYNC_CPU) || defined(SUPPORT_IA32_HAXM)
#error PIT0 pilot requires the single-owner interpreter
#endif
PIT0_TIME pit0_machine_time;
void pit0_machine_service_at(PIT0_SAMPLE now)
{
    PITCH ch = pit.ch;
    PIT0_EFFECT e = pit0_time_observe(&pit0_machine_time, now,
        ch->value, (ch->ctrl & 0x0c) == 0x04,
        !!(ch->flag & PIT_FLAG_I), !!(pic.pi[0].imr & 1));
    if (e.armed) ch->flag |= PIT_FLAG_I;
    else ch->flag &= ~PIT_FLAG_I;
    if (e.irr_effect > 0) pic.pi[0].irr |= 1;
    else if (e.irr_effect < 0) pic.pi[0].irr &= ~1;
}
void pit0_machine_service(void)
{
    pit0_machine_service_at(pit0_time_source());
}
void pit0_machine_reset(void)
{
    pit0_time_reset(&pit0_machine_time, !!(pccore.cpumode & CPUMODE_8MHZ));
    pit0_machine_service();
}
void pit0_machine_schedule(unsigned count)
{
    pit0_time_schedule(&pit0_machine_time, count);
}
void pit0_machine_mask(void)
{
    pit0_time_mask(&pit0_machine_time, pit.ch[0].value);
}
void pit0_machine_ack(void)
{
    pit0_machine_time.mask_remaining = 0;
}
unsigned pit0_machine_count(void)
{
    return pit0_machine_time.remaining / 5;
}
