/* Project-owned machine-time action-plan executor using the actual native FM renderer. */
#include <compiler.h>
#include <sound/opngen.h>
#include <cpucore.h>
#include <pccore.h>
#include <sound/opngen_waveform_policy.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

/* Native register/key methods normally synchronize the legacy stream first.
 * The reference planner has already generated the old prefix to the frontier. */
#if defined(CPUCORE_IA32)
I386CORE i386core;
#else
I286CORE i286core;
#endif
PCCORE pccore;
void sound_sync(void) {}

static uint64_t hash_bytes(uint64_t h,const void *p,size_t n) {
 const uint8_t *s=p;for(size_t i=0;i<n;i++){h^=s[i];h*=UINT64_C(1099511628211);}return h;
}
static uint64_t hash_u32(uint64_t h,uint32_t x) {
 uint8_t b[4]={(uint8_t)x,(uint8_t)(x>>8),(uint8_t)(x>>16),(uint8_t)(x>>24)};
 return hash_bytes(h,b,4);
}
/* W0's scalar renderer fingerprint. No pointer identity or struct padding. */
static uint64_t fingerprint(const _OPNGEN *g) {
 uint64_t h=UINT64_C(14695981039346656037);
#define H(x) h=hash_u32(h,(uint32_t)(x))
 H(g->playchannels);H(g->playing);H(g->feedback2);H(g->feedback3);H(g->feedback4);
 H(g->outdl);H(g->outdc);H(g->outdr);H(g->calcremain);
 for(unsigned i=0;i<OPNCH_MAX;i++) {
  const OPNCH *c=&g->opnch[i];H(c->algorithm);H(c->feedback);H(c->playing);
  H(c->outslot);H(c->op1fb);H(c->pan);H(c->extop);H(c->stereo);
  for(unsigned j=0;j<4;j++){H(c->keynote[j]);H(c->keyfunc[j]);H(c->kcode[j]);}
  for(unsigned j=0;j<4;j++) {
   const OPNSLOT *s=&c->slot[j];H(s->totallevel);H(s->decaylevel);
   H(s->freq_cnt);H(s->freq_inc);H(s->multiple);H(s->keyscalerate);
   H(s->env_mode);H(s->envratio);H(s->ssgeg1);H(s->env_cnt);H(s->env_end);
   H(s->env_inc);H(s->env_inc_attack);H(s->env_inc_decay1);
   H(s->env_inc_decay2);H(s->env_inc_release);
   for(unsigned k=0;k<32;k++)H(s->detune1[k]);
  }
 }
#undef H
 return h;
}
static void voice(OPNGEN g,unsigned channel,unsigned algorithm,unsigned feedback) {
 unsigned chbase=channel<3?0:3,local=channel%3;
 for(unsigned s=0;s<4;s++) {
  unsigned o=s*4+local;
  opngen_setreg(g,chbase,0x30+o,1);
  opngen_setreg(g,chbase,0x40+o,0x18);
  opngen_setreg(g,chbase,0x50+o,0x1f);
  opngen_setreg(g,chbase,0x60+o,4);
  opngen_setreg(g,chbase,0x70+o,3);
  opngen_setreg(g,chbase,0x80+o,0x0f);
 }
 opngen_setreg(g,chbase,0xb0+local,((feedback&7)<<3)|(algorithm&7));
 opngen_setreg(g,chbase,0xb4+local,0xc0);
 opngen_setreg(g,chbase,0xa4+local,0x22);
 opngen_setreg(g,chbase,0xa0+local,0x69);
}
static void fail(const char *what){fprintf(stderr,"AUDIO WAVEFORM INVALID: %s\n",what);exit(2);}
static void generate(OPNGEN g,FILE*out,uint64_t *at,uint64_t end,
                     unsigned quantum,int continuous,int vr,int32_t *pcm,unsigned cpu_mode) {
 if(end<*at || end>200000u)fail("frame bounds");
 while(*at<end) {
  unsigned n=(unsigned)(end-*at);if(quantum && n>quantum)n=quantum;
  memset(pcm+(*at)*2u,0,(size_t)n*8u);
  /* CPU coordinate deliberately varied but never used as waveform authority. */
  CPU_CLOCK=(UINT32)((uint64_t)cpu_mode*(*at+1u)*17u);
  if(vr){if(continuous)opngen_getpcmvr_continuous(g,pcm+(*at)*2u,n);
         else opngen_getpcmvr(g,pcm+(*at)*2u,n);}
  else {if(continuous)opngen_getpcm_continuous(g,pcm+(*at)*2u,n);
        else opngen_getpcm(g,pcm+(*at)*2u,n);}
  *at+=n;
 }
 (void)out;
}
/* Plan fields: global_frame, kind, a, b, c. Kind 8 is a legacy demand
 * fence; it is intentionally ignored by the event-bounded policy. */
int main(int argc,char **argv) {
 if(argc!=10)fail("arguments: rate profile quantum respect_cuts vr cpu_mode plan pcm state");
 unsigned rate=(unsigned)strtoul(argv[1],0,10),continuous=(unsigned)strtoul(argv[2],0,10);
 unsigned quantum=(unsigned)strtoul(argv[3],0,10),cuts=(unsigned)strtoul(argv[4],0,10);
 unsigned vr=(unsigned)strtoul(argv[5],0,10),cpu=(unsigned)strtoul(argv[6],0,10);
 if((rate!=44100&&rate!=48000)||continuous>1||vr>1||cuts>1||quantum>511)fail("profile");
 FILE*in=fopen(argv[7],"r"),*out=fopen(argv[8],"wb"),*state=fopen(argv[9],"w");
 if(!in||!out||!state)fail("open");
 int32_t *pcm=calloc(200000u*2u,sizeof(int32_t));if(!pcm)fail("allocation");
 pccore.baseclock=2457600;pccore.multiple=cpu?cpu:1;pccore.realclock=pccore.baseclock*pccore.multiple;
 opngen_initialize(rate);opngen_setvol(64);
 _OPNGEN g;opngen_reset(&g);opngen_setcfg(&g,6,OPN_STEREO|0x3f);
 uint64_t at=0,frame,previous_frame=0,csm_frontier=0;unsigned kind,a,b,c,actions=0,pending_csm=0;int ended=0;
 while(fscanf(in,"%" SCNu64 " %u %u %u %u",&frame,&kind,&a,&b,&c)==5) {
  if(frame<at || frame<previous_frame || frame>200000u || actions>=100000u)fail("ordered frame/action capacity");
  previous_frame=frame;
  if(pending_csm) {
   if(frame!=csm_frontier || kind!=1 || a!=2 ||
      (pending_csm==1?b!=2:b!=0xf2))fail("CSM off/on application sequence");
   pending_csm=pending_csm==1?2:0;
  }
  if(kind!=7 && (kind!=8||cuts))generate(&g,out,&at,frame,quantum,continuous,vr,pcm,cpu);
  switch(kind) {
  case 0: if(a>3||b>255||c>255)fail("register");opngen_setreg(&g,a,b,(REG8)c);break;
  case 1: if(a>=6||b>255)fail("key");opngen_keyon(&g,a,(REG8)b);break;
  case 2: opngen_csm(&g);break;
  case 3: g.opnch[2].extop=(UINT8)(a&0xc0);break;
  case 4: opngen_reset(&g);opngen_setcfg(&g,6,OPN_STEREO|0x3f);break;
  case 5: if(a>=6||b>7||c>7)fail("voice");voice(&g,a,b,c);break;
  case 6: if(a>=6||b>255)fail("pan");opngen_setreg(&g,a<3?0:3,0xb4+(a%3),(REG8)b);break;
  case 7: pending_csm=1;csm_frontier=frame;break; /* CSM accepted before old-prefix generation. */
  case 8: break; /* demand-only call fence */
  case 9: ended=1;break;
  default: fail("event kind");
  }
  actions++;if(ended)break;
 }
 if(!ended || pending_csm)fail("missing end or incomplete CSM");
 for(int tail;(tail=fgetc(in))!=EOF;)
  if(tail!=' ' && tail!='\n' && tail!='\r' && tail!='\t')fail("trailing action after end");
 if(fwrite(pcm,8,(size_t)at,out)!=(size_t)at)fail("write pcm");
 fprintf(state,"%016" PRIx64 " %" PRIu64 " %u\n",fingerprint(&g),at,actions);
 fclose(in);fclose(out);fclose(state);free(pcm);return 0;
}
