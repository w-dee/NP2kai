/* SPDX-License-Identifier: MIT */
#include "pit0_time.h"
#include <string.h>

static uint32_t period(unsigned count)
{
    return (count > 8 ? count : 65536u) * 5u;
}
static void add_sat(uint64_t *v, uint64_t n)
{
    *v = n > UINT64_MAX - *v ? UINT64_MAX : *v + n;
}
void pit0_time_reset(PIT0_TIME *s, int clock8)
{
    memset(s, 0, sizeof(*s));
    /* 1996800*5/1e9 = 780/78125; 2457600*5/1e9 = 960/78125. */
    s->numerator = clock8 ? 780 : 960;
    s->remaining = period(0);
}
void pit0_time_schedule(PIT0_TIME *s, unsigned count)
{
    s->remaining = period(count);
    s->mask_first = 1; /* Any existing mask was inserted before this timer. */
}
void pit0_time_mask(PIT0_TIME *s, unsigned count)
{
    s->mask_remaining = period(count) / 4;
    s->mask_first = 0;
}
PIT0_EFFECT pit0_time_observe(PIT0_TIME *s, PIT0_SAMPLE now,
                            unsigned count, int periodic, int armed, int masked)
{
    PIT0_EFFECT effect = {0, armed};
    uint64_t delta, part, ticks, expiries = 0, last = 0;
    uint32_t old_mask = s->mask_remaining, first = s->remaining;
    int publish = 0, clear;
    add_sat(&s->services, 1);
    if (!now.valid || (s->anchored && now.ns < s->anchor_ns)) {
        add_sat(&s->rejected, 1);
        return effect;
    }
    if (!s->anchored) {
        s->anchor_ns = now.ns;
        s->anchored = 1;
        return effect;
    }
    delta = now.ns - s->anchor_ns;
    s->anchor_ns = now.ns;
    if (delta > s->max_gap_ns) s->max_gap_ns = delta;
    part = (delta % 78125u) * s->numerator + s->fraction;
    ticks = (delta / 78125u) * s->numerator + part / 78125u;
    s->fraction = (uint32_t)(part % 78125u);
    if (!ticks) return effect;
    if (ticks >= first) {
        uint32_t next = periodic ? period(count) : period(0);
        expiries = 1 + (ticks - first) / next;
        publish = armed || (periodic && expiries > 1);
        last = periodic ? first + (expiries - 1) * next : first;
        s->remaining = next - (uint32_t)((ticks - first) % next);
        effect.armed = periodic;
        if (expiries > 1) add_sat(&s->collapsed, expiries - 1);
    } else {
        s->remaining -= (uint32_t)ticks;
    }
    clear = old_mask && ticks >= old_mask && masked;
    if (old_mask)
        s->mask_remaining = ticks >= old_mask ? 0 : old_mask - (uint32_t)ticks;
    if (publish) {
        effect.irr_effect = 1;
        if (periodic && masked) {
            uint32_t delay = period(count) / 4; /* Parent M_ref=5 integer floor. */
            uint64_t after = ticks - last;
            s->mask_remaining = after >= delay ? 0 : delay - (uint32_t)after;
            effect.irr_effect = s->mask_remaining ? 1 : -1;
            s->mask_first = 1; /* systimer publishes then rearms itself. */
        } else if (clear && (old_mask > last ||
                            (old_mask == last && !s->mask_first))) {
            effect.irr_effect = -1;
        }
    } else if (clear) {
        effect.irr_effect = -1;
    }
    return effect;
}
int pit0_time_deadline(const PIT0_TIME *s, uint64_t *ns)
{
    uint64_t q = s->remaining, delta;
    if (!s->anchored) return 0;
    if (s->mask_remaining && s->mask_remaining < q) q = s->mask_remaining;
    delta = (q * 78125u - s->fraction + s->numerator - 1) / s->numerator;
    if (delta > UINT64_MAX - s->anchor_ns) return 0;
    *ns = s->anchor_ns + delta;
    return 1;
}
