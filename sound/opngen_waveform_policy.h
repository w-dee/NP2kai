/* Private reference profile; deliberately absent from user configuration. */
#pragma once
#include <sound/opngen.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    LEGACY_NATIVE_W0_PROFILE = 0,
    MACHINE_TIME_CONTINUOUS_WAVEFORM_PROFILE = 1
};

void SOUNDCALL opngen_getpcm_continuous(OPNGEN opngen, SINT32 *pcm, UINT count);
void SOUNDCALL opngen_getpcmvr_continuous(OPNGEN opngen, SINT32 *pcm, UINT count);

#ifdef __cplusplus
}
#endif
