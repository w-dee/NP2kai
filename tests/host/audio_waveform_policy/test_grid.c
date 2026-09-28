#include "grid.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <limits.h>

static void check_rate(uint32_t rate)
{
    AudioWaveformSegment g = {UINT64_C(123456789), UINT64_C(777), rate}, next;
    uint64_t f, previous = 0, previous_ns = 0, floor_count = 0, remainder = 0;
    /* Independently accumulated exact quotient/remainder equals epoch formula. */
    for (uint64_t i = 0; i <= 200000; i++) {
        uint64_t dt = (uint64_t)(((__uint128_t)i * UINT64_C(1140071481932319)) / 200000);
        __uint128_t x = (__uint128_t)dt * rate;
        uint64_t expected = g.first_sample + (uint64_t)(x / 1000000000u) +
                            ((x % 1000000000u) != 0);
        assert(audio_waveform_frontier(&g, g.origin_ns + dt, &f) == 0);
        assert(f == expected && f >= previous);
        {
            __uint128_t piece = (__uint128_t)(dt - previous_ns) * rate + remainder;
            floor_count += (uint64_t)(piece / 1000000000u);
            remainder = (uint64_t)(piece % 1000000000u);
            assert(f == g.first_sample + floor_count + (remainder != 0));
        }
        previous_ns = dt;
        previous = f;
    }
    /* Exact boundaries include the event; adjacent integer ns map no earlier. */
    for (uint64_t sample = 0; sample < 10000; sample++) {
        uint64_t boundary = (sample * UINT64_C(1000000000)) / rate;
        if (sample * UINT64_C(1000000000) % rate) continue;
        assert(audio_waveform_frontier(&g,g.origin_ns+boundary,&f)==0);
        assert(f==g.first_sample+sample);
        if (boundary) {
            assert(audio_waveform_frontier(&g,g.origin_ns+boundary-1,&f)==0);
            assert(f==g.first_sample+sample);
        }
        assert(audio_waveform_frontier(&g,g.origin_ns+boundary+1,&f)==0);
        assert(f==g.first_sample+sample+1);
    }
    assert(audio_waveform_frontier(&g, g.origin_ns-1, &f) == -1);
    assert(audio_waveform_frontier(&g, UINT64_MAX, &f)==0);
    g.first_sample=UINT64_MAX;
    assert(audio_waveform_frontier(&g,g.origin_ns+1,&f)==-1);
    g.first_sample=777;
    assert(audio_waveform_frontier(&g,g.origin_ns+1000000000u,&f)==0);
    assert(audio_waveform_fenced_segment(&g,g.origin_ns+1000000000u,f,
           rate==44100?48000:44100,&next)==0);
    assert(next.first_sample==f && next.origin_ns==g.origin_ns+1000000000u);
    assert(audio_waveform_frontier(&next,next.origin_ns,&f)==0 && f==next.first_sample);
    assert(audio_waveform_fenced_segment(&g,g.origin_ns+1000000000u,f+1,48000,&next)==-1);
}
int main(void){check_rate(44100);check_rate(48000);puts("PASS grid ceil/boundary/long-range/fence");return 0;}
