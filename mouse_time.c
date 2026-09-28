/* SPDX-License-Identifier: MIT */
#include "mouse_time.h"
#include <string.h>

static int bounded(int64_t n)
{ return n >= -MOUSE_MOVEMENT_LIMIT && n <= MOUSE_MOVEMENT_LIMIT; }

int mouse_time_reset(MOUSE_TIME *s, uint64_t q)
{
    if (q > MOUSE_TIME_LIMIT_Q) return 0;
    memset(s, 0, sizeof(*s));
    s->origin = s->frontier = s->batch_start = q;
    s->next_capture = q + MOUSE_CAPTURE_Q;
    s->host_buttons = 0xa0;
    return 1;
}

int mouse_time_admit(MOUSE_TIME *s, MOUSE_INPUT r)
{
    uint64_t capture, other;
    int64_t x = r.x, y = r.y;
    unsigned i;
    if (r.q < s->frontier || (s->sealed && r.q == s->frontier) ||
        r.q > MOUSE_TIME_LIMIT_Q || !bounded(x) || !bounded(y) ||
        (r.buttons & ~0xa0) || s->count == MOUSE_INPUT_CAPACITY ||
        (s->have_sequence && (r.sequence <= s->sequence || r.q < s->last_input_q)))
        return 0;
    capture = (r.q - s->origin + MOUSE_CAPTURE_Q - 1) / MOUSE_CAPTURE_Q;
    if (!capture) capture = 1;
    for (i = 0; i < s->count; ++i) {
        other = (s->input[i].q - s->origin + MOUSE_CAPTURE_Q - 1) / MOUSE_CAPTURE_Q;
        if (!other) other = 1;
        if (other == capture) { x += s->input[i].x; y += s->input[i].y; }
    }
    if (!bounded(x) || !bounded(y)) return 0;
    s->input[s->count++] = r;
    s->sequence = r.sequence; s->last_input_q = r.q; s->have_sequence = 1;
    return 1;
}

static int motion(MOUSE_TIME *s, uint64_t q)
{
    unsigned i;
    uint64_t elapsed = q - s->batch_start;
    if (elapsed > MOUSE_CAPTURE_Q) elapsed = MOUSE_CAPTURE_Q;
    for (i = 0; i < 2; ++i) {
        int64_t magnitude = s->batch[i];
        int32_t delivered;
        int64_t live;
        if (magnitude < 0) magnitude = -magnitude;
        magnitude *= elapsed; /* bounded: <=32767*2500000000 */
        delivered = (int32_t)(magnitude / MOUSE_CAPTURE_Q);
        if (s->batch[i] < 0) delivered = -delivered;
        live = (int64_t)s->live[i] + delivered - s->emitted[i];
        if (!bounded(live)) return 0;
        s->live[i] = (int32_t)live;
        s->emitted[i] = delivered;
        s->residue[i] = magnitude % MOUSE_CAPTURE_Q;
    }
    return 1;
}

int mouse_time_settle(MOUSE_TIME *state, uint64_t q)
{
    MOUSE_TIME next = *state;
    MOUSE_TIME *s = &next;
    if (q < s->frontier || q > MOUSE_TIME_LIMIT_Q || s->rate > 3) return 0;
    while (s->next_capture <= q) {
        unsigned n = 0;
        int64_t x = 0, y = 0;
        uint64_t t = s->next_capture, limit, skip;
        if (!motion(s, t)) return 0;
        while (n < s->count && s->input[n].q <= t) {
            x += s->input[n].x; y += s->input[n].y;
            s->host_buttons = s->input[n].buttons;
            ++n;
        }
        if (!bounded(x) || !bounded(y)) return 0;
        s->count -= n;
        memmove(s->input, s->input + n, s->count * sizeof(s->input[0]));
        memset(s->input + s->count, 0, n * sizeof(s->input[0]));
        s->batch[0] = (int32_t)x; s->batch[1] = (int32_t)y;
        s->emitted[0] = s->emitted[1] = 0;
        s->residue[0] = s->residue[1] = 0;
        s->batch_start = t; s->buttons = s->host_buttons;
        s->next_capture += MOUSE_CAPTURE_Q; ++s->captures;
        /* Empty capture runs have no per-boundary effect beyond phase/count.
         * A nonempty batch first completes at its following capture. */
        if (!x && !y) {
            limit = q;
            if (s->count && s->input[0].q <= limit) limit = s->input[0].q - 1;
            if (limit >= s->next_capture) {
                skip = (limit - s->next_capture) / MOUSE_CAPTURE_Q + 1;
                s->next_capture += skip * MOUSE_CAPTURE_Q;
                s->captures += skip;
                s->batch_start = s->next_capture - MOUSE_CAPTURE_Q;
            }
        }
    }
    if (!motion(s, q)) return 0;
    /* Capture and expiry commute in this profile: captures never touch IRQ
     * state. Publication is deferred until all transactional checks succeed. */
    if (s->irq_pending && s->next_irq <= q) {
        uint64_t n = 1, period = MOUSE_IRQ_Q << s->rate;
        if (s->enabled) {
            n += (q - s->next_irq) / period;
            s->next_irq += n * period;
            s->publications += n;
        } else s->irq_pending = 0;
        s->expiries += n;
    }
    s->frontier = q; s->sealed = 1;
    *state = next;
    return 1;
}

int mouse_time_enable(MOUSE_TIME *s, int enabled)
{
    if (s->rate > 3) return 0;
    if (enabled && !s->irq_pending) {
        s->next_irq = s->frontier + (MOUSE_IRQ_Q << s->rate);
        s->irq_pending = 1;
    }
    s->enabled = !!enabled;
    return 1;
}
