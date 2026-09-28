/* SPDX-License-Identifier: MIT */
#ifndef NP2_TIER1_MACHINE_H
#define NP2_TIER1_MACHINE_H
#if defined(NP2_TIER1_MACHINE_TIME)
#include <stdint.h>
/* Exact common lattice for both admitted B, Q=15625, 1920Hz and 282/5Hz.
 * This is a private fake-source representation, not a hardware clock rate. */
#define TIER1_HZ UINT64_C(23462400000000)
#define TIER1_LIMIT (TIER1_HZ * UINT64_C(86400))
#define TIER1_FRAME (TIER1_HZ / 282 * 5)
#define TIER1_KEY_PERIOD (TIER1_HZ / 1920)
#define TIER1_INPUT_CAPACITY 128u
#define TIER1_SOURCES 8u
#define TIER1_KEYS 0x71u
/* Bounded ordinary PC-98 key identity after frontend mapping; 1 key -> 1 byte.
 * Source ids 1..8, action 1=press / 0=release. No live adapter in this pilot. */
typedef struct { uint64_t q, sequence; unsigned source, key, down; } TIER1_EDGE;
typedef struct {
 uint64_t frontier, cursor, key_due, fdc_due, busy_due, seek_due[4];
 uint64_t sequence, input_q, epoch, edges_applied, key_expiries;
 unsigned base, count, ready, sealed, have_sequence, key_armed, fdc_armed, busy_armed;
 unsigned owners[TIER1_KEYS];
 TIER1_EDGE input[TIER1_INPUT_CAPACITY];
} TIER1_MACHINE;
extern TIER1_MACHINE tier1_machine;
extern uint64_t tier1_fake_now;
extern int tier1_dispatching;
int tier1_admit(TIER1_EDGE edge);
int tier1_settle(uint64_t q);
int tier1_start(uint64_t q, unsigned base);
int tier1_gdc_duration(unsigned dots, uint64_t *duration);
void tier1_service(void);
void tier1_reject(void);
void tier1_fdc_irq(void);
void tier1_fdc_seek(unsigned drive, unsigned frames);
void tier1_fdc_reset(void);
void tier1_key_arm(void);
void tier1_key_reset(void);
void tier1_gdc_wait(unsigned dots);
void tier1_gdc_raw(unsigned cycles);
void tier1_gdc_reset(void);
#define TIER1_SERVICE() tier1_service()
#define TIER1_SEEK(d,n) tier1_fdc_seek((d),(n))
#else
#define TIER1_SERVICE() ((void)0)
#define TIER1_SEEK(d,n) (fdc.int_timer[(d)] = (n))
#endif
#endif
