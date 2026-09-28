/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <io/iocore.h>
#include <keystat.h>
#include <commng.h>
#include <tier1_machine.h>
#include <mouse_machine.h>
#include <opna_timer_machine.h>
#include <gdc_machine.h>
#include <assert.h>
#include <stdio.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#if defined(CPUCORE_IA32)
I386CORE i386core;
void CPUCALL ia32_interrupt(int v,int soft){(void)v;(void)soft;}
#else
I286CORE i286core;
void CPUCALL i286c_interrupt(REG8 v){(void)v;}
#endif
PCCORE pccore;PCSTAT pcstat;NP2CFG np2cfg;
_PIC pic;_PIT pit;_GDC gdc;_FDC fdc;_DMAC dmac;_KEYBRD keybrd;
UINT32 SDL_GetTicks(void){assert(!"repeat host clock must not be used");return 0;}
/* The actual keystat implementation is linked; no key-state substitute. */
void softkbd_led(REG8 v){(void)v;}
void joymng_setflags(UINT8 v){(void)v;}
#include "pic-body.inc"
#include "serial-body.inc"
static int fdc_seeksndtimeout[4],fdc_lasttreg[4];
#define FDC_INT_DELAY 6
#define FDC_SEEKSOUND_TIMEOUT 60
BOOL fdd_diskready(REG8 d){(void)d;return 1;}
void fddmtrsnd_play(UINT n,BOOL p){(void)n;(void)p;}
#include "fdc-body.inc"
#include "gdc_sub-body.inc"
/* Endpoints only are substituted. The actual DMA loop is unmodified. */
static UINT8 bytes[64];static unsigned trace[128],tracen;
static UINT8 memread(UINT32 a){trace[tracen++]=0x300+a;return bytes[a];}
static void memwrite(UINT32 a,REG8 b){trace[tracen++]=0x400+a;bytes[a]=b;}
#undef MEMP_READ8
#undef MEMP_WRITE8
#define MEMP_READ8(a) memread(a)
#define MEMP_WRITE8(a,b) memwrite(a,b)
#include "dmax86-body.inc"
static REG8 DMACCALL endpoint(void){trace[tracen++]=0x100;return 0x5a;}
static void DMACCALL output(REG8 v){trace[tracen++]=0x500+v;}
static REG8 DMACCALL end(REG8 f){assert(f==DMAEXT_END);trace[tracen++]=0x200;return 0;}
static void fresh(unsigned base,unsigned multiple)
{
 memset(&pccore,0,sizeof(pccore));memset(&np2cfg,0,sizeof(np2cfg));memset(&fdc,0,sizeof(fdc));memset(&gdc,0,sizeof(gdc));memset(&dmac,0,sizeof(dmac));
 pccore.baseclock=base;pccore.multiple=multiple;pccore.realclock=base*multiple;pccore.cpumode=base==1996800?CPUMODE_8MHZ:0;
 CPU_CLOCK=0;CPU_BASECLOCK=CPU_REMCLOCK=100000;CPU_FLAG=0;
 tier1_fake_now=0;assert(tier1_start(0,base));nevent_allreset();pic_reset(&np2cfg);keyboard_reset(&np2cfg);memset(&keyctrl,0,sizeof(keyctrl));keyctrl.keyrep=0x21;keyctrl.capsref=keyctrl.kanaref=NKEYREF_NC;memset(&keystat,0,sizeof(keystat));memset(keystat.ref,NKEYREF_NC,sizeof(keystat.ref));keystat_tblreset();keystat_ctrlreset();keyboard_changeclock();fdc.chgreg=3;
 tracen=0;memset(bytes,0,sizeof(bytes));
}
static void at(uint64_t q){tier1_fake_now=q;assert(tier1_settle(q));}
static void edge(uint64_t q,uint64_t seq,unsigned source,unsigned key,unsigned down)
{TIER1_EDGE e={q,seq,source,key,down};assert(tier1_admit(e));}
static void dma(void)
{
 dmac.working=4;DMACH c=dmac.dmach+2;c->mode=4;c->adrs.d=0;c->leng.w=3;
 c->proc.inproc=endpoint;c->proc.outproc=output;c->proc.extproc=end;
 _DMAC before=dmac;at(TIER1_HZ);assert(!memcmp(&dmac,&before,sizeof(dmac)));
 for(unsigned i=0;i<4;i++){dmax86();assert(c->adrs.d==i+1&&bytes[i]==0x5a);for(unsigned future=i+1;future<4;future++)assert(bytes[future]==0);}
 assert(!dmac.working&&c->leng.w==65535&&(dmac.stat&4));
 assert(tracen==9&&trace[6]==0x200&&trace[7]==0x100&&trace[8]==0x403);
 /* Each channel is visited in order, one opportunity each; decrement mode. */
 tracen=0;dmac.working=3;
 for(unsigned i=0;i<2;i++){c=dmac.dmach+i;c->adrs.d=8+i;c->mode=0x24;c->leng.w=0;c->proc.inproc=endpoint;c->proc.extproc=end;}
 dmax86();assert(tracen==6&&trace[2]==0x408&&trace[5]==0x409);assert(dmac.dmach[0].adrs.d==7&&dmac.dmach[1].adrs.d==8);
}
static void rejection(void)
{
 TIER1_MACHINE old=tier1_machine;_KEYBRD k=keybrd;_PIC p=pic;_FDC f=fdc;_GDC g=gdc;
 assert(!tier1_settle(TIER1_LIMIT+1));assert(!tier1_settle(tier1_machine.frontier-1));
 assert(!memcmp(&old,&tier1_machine,sizeof(old))&&!memcmp(&k,&keybrd,sizeof(k))&&!memcmp(&p,&pic,sizeof(p))&&!memcmp(&f,&fdc,sizeof(f))&&!memcmp(&g,&gdc,sizeof(g)));
 TIER1_EDGE bad={tier1_machine.frontier,900,1,1,1};assert(!tier1_admit(bad));assert(!memcmp(&old,&tier1_machine,sizeof(old)));
}
#include "expected-durations.inc"
static TIER1_MACHINE rejected_state;static _KEYBRD rejected_key;static _PIC rejected_pic;static _GDC rejected_gdc;
static void reject_signal(int sig)
{
 (void)sig;_exit(memcmp(&rejected_state,&tier1_machine,sizeof(tier1_machine)) || memcmp(&rejected_key,&keybrd,sizeof(keybrd)) || memcmp(&rejected_pic,&pic,sizeof(pic)) || memcmp(&rejected_gdc,&gdc,sizeof(gdc)));
}
static void io_rejection(unsigned mode)
{
 pid_t pid=fork();assert(pid>=0);
 if(!pid){
  rejected_state=tier1_machine;rejected_key=keybrd;rejected_pic=pic;rejected_gdc=gdc;
  signal(SIGABRT,reject_signal);
  if(mode==0){tier1_fake_now=TIER1_LIMIT+1;keyboard_i41(0x41);}
  if(mode==1){np2cfg.keyrepeat_enable=1;keyboard_o43(0x43,0);}
  if(mode==2){tier1_fake_now=TIER1_LIMIT;calc_gdcslavewait(1);}
  _exit(2);
 }
 int status;assert(waitpid(pid,&status,0)==pid);assert(WIFEXITED(status)&&WEXITSTATUS(status)==0);
}
int main(void)
{
 for(unsigned b=0;b<2;b++)for(unsigned m=1;m<=20;m+=(m==1?3:m==4?1:15)) {
  unsigned base=b?1996800:2457600;uint64_t delay=512*(TIER1_HZ/base),duration;
  fresh(base,m);dma();
  for(unsigned r=0;r<NELEMENTS(expected_durations);r++)if(expected_durations[r].base==base){
   fresh(base,m);calc_gdcslavewait(expected_durations[r].dots);assert(tier1_machine.busy_due==expected_durations[r].q);
  }
  for(unsigned cmd=0;cmd<2;cmd++){
   fresh(base,m);fdc.event=FDCEVENT_CMDRECV;fdc.equip=1;fdc.cmds[0]=0;fdc.cmds[1]=2;
   if(cmd)FDC_Seek();else FDC_Recalibrate();
   assert(fdc.int_timer[0]==6&&tier1_machine.seek_due[0]==6*TIER1_FRAME);
   fdc_intdelay();assert(fdc.int_timer[0]==6); /* exec cadence cannot advance it */
   at(6*TIER1_FRAME-1);assert(!fdc.intreq);at(6*TIER1_FRAME+delay);assert(fdc.intreq&&(fdc.stat[0]&FDCRLT_SE));
  }
  fresh(base,m);fdc_interrupt();assert(!nevent_iswork(NEVENT_FDCINT));at(delay-1);assert(!fdc.intreq);at(delay);assert(fdc.intreq&&(pic.pi[1].irr&8));
  fresh(base,m);fdc_interrupt();tier1_fake_now=delay/2;fdc_interrupt();at(delay);assert(!fdc.intreq);at(delay+delay/2);assert(fdc.intreq);
  fresh(base,m);fdc_interrupt();tier1_fdc_reset();at(delay);assert(!fdc.intreq);
  fresh(base,m);fdc.int_stat[0]=0x20;tier1_fdc_seek(0,6);at(6*TIER1_FRAME-1);assert(fdc.int_timer[0]==1&&!fdc.intreq);at(6*TIER1_FRAME);assert(!fdc.int_timer[0]&&fdc.stat[0]==0x20&&!fdc.intreq);at(6*TIER1_FRAME+delay);assert(fdc.intreq);
  fresh(base,m);assert(tier1_gdc_duration(137,&duration));calc_gdcslavewait(137);assert(tier1_machine.busy_due==duration&&!nevent_iswork(NEVENT_GDCSLAVE));at(duration-1);assert(gdc.s_drawing==8);at(duration);assert(!gdc.s_drawing);
  fresh(base,m);calc_gdcslavewait(137);at(duration/2);calc_gdcslavewait(137);assert(tier1_machine.busy_due==2*duration);at(2*duration);assert(!gdc.s_drawing);rejection();
  fresh(base,m);gdcsub_setslavewait(512);assert(tier1_machine.busy_due==delay);
  fresh(base,m);edge(0,1,1,0x20,1);edge(TIER1_KEY_PERIOD,2,1,0x20,0);at(TIER1_KEY_PERIOD);assert(keybrd.data==0x20&&keybrd.buffers==1&&(pic.pi[0].irr&2));assert(keyboard_i41(0x41)==0x20);at(2*TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0xa0);
  /* Edge exactly at an existing deadline joins before control-priority transfer. */
  fresh(base,m);keyboard_ctrl(0xfa);edge(TIER1_KEY_PERIOD,1,1,0x21,1);at(TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0xfa);at(2*TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0x21);
  /* Ownership: duplicate down and two producers do not cause duplicate bytes. */
  fresh(base,m);edge(0,1,1,0x22,1);edge(0,2,1,0x22,1);edge(0,3,2,0x22,1);edge(1,4,1,0x22,0);edge(2,5,2,0x22,0);at(TIER1_KEY_PERIOD);assert(keybrd.buffers==1&&keyboard_i41(0x41)==0x22);at(2*TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0xa2);
  /* Reset at T settles old epoch before clearing and resending held keys. */
  fresh(base,m);edge(0,1,1,0x23,1);tier1_fake_now=TIER1_KEY_PERIOD;keyboard_resetsignal();assert(tier1_machine.key_expiries==1&&tier1_machine.epoch==1&&keybrd.buffers==1&&!(keybrd.status&2));at(2*TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0x23);
 }
 /* Partition equivalence includes full-register retries, seeks and busy. */
 TIER1_MACHINE expected;_KEYBRD kexpected;_FDC fexpected;_PIC pexpected;
 for(unsigned span=0;span<2;span++)for(unsigned plan=0;plan<2;plan++){
  fresh(2457600,4);edge(0,1,1,0x25,1);edge(TIER1_KEY_PERIOD,2,1,0x25,0);tier1_fdc_seek(0,6);calc_gdcslavewait(1000);
  uint64_t total=span ? TIER1_LIMIT : TIER1_HZ;
  if(plan)for(unsigned i=1;i<=137;i++)at((total/137)*i+(total%137)*i/137);else at(total);
  if(!plan){expected=tier1_machine;kexpected=keybrd;fexpected=fdc;pexpected=pic;}
  else {assert(!memcmp(&expected,&tier1_machine,sizeof(expected)));assert(!memcmp(&kexpected,&keybrd,sizeof(keybrd)));assert(!memcmp(&fexpected,&fdc,sizeof(fdc)));assert(!memcmp(&pexpected,&pic,sizeof(pic)));}
 }
 fresh(2457600,4);
 TIER1_MACHINE pristine=tier1_machine;assert(!tier1_start(TIER1_LIMIT+1,2457600));assert(!tier1_start(0,1));assert(!memcmp(&pristine,&tier1_machine,sizeof(pristine)));
 for(unsigned bad=0;bad<4;bad++){TIER1_EDGE x={1,1,1,1,1};if(bad==0)x.source=0;if(bad==1)x.key=TIER1_KEYS;if(bad==2)x.down=2;if(bad==3)x.q=TIER1_LIMIT+1;assert(!tier1_admit(x));assert(!memcmp(&pristine,&tier1_machine,sizeof(pristine)));}
 for(unsigned i=0;i<TIER1_INPUT_CAPACITY;i++)edge(1,i+1,1,1,1);
 TIER1_MACHINE before=tier1_machine;TIER1_EDGE e={1,999,1,1,1};assert(!tier1_admit(e)&&!memcmp(&before,&tier1_machine,sizeof(before)));
 keybrd.buffers=1;assert(!tier1_settle(1)&&!memcmp(&before,&tier1_machine,sizeof(before)));assert(keybrd.buffers==1);
 fresh(2457600,4);keyboard_o43(0x43,1);keyboard_o41(0x41,0x9c);at(TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0xfa);
 fresh(2457600,4);edge(0,1,1,0x24,1);edge(3*TIER1_KEY_PERIOD,2,1,0x24,0);keyboard_o43(0x43,8);
 tier1_fake_now=TIER1_KEY_PERIOD;keyboard_o43(0x43,0);assert(tier1_machine.epoch==1&&tier1_machine.count==1);at(2*TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0x24);at(3*TIER1_KEY_PERIOD);assert(keyboard_i41(0x41)==0xa4);
 for(unsigned mode=0;mode<3;mode++){fresh(2457600,4);io_rejection(mode);}
 puts("PASS_TIER1_DMA_FDC_GDC_KEYBOARD_REAL_BODIES_BOTH_BASES_M1_M4_M5_M20");return 0;
}
