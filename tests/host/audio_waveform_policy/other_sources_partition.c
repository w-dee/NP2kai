/* Source-scope probe: actual PSG or rhythm renderer with owned PCM assets. */
#include <compiler.h>
#include <sound/psggen.h>
#include <sound/rhythm.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
void sound_sync(void) {}
static SINT16 rhythm_sample[111];
static void render_psg(PSGGEN p,int32_t *pcm,unsigned start,unsigned n,unsigned q) {
 for(unsigned done=0;done<n;){unsigned count=q?q:n-done;if(count>n-done)count=n-done;
  psggen_getpcm(p,pcm+2*(start+done),count);done+=count;}
}
static void render_rhythm(RHYTHM r,int32_t *pcm,unsigned start,unsigned n,unsigned q) {
 for(unsigned done=0;done<n;){unsigned count=q?q:n-done;if(count>n-done)count=n-done;
  pcmmix_getpcm((PCMMIX)r,pcm+2*(start+done),count);done+=count;}
}
int main(int argc,char **argv) {
 if(argc!=6)return 2;unsigned rate=(unsigned)strtoul(argv[1],0,10),source=(unsigned)strtoul(argv[2],0,10);
 unsigned q=(unsigned)strtoul(argv[3],0,10);
 FILE*out=fopen(argv[4],"wb"),*state=fopen(argv[5],"w");
 if(!out||!state||(rate!=44100&&rate!=48000)||source>1||q>511)return 2;
 int32_t pcm[1600]={0};
 if(source==0){
  _PSGGEN p;psggen_initialize(rate);psggen_setvol(64);psggen_reset(&p);
  psggen_setreg(&p,0,0x35);psggen_setreg(&p,1,0x00);
  psggen_setreg(&p,6,3);psggen_setreg(&p,7,0x36);
  psggen_setreg(&p,8,0x0f);psggen_setreg(&p,11,7);psggen_setreg(&p,12,0);
  psggen_setreg(&p,13,0x0e);
  render_psg(&p,pcm,0,239,q);
  psggen_setreg(&p,8,0x10);psggen_setreg(&p,7,0x3f);
  render_psg(&p,pcm,239,311,q);
  psggen_setreg(&p,7,0x36);psggen_setreg(&p,13,0x0b);
  render_psg(&p,pcm,550,250,q);
  fprintf(state,"%u %u %u %u %d %u %u %u\n",p.mixer,p.puchicount,p.envcnt,p.envmode,p.tone[0].count,p.tone[0].puchi,p.noise.lfsr,p.noise.count);
 }else{
  _RHYTHM r;rhythm_initialize(rate);rhythm_setvol(64);rhythm_reset(&r);
  r.hdr.enable=0x3f;
  for(unsigned i=0;i<111;i++)rhythm_sample[i]=(SINT16)((int)((i*913u)%5000u)-2500);
  r.trk[0].data.sample=rhythm_sample;r.trk[0].data.samples=111;
  rhythm_setreg(&r,0x18,0xc0);rhythm_setreg(&r,0x10,1);
  render_rhythm(&r,pcm,0,239,q);
  rhythm_setreg(&r,0x10,1);render_rhythm(&r,pcm,239,311,q);
  rhythm_setreg(&r,0x10,0x81);render_rhythm(&r,pcm,550,250,q);
  fprintf(state,"%u %u %td %d %u\n",r.hdr.playing,r.trk[0].remain,r.trk[0].pcm-rhythm_sample,r.trk[0].volume,r.trk[0].flag);
 }
 if(fwrite(pcm,8,800,out)!=800)return 2;fclose(out);fclose(state);return 0;
}
