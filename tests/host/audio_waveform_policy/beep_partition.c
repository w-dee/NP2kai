/* Diagnostic only: actual native BEEP generator, no new BEEP semantics. */
#include <compiler.h>
#include <pccore.h>
#include <sound/beep.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
NP2CFG np2cfg;
_BEEP g_beep;
BEEPCFG beepcfg;
UINT16 beep_data[BEEPDATACOUNT];
UINT32 beep_time[BEEPDATACOUNT];
int main(int argc,char **argv) {
 if(argc!=6)return 2;
 unsigned rate=(unsigned)strtoul(argv[1],0,10),mode=(unsigned)strtoul(argv[2],0,10);
 unsigned quantum=(unsigned)strtoul(argv[3],0,10);
 if((rate!=44100&&rate!=48000)||mode>1||quantum>511)return 2;
 FILE *pcmfile=fopen(argv[4],"wb"),*state=fopen(argv[5],"w");if(!pcmfile||!state)return 2;
 int32_t pcm[128*2]={0}; _BEEP b={0};
 np2cfg.vol_master=100;np2cfg.nbeepofs=0;beepcfg.vol=1;beepcfg.rate=rate;b.mode=(UINT8)mode;
 if(mode==0){
  b.events=1;b.beep_data_curr_loc=0;b.beep_data_load_loc=4;
  beep_time[0]=0;beep_time[1]=12;beep_time[2]=43;beep_time[3]=89;
  beep_data[0]=0;beep_data[1]=255;beep_data[2]=24;beep_data[3]=180;
 }else{
  b.events=2;b.event[0].clock=2u<<16;b.event[0].enable=1;
  b.event[1].clock=3u<<16;b.event[1].enable=0;b.hz=5000;
 }
 for(unsigned pos=0;pos<128;){unsigned n=quantum?quantum:128;
  if(n>128-pos)n=128-pos;beep_getpcm(&b,pcm+pos*2,n);pos+=n;}
 if(fwrite(pcm,8,128,pcmfile)!=128)return 2;
 fprintf(state,"%u %u %u %d %u\n",b.cnt,b.beep_data_curr_loc,b.events,b.lastenable,b.mode);
 fclose(pcmfile);fclose(state);return 0;
}
