/* Private deterministic SDL reference; no product time-source binding. */
#ifndef AUDIO_WAVEFORM_GRID_H
#define AUDIO_WAVEFORM_GRID_H
#include <stdint.h>

enum { AUDIO_WAVEFORM_NS_PER_SECOND = 1000000000u };
typedef struct {
    uint64_t origin_ns;
    uint64_t first_sample;
    uint32_t rate;
} AudioWaveformSegment;

/* 0=success, -1=invalid time/rate or overflow. Never truncate a frontier. */
int audio_waveform_frontier(const AudioWaveformSegment *segment,
                            uint64_t event_ns, uint64_t *frontier);
/* A rate transition is legal only at an already finalized sample frontier. */
int audio_waveform_fenced_segment(const AudioWaveformSegment *old_segment,
                                  uint64_t fence_ns, uint64_t old_finalized_frontier,
                                  uint32_t new_rate, AudioWaveformSegment *next);
#endif
