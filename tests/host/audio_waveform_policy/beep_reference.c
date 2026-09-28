/* Project-owned ordered common-grid BEEP reference, using actual private source. */
#include <compiler.h>
#include <sound/beep_waveform_policy.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
static void fail(const char *why) { fprintf(stderr,"BEEP WAVEFORM INVALID: %s\n",why); exit(2); }
static void render(BEEP_WAVEFORM_STATE *s,int32_t *pcm,uint64_t *at,uint64_t end,
                   unsigned quantum,int volume,int master,unsigned adaptive) {
    while (*at < end) {
        unsigned n=(unsigned)(end-*at);
        if (quantum && n>quantum) n=quantum;
        beep_waveform_render(s,pcm+2*(*at),n,volume,master,adaptive);
        *at+=n;
    }
}
/* Plan: global frame, epoch, sequence, kind, value. 0 mode, 1 PIT data,
 * 2 quantized phase increment, 3 edge, 4 reset, 8 demand fence, 9 end. */
int main(int argc,char **argv) {
    if (argc!=8) fail("arguments");
    unsigned rate=(unsigned)strtoul(argv[1],0,10),q=(unsigned)strtoul(argv[2],0,10);
    unsigned cuts=(unsigned)strtoul(argv[3],0,10),adaptive=(unsigned)strtoul(argv[4],0,10);
    if ((rate!=44100&&rate!=48000)||q>511||cuts>1||adaptive>1) fail("profile");
    FILE *in=fopen(argv[5],"r"),*out=fopen(argv[6],"wb"),*state=fopen(argv[7],"w");
    if (!in||!out||!state) fail("open");
    int32_t *pcm=calloc(200000u*2u,sizeof(*pcm));if (!pcm) fail("allocation");
    BEEP_WAVEFORM_STATE s;beep_waveform_reset(&s);
    uint64_t at=0,frame,previous=0,seq,expected=0;
    unsigned epoch=1,record_epoch,kind,value,actions=0,ended=0,resets=0;
    while (fscanf(in,"%" SCNu64 " %u %" SCNu64 " %u %u",&frame,&record_epoch,&seq,&kind,&value)==5) {
        if (frame<previous||frame>200000u||actions>=100000u||seq!=expected++||record_epoch!=epoch)
            fail("ordered history/capacity");
        if (kind!=8||cuts) render(&s,pcm,&at,frame,q,1,100,adaptive);
        switch(kind) {
        case 0: if(value>1)fail("mode");beep_waveform_mode(&s,(UINT8)value);break;
        case 1: if(value>65535)fail("data");beep_waveform_data(&s,(UINT16)value);break;
        case 2: if(value>65535)fail("hz");beep_waveform_hz(&s,(UINT16)value);break;
        case 3: if(value>1)fail("edge");beep_waveform_edge(&s,(UINT8)value);break;
        case 4: beep_waveform_reset(&s);epoch++;resets++;break;
        case 8: break;
        case 9: ended=1;break;
        default:fail("kind");
        }
        previous=frame;actions++;if(ended)break;
    }
    if(!ended)fail("missing end");
    for(int c;(c=fgetc(in))!=EOF;)if(c!=' '&&c!='\n'&&c!='\r'&&c!='\t')fail("trailing action");
    if(fwrite(pcm,8,(size_t)at,out)!=(size_t)at)fail("write pcm");
    fprintf(state,"%" PRIu64 " %u %u %u %u %u %u %u %u %u %" PRId64 " %d %u %u\n",
        at,epoch,s.mode,s.enabled,s.have_data,s.edge_pending,s.data,s.hz,s.phase,s.offset_count,
        s.offset_sum,s.offset,actions,resets);
    fclose(in);fclose(out);fclose(state);free(pcm);return 0;
}
