/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#define CPU_CLOCK ledger[0]
#define CPU_BASECLOCK ledger[1]
#define CPU_REMCLOCK ledger[2]
#include <sdl/cpupacing.h>
static uint32_t ledger[3], saved[3];
static uint64_t host, deadline_ns;
static unsigned sleeps, interruptions;
int __wrap_clock_gettime(clockid_t id, struct timespec *t)
{
    assert(id == CLOCK_MONOTONIC);
    t->tv_sec = host / 1000000000; t->tv_nsec = host % 1000000000;
    return 0;
}
int __wrap_clock_nanosleep(clockid_t id, int flags,
                         const struct timespec *t, struct timespec *remain)
{
    assert(id == CLOCK_MONOTONIC && flags == TIMER_ABSTIME && !remain);
    assert(!memcmp(ledger, saved, sizeof ledger));
    deadline_ns = (uint64_t)t->tv_sec * 1000000000 + t->tv_nsec;
    sleeps++;
    if (interruptions) { interruptions--; return EINTR; }
    if (host < deadline_ns) host = deadline_ns;
    return 0;
}
static void keep(void) { memcpy(saved, ledger, sizeof ledger); }
int main(void)
{
    /* Existing slice carries instruction overshoot and later NEVENT rebases.
     * Pacing is observation-only across all of them. */
    ledger[0]=100; ledger[1]=50000; ledger[2]=50000;
    host=1000000000; keep(); sdl_cpu_pacing_begin(SDL_CPU_POSITION(), 2000000);
    ledger[2]-=999; keep(); SDL_CPU_CHECKPOINT(); assert(!sleeps);
    ledger[2]-=1; keep(); SDL_CPU_CHECKPOINT();
    assert(sleeps==1 && host==1000500000 && !memcmp(ledger,saved,sizeof ledger));
    ledger[1]-=700; ledger[2]-=700; /* paired rebase changes no current position */
    keep(); SDL_CPU_CHECKPOINT(); assert(sleeps==1);
    ledger[2]-=1003; keep(); interruptions=1; SDL_CPU_CHECKPOINT();
    assert(sleeps==3 && host==1001001500);
    ledger[2]-=499; keep(); sdl_cpu_pacing_end(SDL_CPU_POSITION());
    assert(host==1001251000 && !sdl_cpu_pacing.active);
    assert(!memcmp(ledger,saved,sizeof ledger));
    /* Modulo clock wrap, final fractional debit, no wait for already-late work. */
    host=2000000000; sdl_cpu_pacing_begin(UINT32_MAX-100,1000000);
    sdl_cpu_pacing_wait(399); assert(host==2000500000);
    host+=10000000; sdl_cpu_pacing_end(400); assert(host==2010500000);
    /* Cold reset backward jump cannot become billions of credited cycles. */
    sdl_cpu_pacing_begin(1000000,1000000); sleeps=0;
    sdl_cpu_pacing_wait(0); assert(!sdl_cpu_pacing.active && !sleeps);
    sdl_cpu_pacing_begin(0,0); assert(!sdl_cpu_pacing.active);
    assert(sdl_cpu_pacing_work_count(65536,0,3697,128)==1);
    assert(sdl_cpu_pacing_work_count(65536,14000000,3697,128)==0);
    assert(sdl_cpu_pacing_work_count(3*65536,14000000,3697,128)==2);
    assert(sdl_cpu_pacing_work_count(65536,UINT64_MAX,3697,128)==0);
    assert(sdl_cpu_pacing_work_count(65536,5000000,0,128)==1);
    /* Independent wide-integer oracle for adaptive draw-time subtraction. */
    {
        uint32_t raws[] = {0,1,65535,65536,196608,UINT32_MAX};
        uint32_t steps[] = {0,3697,65536,UINT32_MAX};
        uint32_t speeds[] = {0,64,128,256,UINT32_MAX};
        uint64_t waits[] = {0,499999,500000,1000000,1000000000,UINT64_MAX};
        unsigned a,b,c,d;
        for(a=0;a<6;a++)for(b=0;b<4;b++)for(c=0;c<5;c++)for(d=0;d<6;d++) {
            __uint128_t idle=(__uint128_t)waits[d]*steps[b]*speeds[c]/128000000;
            unsigned expected=idle>=raws[a]?0:(unsigned)((raws[a]-(uint64_t)idle)>>16);
            assert(sdl_cpu_pacing_work_count(raws[a],waits[d],steps[b],speeds[c])==expected);
        }
    }
    puts("PASS: immutable CPU ledger, paired rebase, exact debit/overshoot, wrap, interruption, late host, reset");
}
