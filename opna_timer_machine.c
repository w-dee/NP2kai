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
#if !defined(NP2_OPNA_CSM_HISTORY)
    if ((g_opna[0].s.reg[0x27] & 0xc0) == 0x80) reject(4);
#else
    if (pccore.baseclock != ((pccore.cpumode & CPUMODE_8MHZ) ? 1996800u : 2457600u) ||
        opna_timer_machine.time.numerator != ((pccore.cpumode & CPUMODE_8MHZ) ? 156u : 192u)) {
        if (opna_timer_machine.ready) reject(6);
    }
    if (opna_timer_machine.ready && !opna_timer_machine.history_epoch) reject(9);
    if (opna_timer_machine.ready &&
        ((opna_timer_machine.time.timer[0].active &&
          (!opna_timer_machine.time.timer[0].remaining || opna_timer_machine.time.timer[0].fraction >= 78125u)) ||
         (opna_timer_machine.time.timer[1].active &&
          (!opna_timer_machine.time.timer[1].remaining || opna_timer_machine.time.timer[1].fraction >= 78125u)))) reject(9);
    if (opna_timer_machine.history_count > OPNA_CSM_HISTORY_TEST_CAPACITY ||
        opna_timer_machine.history_finalized_count != opna_timer_machine.history_count)
        reject(9);
    if (opna_timer_machine.history_next_sequence != opna_timer_machine.history_count) {
        if (opna_timer_machine.history_next_sequence == UINT64_MAX) reject(8);
        reject(9); /* no insertion before an already finalized sequence */
    }
#endif
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
{
#if defined(NP2_OPNA_CSM_HISTORY)
    uint64_t epoch = opna_timer_machine.history_epoch;
    memset(&opna_timer_machine, 0, sizeof(opna_timer_machine));
    opna_timer_machine.history_epoch = epoch;
#else
    memset(&opna_timer_machine, 0, sizeof(opna_timer_machine));
#endif
}
void opna_timer_machine_reset(void)
{
#if defined(NP2_OPNA_CSM_HISTORY)
    if (opna_timer_machine.history_epoch == UINT64_MAX) reject(8);
#endif
    opna_timer_machine_discard();
#if defined(NP2_OPNA_CSM_HISTORY)
    opna_timer_machine.history_epoch++;
#endif
    scope();
    if (pccore.baseclock != ((pccore.cpumode & CPUMODE_8MHZ) ? 1996800u : 2457600u)) reject(6);
    opna_timer_time_reset(&opna_timer_machine.time, pccore.cpumode & CPUMODE_8MHZ);
    opna_timer_machine.ready = 1;
    opna_timer_machine_service();
#if defined(NP2_OPNA_CSM_HISTORY)
    opna_timer_machine.accepted_frontier_ns = opna_timer_machine.time.anchor_ns;
#endif
}
void opna_timer_machine_service_at(OPNA_TIMER_SAMPLE now)
{
    uint32_t p[2];
    unsigned due;
    _NEVENTITEM item;
    if (!opna_timer_machine.ready || opna_timer_machine.servicing) return;
    scope();
    periods(p);
#if defined(NP2_OPNA_CSM_HISTORY)
    if ((g_opna[0].s.reg[0x27] & 0xc0) == 0x80) {
        OPNA_TIMER_TIME next = opna_timer_machine.time;
        uint64_t required, old_ordinal, deadlines[OPNA_CSM_HISTORY_TEST_CAPACITY];
        unsigned i;
        required = opna_timer_time_expiries_until(&next, now, 0, p[0]);
        if (required > OPNA_CSM_HISTORY_TEST_CAPACITY - opna_timer_machine.history_count) {
            opna_timer_machine.rejection_required = required;
            opna_timer_machine.rejection_target_ns = now.ns;
            reject(7); /* accepted frontier and all semantic state remain old */
        }
        if (required > UINT64_MAX - next.expired[0] ||
            required > UINT64_MAX - opna_timer_machine.history_next_sequence) reject(8);
        for (i = 0; i < required; ++i)
            if (!opna_timer_time_nth_deadline(&next, 0, p[0], (uint64_t)i + 1, &deadlines[i]) ||
                deadlines[i] > now.ns) reject(8);
        old_ordinal = next.expired[0];
        due = opna_timer_time_observe(&next, now, p);
        if (next.expired[0] != old_ordinal + required || (!!(due & 1) != !!required)) reject(8);
        memset(&item, 0, sizeof(item));
        item.flag = NEVENT_SETEVENT;
        item.userData = (INTPTR)&g_opna[0];
        opna_timer_machine.servicing = 1;
        opna_timer_machine.time = next;
        for (i = 0; i < required; ++i) {
            OPNA_CSM_HISTORY_RECORD *r;
            fmport_a(&item); /* status/PIC/rearm before the logical CSM pair */
            r = &opna_timer_machine.history[opna_timer_machine.history_count++];
            r->epoch = opna_timer_machine.history_epoch;
            r->sequence = opna_timer_machine.history_next_sequence++;
            r->deadline_ns = deadlines[i];
            r->service_ns = now.ns;
            r->timer_a_ordinal = old_ordinal + i + 1;
            r->kind = OPNA_CSM_PAIR_KIND;
            r->key_off_subindex = 0;
            r->key_on_subindex = 1;
        }
        if (due & 2) fmport_b(&item);
        opna_timer_machine.history_finalized_count = opna_timer_machine.history_count;
        opna_timer_machine.accepted_frontier_ns = opna_timer_machine.time.anchor_ns;
        opna_timer_machine.servicing = 0;
        return;
    }
#endif
    opna_timer_machine.servicing = 1;
    due = opna_timer_time_observe(&opna_timer_machine.time, now, p);
    memset(&item, 0, sizeof(item));
    item.flag = NEVENT_SETEVENT;
    item.userData = (INTPTR)&g_opna[0];
    /* CSM-off status/PIC progression remains analytical and O(1) in the
     * expired-period count, exactly as in N6-T. */
    if (due & 1) fmport_a(&item);
    if (due & 2) fmport_b(&item);
#if defined(NP2_OPNA_CSM_HISTORY)
    opna_timer_machine.accepted_frontier_ns = opna_timer_machine.time.anchor_ns;
#endif
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
#if !defined(NP2_OPNA_CSM_HISTORY)
    if (address == 0x27 && (data & 0xc0) == 0x80) reject(4);
#endif
    opna_timer_machine_service(); /* old register values, including at equality */
}
