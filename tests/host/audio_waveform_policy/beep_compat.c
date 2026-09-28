/* Controlled legacy BEEP replay of the same ordered control events.
 * Legacy mode-0 timestamps are synthetic sample-index units here. */
#include <compiler.h>
#include <pccore.h>
#include <sound/beep.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
NP2CFG np2cfg;
_BEEP g_beep;
BEEPCFG beepcfg;
UINT16 beep_data[BEEPDATACOUNT];
UINT32 beep_time[BEEPDATACOUNT];
typedef struct { uint64_t frame,seq; unsigned epoch,kind,value; } Event;
static Event e[1024];
static int32_t pcm[200000u*2u];
static void fail(const char *why) { fprintf(stderr,"BEEP COMPAT INVALID: %s\n",why);exit(2); }
static void render(_BEEP *b,uint64_t start,uint64_t end,unsigned q) {
    for(uint64_t at=start;at<end;) {
        unsigned n=(unsigned)(end-at);if(q&&n>q)n=q;
        beep_getpcm(b,pcm+2*at,n);at+=n;
    }
}
int main(int argc,char **argv) {
    if(argc!=7)fail("arguments");
    unsigned rate=(unsigned)strtoul(argv[1],0,10),q=(unsigned)strtoul(argv[2],0,10);
    unsigned adaptive=(unsigned)strtoul(argv[3],0,10);
    if((rate!=44100&&rate!=48000)||q>512||adaptive>1)fail("profile");
    FILE *in=fopen(argv[4],"r"),*out=fopen(argv[5],"wb"),*state=fopen(argv[6],"w");
    if(!in||!out||!state)fail("open");
    unsigned count=0;uint64_t f,seq;unsigned ep,k,v;
    while(fscanf(in,"%" SCNu64 " %u %" SCNu64 " %u %u",&f,&ep,&seq,&k,&v)==5) {
        if(count>=1024||f>200000u||seq!=count||(count&&f<e[count-1].frame))fail("history");
        e[count++]=(Event){f,seq,ep,k,v};
        if(k==9)break;
    }
    if(!count||e[count-1].kind!=9)fail("end");
    _BEEP b={0};beepcfg.rate=rate;beepcfg.vol=1;np2cfg.vol_master=100;np2cfg.nbeepofs=adaptive;
    uint64_t at=0;unsigned i=0,resets=0;
    while(i<count) {
        /* Apply controls exactly at this frontier before its next sample. */
        while(i<count&&e[i].frame==at&&(e[i].kind==0||e[i].kind==2||e[i].kind==4)) {
            if(e[i].kind==0){b.mode=(UINT8)e[i].value;b.events=0;b.lastenable=0;}
            if(e[i].kind==2)b.hz=(UINT16)e[i].value;
            if(e[i].kind==4){memset(&b,0,sizeof(b));resets++;}
            i++;
        }
        unsigned j=i;uint64_t end=e[count-1].frame;
        for(unsigned z=i;z<count;z++)if(e[z].kind==0||e[z].kind==2||e[z].kind==4||e[z].kind==9){end=e[z].frame;break;}
        if(end<at)fail("frontier");
        if(b.mode==0) {
            unsigned n=0;
            for(;j<count&&e[j].frame<end;j++) {
                if(e[j].kind!=1)fail("mode0 event");
                if(n>=BEEPDATACOUNT-1)fail("data capacity");
                beep_time[n]=(UINT32)(e[j].frame-at);beep_data[n]=(UINT16)e[j].value;n++;
            }
            if(n){beep_time[n]=(UINT32)(end-at);beep_data[n]=beep_data[n-1];
                b.beep_data_curr_loc=0;b.beep_data_load_loc=n+1;b.events=1;}
            if(q==512) {
                uint64_t cursor=at;
                for(unsigned z=i;z<j;z++)if(e[z].frame>cursor){render(&b,cursor,e[z].frame,0);cursor=e[z].frame;}
                render(&b,cursor,end,0);
            } else render(&b,at,end,q);
        } else if(b.mode==1) {
            unsigned n=0;uint64_t prior=at;
            for(;j<count&&e[j].frame<end;j++) {
                if(e[j].kind!=3||n>=BEEPEVENT_MAX)fail("mode1 event");
                b.event[n].clock=(UINT32)((e[j].frame-prior)<<16);
                b.event[n].enable=(int)e[j].value;prior=e[j].frame;n++;
            }
            b.events=n;
            if(q==512) {
                uint64_t cursor=at;
                for(unsigned z=i;z<j;z++)if(e[z].frame>cursor){render(&b,cursor,e[z].frame,0);cursor=e[z].frame;}
                render(&b,cursor,end,0);
            } else render(&b,at,end,q);
        } else fail("mode");
        at=end;i=j;
        if(i<count&&e[i].kind==9)break;
        if(i<count&&e[i].frame==at&&e[i].kind!=0&&e[i].kind!=2&&e[i].kind!=4)fail("stalled");
    }
    if(fwrite(pcm,8,(size_t)at,out)!=(size_t)at)fail("write");
    fprintf(state,"%" PRIu64 " %u %u %u %d %u %u %u\n",at,b.mode,b.cnt,b.hz,b.lastenable,
            b.beep_data_curr_loc,b.events,resets);
    fclose(in);fclose(out);fclose(state);return 0;
}
