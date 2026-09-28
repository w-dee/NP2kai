/* SPDX-License-Identifier: MIT */
#ifndef NP2_MOUSE_TIME_H
#define NP2_MOUSE_TIME_H
#include <stdint.h>
/* Owner-approved normalized profile. One quantum = 1/(141*10^9) s.
 * Integer-ns sources multiply by 141; both autonomous periods remain exact. */
#define MOUSE_CAPTURE_Q UINT64_C(2500000000)
#define MOUSE_IRQ_Q UINT64_C(1175000000)
#define MOUSE_TIME_LIMIT_Q UINT64_C(12182400000000000) /* 24 hours/epoch */
#define MOUSE_INPUT_CAPACITY 256u /* pilot admission capacity, never a drop rule */
#define MOUSE_MOVEMENT_LIMIT 32767

typedef struct {
    uint64_t q, sequence;
    int32_t x, y;
    uint8_t buttons; /* active-low level, bits 7 and 5 */
} MOUSE_INPUT;
typedef struct {
    uint64_t origin, frontier, next_capture, batch_start, next_irq;
    uint64_t sequence, last_input_q, captures, expiries, publications;
    int32_t live[2], batch[2], emitted[2];
    uint64_t residue[2];
    unsigned count, rate;
    int sealed, have_sequence, irq_pending, enabled;
    uint8_t buttons, host_buttons;
    MOUSE_INPUT input[MOUSE_INPUT_CAPACITY];
} MOUSE_TIME;
/* All failing operations leave the entire input state unchanged. */
int mouse_time_reset(MOUSE_TIME *s, uint64_t q);
int mouse_time_admit(MOUSE_TIME *s, MOUSE_INPUT input);
int mouse_time_settle(MOUSE_TIME *s, uint64_t q);
int mouse_time_enable(MOUSE_TIME *s, int enabled);
#endif
