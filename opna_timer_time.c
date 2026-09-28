/* SPDX-License-Identifier: MIT */
#include "opna_timer_time.h"
#include <string.h>
#define DEN 78125u
static void add_saturated(uint64_t *v, uint64_t n)
{ *v = n > UINT64_MAX - *v ? UINT64_MAX : *v + n; }
void opna_timer_time_reset(OPNA_TIMER_TIME *s, int clock8)
{
    memset(s, 0, sizeof(*s));
    s->numerator = clock8 ? 156 : 192; /* base Hz / 10^9; no M_ref */
}
void opna_timer_time_control(OPNA_TIMER_TIME *s, unsigned control, const uint32_t period[2])
{
    unsigned i;
    for (i = 0; i < 2; ++i) {
        OPNA_TIMER_CHANNEL *t = &s->timer[i];
        if (!(control & (1u << i))) t->active = 0;
        else if (!t->active) {
            t->active = 1;
            t->remaining = period[i];
            t->fraction = 0;
        }
    }
}
unsigned opna_timer_time_observe(OPNA_TIMER_TIME *s, OPNA_TIMER_SAMPLE now, const uint32_t period[2])
{
    uint64_t delta;
    unsigned i, due = 0;
    if (!now.valid || (s->anchored && now.ns < s->anchor_ns)) {
        add_saturated(&s->rejected, 1);
        return 0;
    }
    if (!s->anchored) {
        s->anchor_ns = now.ns;
        s->anchored = 1;
        return 0;
    }
    delta = now.ns - s->anchor_ns;
    s->anchor_ns = now.ns;
    add_saturated(&s->services, 1);
    if (delta > s->max_gap_ns) s->max_gap_ns = delta;
    /* Exactly two channels, independent of expired-period count. The largest
     * ns delta produces < 2^56 ticks. Split before multiplying. */
    for (i = 0; i < 2; ++i) {
        OPNA_TIMER_CHANNEL *t = &s->timer[i];
        uint64_t part, ticks, count;
        if (!t->active) continue;
        part = (delta % DEN) * s->numerator + t->fraction;
        ticks = (delta / DEN) * s->numerator + part / DEN;
        t->fraction = part % DEN;
        if (ticks < t->remaining) {
            t->remaining -= (uint32_t)ticks;
            continue;
        }
        ticks -= t->remaining;
        count = 1 + ticks / period[i];
        t->remaining = period[i] - ticks % period[i];
        add_saturated(&s->expired[i], count);
        due |= 1u << i;
    }
    return due;
}
int opna_timer_time_deadline(const OPNA_TIMER_TIME *s, unsigned i, uint64_t *ns)
{
    uint64_t delta;
    const OPNA_TIMER_CHANNEL *t;
    if (i >= 2 || !s->anchored) return 0;
    t = &s->timer[i];
    if (!t->active) return 0;
    delta = ((uint64_t)t->remaining * DEN - t->fraction + s->numerator - 1) / s->numerator;
    if (delta > UINT64_MAX - s->anchor_ns) return 0;
    *ns = s->anchor_ns + delta;
    return 1;
}
