/* Private, default-OFF BEEP reference. Events apply at the common grid frontier. */
#ifndef NP2_BEEP_WAVEFORM_POLICY_H
#define NP2_BEEP_WAVEFORM_POLICY_H
#include <compiler.h>
#include <stdint.h>
typedef struct {
    UINT8 mode, enabled, have_data, edge_pending;
    UINT16 data, hz, phase;
    UINT32 offset_count;
    int64_t offset_sum;
    SINT32 offset;
} BEEP_WAVEFORM_STATE;
void beep_waveform_reset(BEEP_WAVEFORM_STATE *state);
void beep_waveform_mode(BEEP_WAVEFORM_STATE *state, UINT8 mode);
void beep_waveform_data(BEEP_WAVEFORM_STATE *state, UINT16 data);
void beep_waveform_hz(BEEP_WAVEFORM_STATE *state, UINT16 hz);
void beep_waveform_edge(BEEP_WAVEFORM_STATE *state, UINT8 enabled);
void beep_waveform_render(BEEP_WAVEFORM_STATE *state, SINT32 *pcm, UINT count,
    SINT32 volume, SINT32 master_volume, UINT8 adaptive_offset);
#endif
