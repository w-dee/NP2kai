/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "cpupacing.h"
#include <errno.h>
#include <time.h>

SDL_CPU_PACING sdl_cpu_pacing;

void sdl_cpu_pacing_begin(uint32_t cycles, uint64_t rate)
{
    struct timespec now;
    SDL_CPU_PACING *p = &sdl_cpu_pacing;
    p->active = 0;
    p->waited_ns = 0;
    if (!rate || clock_gettime(CLOCK_MONOTONIC, &now)) return;
    p->origin = cycles;
    p->rate = rate;
    /* 0.5 ms of the selected CPU throughput, not a device deadline. */
    p->quantum = (uint32_t)(rate / 2000);
    if (!p->quantum) p->quantum = 1;
    p->next = cycles + p->quantum;
    p->host_origin = (uint64_t)now.tv_sec * 1000000000 + now.tv_nsec;
    p->active = 1;
}

void sdl_cpu_pacing_wait(uint32_t cycles)
{
    SDL_CPU_PACING *p = &sdl_cpu_pacing;
    uint32_t consumed = cycles - p->origin;
    uint64_t target;
    struct timespec deadline, before, after;
    int error;
    if (!p->active) return;
    /* Reset/discontinuous ledger: do not turn a backward jump into credit
     * or a multi-second sleep. The next ordinary frame establishes an epoch. */
    if (consumed >= UINT32_C(0x80000000)) { p->active = 0; return; }
    target = p->host_origin + (uint64_t)consumed * 1000000000 / p->rate;
    deadline.tv_sec = (time_t)(target / 1000000000);
    deadline.tv_nsec = (long)(target % 1000000000);
    if (clock_gettime(CLOCK_MONOTONIC, &before)) { p->active = 0; return; }
    /* Absolute sleep returns immediately when execution is already late.
     * Nothing here reads/writes a guest, device, event or renderer object. */
    do {
        error = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &deadline, 0);
    } while (error == EINTR);
    if (error) p->active = 0;
    if (!clock_gettime(CLOCK_MONOTONIC, &after)) {
        uint64_t a = (uint64_t)before.tv_sec * 1000000000 + before.tv_nsec;
        uint64_t b = (uint64_t)after.tv_sec * 1000000000 + after.tv_nsec;
        if (b >= a) p->waited_ns += b - a;
    }
    p->next = cycles + p->quantum;
}

void sdl_cpu_pacing_end(uint32_t cycles)
{
    sdl_cpu_pacing_wait(cycles);
    sdl_cpu_pacing.active = 0;
}

/* Existing adaptive draw policy measures work, not deliberately inserted idle.
 * Keep the real frontend counter untouched for processwait and frame cadence. */
unsigned sdl_cpu_pacing_work_count(uint32_t raw, uint64_t waited_ns,
                                   uint32_t msstep, uint32_t speed)
{
    uint64_t rate = (uint64_t)msstep * speed;
    uint64_t limit = (uint64_t)raw * 128000000;
    uint64_t enough;
    if (!rate) return raw >> 16;
    enough = limit / rate + (limit % rate != 0);
    if (waited_ns >= enough) return 0;
    /* The comparison bounds this multiplication below raw * 128000000. */
    return (unsigned)((raw - waited_ns * rate / 128000000) >> 16);
}
