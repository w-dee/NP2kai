#include "grid.h"
#include <limits.h>
#include <stddef.h>

static int supported_rate(uint32_t rate)
{
    return rate == 44100u || rate == 48000u;
}

int audio_waveform_frontier(const AudioWaveformSegment *segment,
                            uint64_t event_ns, uint64_t *frontier)
{
    __uint128_t product, relative;
    if (!segment || !frontier || !supported_rate(segment->rate) ||
        event_ns < segment->origin_ns) return -1;
    product = (__uint128_t)(event_ns - segment->origin_ns) * segment->rate;
    relative = (product / AUDIO_WAVEFORM_NS_PER_SECOND) +
               ((product % AUDIO_WAVEFORM_NS_PER_SECOND) != 0);
    if (relative > UINT64_MAX - segment->first_sample) return -1;
    *frontier = segment->first_sample + (uint64_t)relative;
    return 0;
}

int audio_waveform_fenced_segment(const AudioWaveformSegment *old_segment,
                                  uint64_t fence_ns, uint64_t old_finalized_frontier,
                                  uint32_t new_rate, AudioWaveformSegment *next)
{
    uint64_t fence;
    if (!next || !supported_rate(new_rate) ||
        audio_waveform_frontier(old_segment, fence_ns, &fence) != 0 ||
        fence != old_finalized_frontier) return -1;
    next->origin_ns = fence_ns;
    next->first_sample = fence;
    next->rate = new_rate;
    return 0;
}
