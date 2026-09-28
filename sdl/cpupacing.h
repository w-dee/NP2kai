/* SPDX-License-Identifier: MIT */
#ifndef NP2_SDL_CPUPACING_H
#define NP2_SDL_CPUPACING_H

/* Private Linux SDL live-GDC implementation, not a CPU or device-time API.
 * OFF and deterministic GDC builds have no interpreter hot-path overhead. */
#if defined(NP2_GDC_MACHINE_TIME) && !defined(NP2_GDC_FAKE_TIME)
#include <stdint.h>
typedef struct {
    uint32_t origin, next, quantum;
    uint64_t host_origin, rate, waited_ns;
    int active;
} SDL_CPU_PACING;
extern SDL_CPU_PACING sdl_cpu_pacing;
void sdl_cpu_pacing_begin(uint32_t cycles, uint64_t rate);
void sdl_cpu_pacing_wait(uint32_t cycles);
void sdl_cpu_pacing_end(uint32_t cycles);
unsigned sdl_cpu_pacing_work_count(uint32_t raw, uint64_t waited_ns,
                                   uint32_t msstep, uint32_t speed);
#define SDL_CPU_POSITION() ((uint32_t)CPU_CLOCK + \
    (uint32_t)CPU_BASECLOCK - (uint32_t)CPU_REMCLOCK)
#define SDL_CPU_CHECKPOINT() do { \
    if (sdl_cpu_pacing.active) { \
        uint32_t sdl_position_ = SDL_CPU_POSITION(); \
        if ((int32_t)(sdl_position_ - sdl_cpu_pacing.next) >= 0) \
            sdl_cpu_pacing_wait(sdl_position_); \
    } \
} while (0)
#else
#define SDL_CPU_CHECKPOINT() ((void)0)
#endif
#endif
