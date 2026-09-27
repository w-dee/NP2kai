/* SPDX-License-Identifier: MIT */
#ifndef NP2_LEGACYTIME_H
#define NP2_LEGACYTIME_H

/* Internal legacy units, not serialized wrappers or host timestamps.
 * compiler.h supplies the existing integer types and INLINE definition. */
typedef UINT32 LEGACY_CYCLESTAMP; /* modulo-2^32 CPU-derived device position */
typedef SINT32 LEGACY_DEADLINE;   /* signed offset from NEVENT slice origin */
typedef UINT32 LEGACY_CYCLE_RATE; /* configured virtual cycles/second */

static INLINE LEGACY_CYCLESTAMP legacy_cycles_now(UINT32 committed,
                                                 SINT32 slice, SINT32 remaining)
{
    /* Keep unsigned arithmetic from the FIRST addition, including wrap. */
    return committed + slice - remaining;
}

static INLINE SINT32 legacy_slice_elapsed(SINT32 slice, SINT32 remaining)
{
    /* Signed overshoot is intentional. Do not widen/clamp this subtraction. */
    return slice - remaining;
}

static INLINE void legacy_budget_begin(SINT32 *slice, SINT32 *remaining,
                                       LEGACY_DEADLINE deadline)
{
    *slice = deadline;
    *remaining = *slice;
}

static INLINE void legacy_budget_continue(SINT32 *slice, SINT32 *remaining,
                                          LEGACY_DEADLINE deadline)
{
    /* After committing the old slice, carry (possibly negative) overshoot. */
    *slice = deadline;
    *remaining += deadline;
}

static INLINE void legacy_budget_forceexit(SINT32 *slice, SINT32 *remaining)
{
    if (*remaining > 0) {
        *slice -= *remaining;
        *remaining = 0;
    }
}

static INLINE LEGACY_CYCLE_RATE legacy_configured_rate(UINT32 base_hz, UINT multiple)
{
    return base_hz * multiple;
}

static INLINE LEGACY_DEADLINE legacy_deadline_from_ms(LEGACY_CYCLE_RATE rate,
                                                     SINT32 ms)
{
    /* Preserve divide-before-multiply, UINT64 promotion of negative ms,
     * and the original unsigned INT_MAX-rate clamp, including its limits. */
    UINT64 waittime = (UINT64)(rate / 1000) * ms;
    if (waittime > INT_MAX - rate)
        return INT_MAX - rate;
    return (SINT32)waittime;
}

#endif
