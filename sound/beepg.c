#include	<compiler.h>
#include	<cpucore.h>
#include	<sound/sound.h>
#include	<sound/beep.h>
#include	<sound/beep_waveform_policy.h>
#include	<string.h>
#include	<pccore.h>


static int beepOffsetCounter = 0;
static SINT32 beepOffsetSum = 0;
static SINT32 beepOffset = 0;

static void pushBeepOffsetData(SINT32 data) {
	if (np2cfg.nbeepofs) {
		beepOffsetSum += data;
		beepOffsetCounter++;
		beepOffset = beepOffsetSum / beepOffsetCounter;
	}
}
static void resetBeepOffsetData() {
	beepOffsetCounter = 0;
	beepOffsetSum = 0;
	beepOffset = 0;
}

extern	BEEPCFG		beepcfg;

static void oneshot(BEEP bp, SINT32 *pcm, UINT count) {
	
	SINT32		volM;
	SINT32		samp;
	UINT32		firsttime = beep_time[bp->beep_data_curr_loc];
	UINT32		time = firsttime;
	UINT32		bound;
	SINT32		curBeepOffset = beepOffset;

	if (!np2cfg.nbeepofs) {
		curBeepOffset = 0x2500 * beepcfg.vol; // 固定オフセット
	}

	volM = np2cfg.vol_master;

	if(bp->beep_data_load_loc != 0)
		bound = (beep_time[bp->beep_data_load_loc - 1] - firsttime) / count;
	else
		bound = (beep_time[BEEPDATACOUNT - 1] - firsttime) / count;

	while(count--) {
		while(time >= beep_time[bp->beep_data_curr_loc] && bp->beep_data_curr_loc != bp->beep_data_load_loc) {
			bp->beep_data_curr_loc++;
			if(bp->beep_data_curr_loc >= BEEPDATACOUNT)
				bp->beep_data_curr_loc = 0;
		}
		if(bp->beep_data_curr_loc != 0)
			samp = beep_data[bp->beep_data_curr_loc - 1];
		else
			samp = beep_data[BEEPDATACOUNT - 1];
		samp = (SINT32)((double)samp / 0x100 * (0x5000 * beepcfg.vol));
		if (beepOffsetCounter < 500 && np2cfg.nbeepofs)
		{
			// 平均オフセット 500サンプルまでを見る
			pushBeepOffsetData(samp);
			curBeepOffset = beepOffset;
		}
		samp -= curBeepOffset;
		pcm[0] += samp * volM / 100;
		pcm[1] += samp * volM / 100;
		pcm += 2;
		time += bound;
	}
}

static void rategenerator(BEEP bp, SINT32 *pcm, UINT count) {

	SINT32		vol;
	SINT32		volM;
const BPEVENT	*bev;
	SINT32		samp;
	SINT32		remain;
	SINT32		clk;
	int			event;
	UINT		r;
	
	volM = np2cfg.vol_master;

	vol = beepcfg.vol;
	bev = bp->event;
	if (bp->events) {
		bp->events--;
		clk = bev->clock;
		event = bev->enable;
		bev++;
	}
	else {
		clk = 0x40000000;
		event = bp->lastenable;
	}
	do {
		if (clk >= (1 << 16)) {
			r = clk >> 16;
			r = MIN(r, count);
			clk -= r << 16;
			count -= r;
			if (bp->lastenable) {
				do {
					samp = (bp->cnt & 0x8000)?1:-1;
					bp->cnt += bp->hz;
					samp += (bp->cnt & 0x8000)?1:-1;
					bp->cnt += bp->hz;
					samp += (bp->cnt & 0x8000)?1:-1;
					bp->cnt += bp->hz;
					samp += (bp->cnt & 0x8000)?1:-1;
					bp->cnt += bp->hz;
					samp *= vol;
					samp *= (1 << (10 - 2));
					if(samp > 32767) samp = 0; // XXX: 処理落ち時のノイズ回避 np21w ver0.86 rev42
					if(samp < -32768) samp = 0; // XXX: 処理落ち時のノイズ回避 np21w ver0.86 rev42
					pcm[0] += samp * volM / 100;
					pcm[1] += samp * volM / 100;
					pcm += 2;
				} while(--r);
			}
			else {
				pcm += 2 * r;
			}
		}
		else {
			remain = (1 << 16);
			samp = 0;
			while(remain >= clk) {
				remain -= clk;
				if (bp->lastenable) {
					samp += clk;
				}
				bp->lastenable = event;
				bp->cnt = 0;
				if (bp->events) {
					bp->events--;
					clk = bev->clock;
					event = bev->enable;
					bev++;
				}
				else {
					clk = 0x40000000;
				}
			}
			clk -= remain;
			if (bp->lastenable) {
				samp += remain;
			}
			samp *= vol;
			samp >>= (16 - 10);
			if(samp > 32767) samp = 0; // XXX: 処理落ち時のノイズ回避 np21w ver0.86 rev42
			if(samp < -32768) samp = 0; // XXX: 処理落ち時のノイズ回避 np21w ver0.86 rev42
			pcm[0] += samp * volM / 100;
			pcm[1] += samp * volM / 100;
			pcm += 2;
			count--;
		}
	} while(count);
	bp->lastenable = event;
	bp->events = 0;
}

void SOUNDCALL beep_getpcm(BEEP bp, SINT32 *pcm, UINT count) {

	if ((count) && (beepcfg.vol)) {
		if (bp->mode == 0) {
			if (bp->events) {
				oneshot(bp, pcm, count);
			}
		}
		else if (bp->mode == 1) {
			rategenerator(bp, pcm, count);
		}
	}
}


/* Ordered machine-time events are applied by the owner at ceil-mapped
 * frontiers. Renderer state and offset have no call-local clock. */
void beep_waveform_reset(BEEP_WAVEFORM_STATE *state) {
    memset(state, 0, sizeof(*state));
}
void beep_waveform_mode(BEEP_WAVEFORM_STATE *state, UINT8 mode) {
    state->mode = mode;
    state->enabled = 0;
    state->have_data = 0;
    state->edge_pending = 0;
}
void beep_waveform_data(BEEP_WAVEFORM_STATE *state, UINT16 data) {
    state->data = data;
    state->have_data = 1;
}
void beep_waveform_hz(BEEP_WAVEFORM_STATE *state, UINT16 hz) {
    state->hz = hz;
}
void beep_waveform_edge(BEEP_WAVEFORM_STATE *state, UINT8 enabled) {
    state->enabled = !!enabled;
    state->phase = 0;
    state->edge_pending = 1;
}
void beep_waveform_render(BEEP_WAVEFORM_STATE *state, SINT32 *pcm, UINT count,
        SINT32 volume, SINT32 master_volume, UINT8 adaptive_offset) {
    while (count--) {
        SINT32 sample = 0;
        if (state->mode == 0 && state->have_data) {
            /* Source mode 0 holds the latest PIT data until another write. */
            sample = (SINT32)(((int64_t)state->data * 0x5000 * volume) / 256);
            if (adaptive_offset && state->offset_count < 500) {
                state->offset_sum += sample;
                state->offset_count++;
                state->offset = (SINT32)(state->offset_sum / state->offset_count);
            }
            sample -= adaptive_offset ? state->offset : 0x2500 * volume;
        }
        else if (state->mode == 1) {
            if (state->edge_pending) {
                /* Native exact-boundary event sample uses the new duty
                 * value; four-step phase resumes on the next sample. */
                sample = state->enabled ? volume * (1 << 10) : 0;
                state->edge_pending = 0;
            }
            else if (state->enabled) {
                UINT i;
                for (i = 0; i < 4; i++) {
                    sample += (state->phase & 0x8000) ? 1 : -1;
                    state->phase = (UINT16)(state->phase + state->hz);
                }
                sample *= volume * (1 << (10 - 2));
                if (sample > 32767 || sample < -32768) sample = 0;
            }
        }
        sample = (SINT32)(((int64_t)sample * master_volume) / 100);
        pcm[0] += sample;
        pcm[1] += sample;
        pcm += 2;
    }
}
