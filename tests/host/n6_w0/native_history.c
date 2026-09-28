/* SPDX-License-Identifier: MIT */
/* Private native OPNA source recorder and serial/delayed replay. No product hook. */
#include <compiler.h>
#include <pccore.h>
#include <sound/fmboard.h>
#include <sound/opntimer.h>
#include <sound/opngen.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <inttypes.h>

#define W0_RECORD_LIMIT 50000u /* host fixture bound; never a product debt limit */
#define W0_FRAME_LIMIT 200000u
#define W0_SCHEMA 1u
#define W0_MAGIC "N6W0A01"
enum { W_RESET=1,W_REGISTER,W_REG_APPLY,W_KEY,W_KEY_APPLY,W_TIMER_A,
 W_STATUS,W_PIC,W_REARM,W_CSM,W_EDGE_OFF,W_EDGE_ON,W_SYNC_ENTER,W_SYNC_EXIT,
 W_GENERATE,W_FRONTIER,W_FINALIZE };
enum { O_CONTROLLED=1,O_CPU_SYNC=2,O_DEMAND=3 };
typedef struct {
 uint64_t seq,parent,time_ns,service_ns,frame,call_id,cpu,last_before,last_after;
 uint32_t kind,epoch,origin,reg,value,sub,requested,actual,remain_before,remain_after,aux;
} WRecord;
static WRecord records[W0_RECORD_LIMIT], consumed[W0_RECORD_LIMIT];
static uint32_t consumed_count;
static uint32_t nrecords, epoch, source_frame, output_frames, source_total, output_total, call_id, csm_sync_index;
static uint64_t next_sequence, csm_parent, initial_hash;
static int recording, replaying, captured_invalid;
static int32_t source_pcm[W0_FRAME_LIMIT*2u], worker_pcm[W0_FRAME_LIMIT*2u];
static _OPNGEN worker;
PCCORE pccore;
OPNA g_opna[OPNA_MAX];
_PCM86 g_pcm86;
#define sound_sync w0_actual_sound_sync
#include "sound/sound.c"
#undef sound_sync
I286CORE i286core;
static void die(const char *what) { fprintf(stderr,"N6-W0 INVALID: %s\n",what);exit(2); }
static void ensure(int yes,const char *why) {if(!yes)die(why);}
static uint64_t hash_bytes(uint64_t h,const void *p,size_t n) {
 const uint8_t *s=p;for(size_t i=0;i<n;i++){h^=s[i];h*=UINT64_C(1099511628211);}return h;
}
static uint64_t hash_u32(uint64_t h,uint32_t x) {
 uint8_t b[4]={(uint8_t)x,(uint8_t)(x>>8),(uint8_t)(x>>16),(uint8_t)(x>>24)};
 return hash_bytes(h,b,4);
}
/* Explicit scalar serialization. Pointer values and padding never enter this hash. */
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
static WRecord *emit(uint32_t kind) {
 if(!recording)return NULL;
 if(nrecords>=W0_RECORD_LIMIT||next_sequence==UINT64_MAX){captured_invalid=1;die("record capacity or sequence overflow");}
 WRecord *r=&records[nrecords++];memset(r,0,sizeof(*r));r->seq=next_sequence++;
 r->kind=kind;r->epoch=epoch;r->time_ns=((uint64_t)CPU_CLOCK*1000000000u)/pccore.realclock;
 r->service_ns=r->time_ns;r->frame=source_frame;r->cpu=CPU_CLOCK;
 r->last_before=r->last_after=soundcfg.lastclock;r->remain_before=r->remain_after=sndstream.remain;
 return r;
}
static void finalize(void) {
 WRecord *r=emit(W_FINALIZE);r->parent=r->seq-1;r->aux=(uint32_t)(r->parent&UINT32_MAX);
}
static void voice(OPNGEN g) {
 opngen_reset(g);opngen_setcfg(g,3,OPN_MONORAL);
 for(unsigned s=0;s<4;s++) {
  unsigned o=s*4+2;opngen_setreg(g,0,0x30+o,1);opngen_setreg(g,0,0x40+o,0x18);
  opngen_setreg(g,0,0x50+o,0x1f);opngen_setreg(g,0,0x60+o,4);
  opngen_setreg(g,0,0x70+o,3);opngen_setreg(g,0,0x80+o,0x0f);
 }
 opngen_setreg(g,0,0xb2,7);opngen_setreg(g,0,0xa6,0x22);
 opngen_setreg(g,0,0xa2,0x69);opngen_keyon(g,2,0xf2);
}
static void init_source(int with_stream) {
 recording=0;memset(&g_opna[0],0,sizeof(g_opna[0]));memset(&g_pcm86,0,sizeof(g_pcm86));
 memset(&i286core,0,sizeof(i286core));memset(&sndstream,0,sizeof(sndstream));
 memset(&soundcfg,0,sizeof(soundcfg));
 pccore.baseclock=2457600;pccore.multiple=20;pccore.realclock=49152000;pccore.cpumode=0;
 soundcfg.rate=44100;voice(&g_opna[0].opngen);g_pcm86.irq=0xff;
 g_opna[0].s.irq=12;g_opna[0].s.reg[0x24]=0xff;g_opna[0].s.reg[0x25]=3;
 g_opna[0].s.reg[0x27]=0x85;
 if(with_stream){
  static int32_t buffer[W0_FRAME_LIMIT*2u];memset(buffer,0,sizeof(buffer));
  sndstream.buffer=buffer;sndstream.ptr=buffer;sndstream.samples=W0_FRAME_LIMIT;
  sndstream.remain=W0_FRAME_LIMIT;sndstream.cbreg=sndstream.cb;
 }
 sound_changeclock();
}
static void init_worker(void) {
 replaying=1;recording=0;memset(&worker,0,sizeof(worker));voice(&worker);replaying=0;
}
void beep_eventreset(void) {}
void soundmng_sync(void) {} /* controlled fixture: transport cannot demand frames */
BOOL pcm86gen_intrq(int arg){(void)arg;return FALSE;}
void pic_setirq(REG8 irq) {
 WRecord *s=emit(W_STATUS);s->value=g_opna[0].s.status;
 WRecord *p=emit(W_PIC);p->value=irq;
}
void nevent_set(NEVENTID id,SINT32 ticks,NEVENTCB cb,NEVENTPOSITION pos) {
 (void)cb;WRecord *r=emit(W_REARM);r->reg=id;r->value=(uint32_t)ticks;r->aux=pos;
}
static void source_gen(unsigned count,uint32_t origin,int direct) {
 ensure(count>0&&count<=W0_FRAME_LIMIT&&source_frame<=W0_FRAME_LIMIT-count&&source_total<=W0_FRAME_LIMIT-count,"source frame bounds");
 WRecord *r=emit(W_GENERATE);r->origin=origin;r->call_id=++call_id;
 r->requested=count;r->actual=count;r->remain_before=sndstream.remain;
 if(direct) {
  memset(source_pcm+source_total*2u,0,count*8u);
  opngen_getpcm(&g_opna[0].opngen,source_pcm+source_total*2u,count);
 } else {
  /* sound.c has already zeroed the mixed buffer before this callback. */
  opngen_getpcm(&g_opna[0].opngen,sndstream.ptr,count);
  memcpy(source_pcm+source_total*2u,sndstream.ptr,count*8u);
 }
 source_frame+=count;source_total+=count;r->remain_after=direct?sndstream.remain:sndstream.remain-count;
 WRecord *front=emit(W_FRONTIER);front->parent=r->seq;front->call_id=r->call_id;front->actual=count;
}
static void source_stream_callback(void *ctx,SINT32 *pcm,UINT count) {
 (void)ctx;
 ensure(pcm==sndstream.ptr,"callback buffer address");
 source_gen(count,O_CPU_SYNC,0);
}
void sound_sync(void) {
 if(replaying)return; /* worker applies the recorded generation plan */
 if(!recording){w0_actual_sound_sync();return;}
 if(csm_parent)++csm_sync_index;
 WRecord *r=emit(W_SYNC_ENTER);r->parent=csm_parent;r->last_before=soundcfg.lastclock;
 uint64_t seq=r->seq;uint32_t before=source_frame;
 w0_actual_sound_sync();
 WRecord *x=emit(W_SYNC_EXIT);x->parent=seq;x->actual=source_frame-before;
 x->last_before=r->last_before;x->last_after=soundcfg.lastclock;
 if(csm_parent&&csm_sync_index==1){WRecord *e=emit(W_EDGE_OFF);e->parent=csm_parent;e->sub=0;e->value=2;}
}
static void source_csm(OPNGEN g) {
 WRecord *r=emit(W_CSM);csm_parent=r->seq;csm_sync_index=0;
 opngen_csm(g);
 ensure(csm_sync_index==2,"CSM requires exactly two native sync calls");
 WRecord *e=emit(W_EDGE_ON);e->parent=csm_parent;e->sub=1;e->value=0xf2;
 csm_parent=0;csm_sync_index=0;
}
#define opngen_csm source_csm
#include "sound/opntimer.c"
#undef opngen_csm
static void source_reset(int with_stream) {
 epoch++;source_frame=0;call_id=0;init_source(with_stream);
 if(with_stream)sound_streamregist(&g_opna[0].opngen,source_stream_callback);
 recording=1;WRecord *r=emit(W_RESET);r->aux=(uint32_t)(fingerprint(&g_opna[0].opngen)&UINT32_MAX);
 finalize();
}
static void at(uint32_t cycles){CPU_CLOCK=cycles;CPU_BASECLOCK=CPU_REMCLOCK=0;}
static void gen(unsigned count) {source_gen(count,O_CONTROLLED,1);finalize();}
static void reg(unsigned address,unsigned value) {
 WRecord *r=emit(W_REGISTER);r->reg=address;r->value=value;
 opngen_setreg(&g_opna[0].opngen,0,address,value);
 WRecord *x=emit(W_REG_APPLY);x->reg=address;x->value=value;finalize();
}
static void key(unsigned value) {
 WRecord *r=emit(W_KEY);r->value=value;opngen_keyon(&g_opna[0].opngen,2,value);
 WRecord *x=emit(W_KEY_APPLY);x->value=value;finalize();
}
static void csm(void) {source_csm(&g_opna[0].opngen);finalize();}
static void timer_a(void){
 WRecord *r=emit(W_TIMER_A);r->value=g_opna[0].s.reg[0x27];
 _NEVENTITEM item={0};item.flag=NEVENT_SETEVENT;item.userData=(INTPTR)&g_opna[0];
 fmport_a(&item);finalize();
}
static void run_case(unsigned which) {
 source_reset(which==7);at(10000);
 switch(which) {
 case 1: gen(300);reg(0xa6,0x2a);reg(0xa2,0x41);gen(1000);break;
 case 2: gen(300);timer_a();gen(1000);break;
 case 3: gen(300);for(unsigned i=0;i<10;i++){at(10000+i*1200);csm();gen(100);}break;
 case 4: gen(300);csm();key(2);gen(1000);break;
 case 5: gen(300);csm();reg(0xa6,0x2a);reg(0xa2,0x41);gen(1000);break;
 case 6: gen(300);csm();gen(300);at(12000);source_reset(0);at(14000);gen(300);csm();gen(1000);break;
 case 7: at(100000);timer_a();gen(1000);break;
 case 8: gen(300);key(2);gen(9700);csm();gen(1000);break;
 case 9: gen(300);key(2);for(unsigned i=0;i<9700;i++)gen(1);csm();gen(1000);break;
 case 10: for(unsigned i=0;i<20;i++){gen(137);if(i%3==0)csm();if(i%5==0)reg(0xa2,0x40+i);}break;
 case 11: for(unsigned i=0;i<20;i++){for(unsigned j=0;j<137;j++)gen(1);if(i%3==0)csm();if(i%5==0)reg(0xa2,0x40+i);}break;
 case 12: for(unsigned i=0;i<17000;i++)gen(1);break; /* must invalidate capture */
 default:die("unknown fixture case");
 }
}
static void u32(FILE *f,uint32_t n){for(int i=0;i<4;i++)if(fputc((n>>(i*8))&255,f)==EOF)die("record write");}
static void u64(FILE *f,uint64_t n){for(int i=0;i<8;i++)if(fputc((n>>(i*8))&255,f)==EOF)die("record write");}
static uint32_t read32(FILE *f){uint32_t n=0;for(int i=0;i<4;i++){int c=fgetc(f);if(c==EOF)die("truncated record");n|=(uint32_t)c<<(i*8);}return n;}
static uint64_t read64(FILE *f){uint64_t n=0;for(int i=0;i<8;i++){int c=fgetc(f);if(c==EOF)die("truncated record");n|=(uint64_t)c<<(i*8);}return n;}
static void write_record(FILE *f,const WRecord *r){
 u64(f,r->seq);u64(f,r->parent);u64(f,r->time_ns);u64(f,r->service_ns);u64(f,r->frame);u64(f,r->call_id);u64(f,r->cpu);u64(f,r->last_before);u64(f,r->last_after);
 u32(f,r->kind);u32(f,r->epoch);u32(f,r->origin);u32(f,r->reg);u32(f,r->value);u32(f,r->sub);u32(f,r->requested);u32(f,r->actual);u32(f,r->remain_before);u32(f,r->remain_after);u32(f,r->aux);
}
static WRecord read_record(FILE *f){WRecord r={0};
 r.seq=read64(f);r.parent=read64(f);r.time_ns=read64(f);r.service_ns=read64(f);r.frame=read64(f);r.call_id=read64(f);r.cpu=read64(f);r.last_before=read64(f);r.last_after=read64(f);
 r.kind=read32(f);r.epoch=read32(f);r.origin=read32(f);r.reg=read32(f);r.value=read32(f);r.sub=read32(f);r.requested=read32(f);r.actual=read32(f);r.remain_before=read32(f);r.remain_after=read32(f);r.aux=read32(f);return r;
}
static void write_plan_records(const char *path,unsigned which,const WRecord *plan,unsigned count){FILE*f=fopen(path,"wb");if(!f)die("open record");
 if(fwrite(W0_MAGIC,1,8,f)!=8)die("header write");
 u32(f,W0_SCHEMA);u32(f,which);u32(f,44100);u32(f,2);u32(f,4);u32(f,2457600);u32(f,20);u32(f,64);u32(f,1);u32(f,4);u32(f,0);u32(f,3);u32(f,0);u64(f,initial_hash);u64(f,count);
 for(unsigned i=0;i<count;i++)write_record(f,&plan[i]);
 if(fclose(f)!=0)die("close record");}
static void write_plan(const char *path,unsigned which){write_plan_records(path,which,records,nrecords);}
static unsigned read_plan(const char *path){FILE*f=fopen(path,"rb");if(!f)die("open replay");char magic[8];if(fread(magic,1,8,f)!=8||memcmp(magic,W0_MAGIC,8))die("record magic");
 if(read32(f)!=W0_SCHEMA)die("unsupported schema version");unsigned which=read32(f);if(which<1||which>11)die("unknown fixture profile");
 if(read32(f)!=44100||read32(f)!=2||read32(f)!=4||read32(f)!=2457600||read32(f)!=20||read32(f)!=64||read32(f)!=1||read32(f)!=4||read32(f)!=0||read32(f)!=3||read32(f)!=0)die("profile metadata");
 initial_hash=read64(f);uint64_t count=read64(f);if(count==0||count>W0_RECORD_LIMIT)die("record capacity");nrecords=(uint32_t)count;
 for(unsigned i=0;i<nrecords;i++)records[i]=read_record(f);
 if(fgetc(f)!=EOF||ferror(f))die("record trailing bytes");fclose(f);return which;
}
static uint64_t source_final_hash;
static void pcm_file(const char *path,const int32_t *pcm,unsigned frames){FILE*f=fopen(path,"wb");if(!f)die("open PCM");for(uint64_t i=0;i<(uint64_t)frames*2u;i++)u32(f,(uint32_t)pcm[i]);if(fclose(f))die("close PCM");}
static void state_file(const char *path,uint64_t hash){FILE*f=fopen(path,"wb");if(!f)die("state file");u64(f,hash);if(fclose(f))die("close state");}
static void validate_plan(void){
 unsigned current_epoch=0;uint64_t frontier=0,previous_time=0,finalized_seq=UINT64_MAX;
 uint64_t previous_call=0,csmpair=0,expect_frontier=0,sync_open=0,sync_start=0;unsigned pending=0,csm_stage=0;
 for(unsigned i=0;i<nrecords;i++){
  const WRecord *r=&records[i];if(r->seq!=i||r->kind<W_RESET||r->kind>W_FINALIZE)die("record sequence/kind");
  if(expect_frontier){if(r->kind!=W_FRONTIER||r->parent!=expect_frontier-1||r->call_id!=previous_call||r->frame!=frontier)die("generation frontier publication");expect_frontier=0;}
  if(r->kind==W_RESET){if(pending||sync_open||csm_stage)die("unfinalized epoch transition");if(r->epoch!=current_epoch+1||r->frame!=0)die("epoch reset");current_epoch=r->epoch;frontier=0;previous_time=0;csmpair=0;}
  else if(r->epoch!=current_epoch)die("cross epoch");
  if(r->time_ns<previous_time)die("retrospective timestamp");previous_time=r->time_ns;
  if(r->kind==W_GENERATE){if(r->frame!=frontier||r->actual==0||r->actual!=r->requested||r->actual>W0_FRAME_LIMIT||frontier>W0_FRAME_LIMIT-r->actual||r->call_id!=previous_call+1)die("generation frontier/call");frontier+=r->actual;previous_call=r->call_id;expect_frontier=r->seq+1;}
  else if(r->kind==W_RESET)previous_call=0;
  else if(r->frame!=frontier)die("retrospective event/frontier");
  if(r->kind==W_CSM){if(csm_stage||sync_open)die("nested/incomplete CSM");csmpair=r->seq;csm_stage=1;}
  if(r->kind==W_SYNC_ENTER){
   if(sync_open)die("nested synchronization");sync_open=r->seq+1;sync_start=frontier;
   if(csmpair){if(csm_stage==1)csm_stage=2;else if(csm_stage==4)csm_stage=5;else die("CSM sync order");}
  }
  if(r->kind==W_SYNC_EXIT){
   if(!sync_open||r->parent!=sync_open-1||r->actual!=frontier-sync_start)die("unmatched synchronization");sync_open=0;
   if(csmpair){if(csm_stage==2)csm_stage=3;else if(csm_stage==5)csm_stage=6;else die("CSM sync completion");}
  }
  if(r->kind==W_EDGE_OFF){if(r->parent!=csmpair||r->sub!=0||csm_stage!=3||sync_open)die("CSM off order");csm_stage=4;}
  if(r->kind==W_EDGE_ON){if(r->parent!=csmpair||r->sub!=1||csm_stage!=6||sync_open)die("CSM on order");csmpair=0;csm_stage=0;}
  if(r->kind==W_FINALIZE){if(csm_stage||sync_open)die("premature finalization");if(!pending||r->parent!=r->seq-1||r->frame!=frontier||r->aux!=(uint32_t)(r->parent&UINT32_MAX))die("premature/incomplete finalization");finalized_seq=r->seq;pending=0;}
  else pending++;
 }
 if(csm_stage||sync_open)die("incomplete CSM or sync");
 if(pending||records[nrecords-1].kind!=W_FINALIZE||finalized_seq!=nrecords-1)die("unfinalized history");
}
static void apply(const WRecord *r){
 static unsigned pending_reg,pending_key;static int have_reg,have_key;
 switch(r->kind){
 case W_RESET:init_worker();ensure((uint32_t)fingerprint(&worker)==r->aux&&fingerprint(&worker)==initial_hash,"initial renderer state");break;
 case W_REGISTER:pending_reg=r->reg;pending_key=r->value;have_reg=1;break;
 case W_REG_APPLY:ensure(have_reg&&pending_reg==r->reg&&pending_key==r->value,"register apply ordering");replaying=1;opngen_setreg(&worker,0,r->reg,r->value);replaying=0;have_reg=0;break;
 case W_KEY:pending_key=r->value;have_key=1;break;
 case W_KEY_APPLY:ensure(have_key&&pending_key==r->value,"key apply ordering");replaying=1;opngen_keyon(&worker,2,r->value);replaying=0;have_key=0;break;
 case W_EDGE_OFF:replaying=1;opngen_keyon(&worker,2,2);replaying=0;break;
 case W_EDGE_ON:replaying=1;opngen_keyon(&worker,2,0xf2);replaying=0;break;
 case W_GENERATE:
  ensure(r->frame==output_frames&&r->actual<=W0_FRAME_LIMIT-output_frames&&r->actual<=W0_FRAME_LIMIT-output_total,"worker render frontier");
  memset(worker_pcm+output_total*2u,0,r->actual*8u);
  opngen_getpcm(&worker,worker_pcm+output_total*2u,r->actual);
  output_frames+=r->actual;output_total+=r->actual;break;
 default:break;
 }
 if(r->kind==W_RESET)output_frames=0; /* epoch-local frontier, total PCM retained */
}
static void replay_plan(const char *mode){
 validate_plan();init_worker();output_frames=output_total=consumed_count=0;
 if(strcmp(mode,"immediate")&&strcmp(mode,"delayed"))die("replay mode");
 /* Delayed placement publishes a complete bounded immutable plan to a
  * separate worker buffer. Clearing the source buffer proves replay has no
  * dependency on source-owned records after publication. */
 WRecord *published=NULL;
 const WRecord *plan=records;
 if(!strcmp(mode,"delayed")){
  published=malloc((size_t)nrecords*sizeof(*published));
  if(!published)die("delayed worker allocation");
  memcpy(published,records,(size_t)nrecords*sizeof(*published));
  memset(records,0,(size_t)nrecords*sizeof(*records));
  plan=published;
 }
 unsigned start=0;
 for(unsigned i=0;i<nrecords;i++)if(plan[i].kind==W_FINALIZE){
  for(unsigned j=start;j<i;j++){apply(&plan[j]);consumed[consumed_count++]=plan[j];}
  consumed[consumed_count++]=plan[i];start=i+1;
 }
 ensure(start==nrecords&&consumed_count==nrecords,"finalization tail");free(published);
}
int main(int argc,char**argv){
 if(argc!=5)die("usage: record CASE PATH PCM | replay MODE PATH PCM");
 opngen_initialize(44100);opngen_setvol(64);
 if(!strcmp(argv[1],"record")){
  unsigned which=(unsigned)strtoul(argv[2],NULL,10);ensure(which>=1&&which<=12,"case");
  nrecords=epoch=source_frame=source_total=call_id=0;next_sequence=0;recording=0;
  init_source(0);initial_hash=fingerprint(&g_opna[0].opngen);
  run_case(which);source_final_hash=fingerprint(&g_opna[0].opngen);
  write_plan(argv[3],which);pcm_file(argv[4],source_pcm,source_total);
  char statepath[4096];snprintf(statepath,sizeof(statepath),"%s.state",argv[4]);state_file(statepath,source_final_hash);
  printf("case=%u records=%u frames=%u state=%016"PRIx64"\n",which,nrecords,source_total,source_final_hash);
 } else if(!strcmp(argv[1],"replay")){
  unsigned which=read_plan(argv[3]);(void)which;replay_plan(argv[2]);
  pcm_file(argv[4],worker_pcm,output_total);
  char historypath[4096];snprintf(historypath,sizeof(historypath),"%s.history",argv[4]);
  write_plan_records(historypath,which,consumed,consumed_count);
  char statepath[4096];snprintf(statepath,sizeof(statepath),"%s.state",argv[4]);state_file(statepath,fingerprint(&worker));
  printf("case=%u mode=%s records=%u frames=%u state=%016"PRIx64"\n",which,argv[2],nrecords,output_total,fingerprint(&worker));
 } else die("mode");
 return captured_invalid?2:0;
}
