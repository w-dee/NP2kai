/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include "opna_timer_machine.h"
#include <pccore.h>
#include <sound/fmboard.h>
#include <sound/opntimer.h>
#include <stdio.h>
#include <stdlib.h>
OPNA_TIMER_MACHINE opna_timer_machine;
static void reject(int code)
{
    opna_timer_machine.admission_error = code;
    fprintf(stderr, "OPNA Timer machine-time profile not admitted: %d\n", code);
    abort();
}
void opna_timer_machine_admit(unsigned soundid)
{
    if (soundid != SOUNDID_PC_9801_86) reject(1);
#if defined(SUPPORT_FMGEN)
    if (enable_fmgen) reject(2);
#endif
}
static void scope(void)
{
    opna_timer_machine_admit(g_nSoundID);
    if (g_opna[0].s.cCaps != (OPNA_MODE_2608 | OPNA_HAS_TIMER | OPNA_S98)) reject(3);
    if ((g_opna[0].s.reg[0x27] & 0xc0) == 0x80) reject(4);
    /* Quiescent means no consumption, shared IRQ, or scheduled PCM work.
     * The original shared callback query is retained; fifo bit5=0 makes
     * pcm86gen_intrq return before mixer synchronization or mutation. */
    if ((g_pcm86.fifo & 0xa0) || g_pcm86.irqflag || g_pcm86.reqirq ||
        g_pcm86.realbuf || g_pcm86.virbuf || nevent_iswork(NEVENT_86PCM)) reject(5);
}
static void periods(uint32_t p[2])
{
    const UINT8 *r = g_opna[0].s.reg;
    uint32_t k = opna_timer_machine.time.numerator == 156 ? 1248 : 1536;
    p[0] = 18u * (1024u - ((r[0x24] << 2) | (r[0x25] & 3))) * k / 625;
    p[1] = 288u * (256u - r[0x26]) * k / 625;
}
void opna_timer_machine_discard(void)
{ memset(&opna_timer_machine, 0, sizeof(opna_timer_machine)); }
void opna_timer_machine_reset(void)
{
    opna_timer_machine_discard();
    scope();
    if (pccore.baseclock != ((pccore.cpumode & CPUMODE_8MHZ) ? 1996800u : 2457600u)) reject(6);
    opna_timer_time_reset(&opna_timer_machine.time, pccore.cpumode & CPUMODE_8MHZ);
    opna_timer_machine.ready = 1;
    opna_timer_machine_service();
}
void opna_timer_machine_service_at(OPNA_TIMER_SAMPLE now)
{
    uint32_t p[2];
    unsigned due;
    _NEVENTITEM item;
    if (!opna_timer_machine.ready || opna_timer_machine.servicing) return;
    scope();
    periods(p);
    opna_timer_machine.servicing = 1;
    due = opna_timer_time_observe(&opna_timer_machine.time, now, p);
    memset(&item, 0, sizeof(item));
    item.flag = NEVENT_SETEVENT;
    item.userData = (INTPTR)&g_opna[0];
    /* In the admitted profile these transitions commute: independent sticky
     * status bits and one shared PIC request. No CPU arbitration intervenes.
     * Later expiries without guest I/O cannot change this finite state. */
    if (due & 1) fmport_a(&item);
    if (due & 2) fmport_b(&item);
    opna_timer_machine.servicing = 0;
}
void opna_timer_machine_service(void)
{ opna_timer_machine_service_at(opna_timer_time_source()); }
void opna_timer_machine_control(unsigned data)
{
    uint32_t p[2];
    if (!opna_timer_machine.ready) return;
    scope();
    periods(p);
    opna_timer_time_control(&opna_timer_machine.time, data, p);
}
void opna_timer_machine_write(unsigned address, unsigned data)
{
    if (address == 0x27 && (data & 0xc0) == 0x80) reject(4);
    opna_timer_machine_service(); /* old register values, including at equality */
}
