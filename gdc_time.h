/* SPDX-License-Identifier: MIT */
#ifndef NP2_GDC_TIME_H
#define NP2_GDC_TIME_H
#include <stdint.h>

typedef struct { uint64_t ns; int valid; } GDC_SAMPLE;
typedef struct {
    uint32_t hclock, vclock, raster, horizontal, display, vertical;
} GDC_PROFILE;
typedef struct {
    uint64_t anchor_ns, ticks, services, rejected, max_gap_ns;
    uint64_t transitions, collapsed, max_late_ticks;
    uint32_t fraction, base, remaining;
    int anchored, vsync;
    GDC_PROFILE profile;
} GDC_TIME;
typedef struct { uint64_t vertical, display; int first_vertical; } GDC_EDGES;
int gdc_profile_make(GDC_PROFILE *p, const uint8_t sync[8], unsigned scan_class,
                     uint32_t fixed_base);
void gdc_time_reset(GDC_TIME *s, uint32_t fixed_base, const GDC_PROFILE *p);
int gdc_time_sample(GDC_TIME *s, GDC_SAMPLE now, uint64_t *ticks);
GDC_EDGES gdc_time_skip(GDC_TIME *s, uint64_t ticks);
unsigned gdc_time_status(const GDC_TIME *s);
int gdc_time_deadline(const GDC_TIME *s, uint64_t *ns);
GDC_SAMPLE gdc_time_source(void);
void gdc_add_sat(uint64_t *value, uint64_t amount);
#endif
