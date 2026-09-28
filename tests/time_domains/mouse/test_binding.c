/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <io/iocore.h>
#include <mousemng.h>
#include <opna_timer_machine.h>
#include <gdc_machine.h>
#include <mouse_machine.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#if defined(CPUCORE_IA32)
I386CORE i386core;
void CPUCALL ia32_interrupt(int v,int soft);
#else
I286CORE i286core;
void CPUCALL i286c_interrupt(REG8 v);
#endif
PCCORE pccore;
PCSTAT pcstat;
NP2CFG np2cfg;
_MOUSEIF mouseif;
_PIC pic;
_PIT pit;
_GDC gdc;
static unsigned dispatches,vector;
#if defined(CPUCORE_IA32)
void CPUCALL ia32_interrupt(int v,int soft){dispatches++;vector=v;(void)soft;}
#else
void CPUCALL i286c_interrupt(REG8 v){dispatches++;vector=v;}
#endif
REG8 keystat_getmouse(SINT16 *x,SINT16 *y){(void)x;(void)y;return 0xff;}
#include "pic-body.inc"
#include "mouseif-body.inc"
static void fresh(unsigned base,unsigned mult)
{
 memset(&np2cfg,0,sizeof(np2cfg));memset(&pccore,0,sizeof(pccore));
 pccore.baseclock=base;pccore.multiple=mult;pccore.realclock=base*mult;
 CPU_CLOCK=0;CPU_BASECLOCK=CPU_REMCLOCK=100000;CPU_FLAG=0;
 mouse_machine_ready=0;mouse_fake_now=0;mouseif_absflag=0;mouseif_limitcounter=0;
 nevent_allreset();pic_reset(&np2cfg);mouseif_reset(&np2cfg);
 dispatches=vector=0;
}
static void input(uint64_t t,uint64_t seq,int x,int y,unsigned buttons)
{ MOUSE_INPUT r;memset(&r,0,sizeof(r));r.q=t;r.sequence=seq;r.x=x;r.y=y;r.buttons=buttons;assert(mouse_time_admit(&mouse_machine,r)); }
static void at(uint64_t q){mouse_fake_now=q;mouse_machine_service();}
static MOUSE_TIME saved_time;
static _MOUSEIF saved_mouse;
static _PIC saved_pic;
static void rejected(int sig)
{
 (void)sig;
 _exit(memcmp(&saved_time,&mouse_machine,sizeof(saved_time)) ||
       memcmp(&saved_mouse,&mouseif,sizeof(saved_mouse)) ||
       memcmp(&saved_pic,&pic,sizeof(saved_pic)) ? 1 : 0);
}
static void reject_without_mutation(unsigned kind)
{
 pid_t child=fork();assert(child>=0);
 if(child==0) {
  if(kind==0)mouse_fake_now=MOUSE_TIME_LIMIT_Q+1;
  if(kind==1)np2cfg.KEY_MODE=3;
  if(kind==3)np2cfg.MOUSERAPID=1;
  if(kind==4){mouse_machine_ready=0;mouse_fake_now=MOUSE_TIME_LIMIT_Q+1;}
  saved_time=mouse_machine;saved_mouse=mouseif;saved_pic=pic;
  signal(SIGABRT,rejected);
  if(kind==2||kind==4)mouseif_reset(&np2cfg);
  else mouseif_i7fd9(0x7fd9);
  _exit(2);
 }
 int status;assert(waitpid(child,&status,0)==child);
 assert(WIFEXITED(status)&&WEXITSTATUS(status)==0);
}
int main(void)
{
 const uint64_t p=MOUSE_CAPTURE_Q;
 for(unsigned b=0;b<2;b++)for(unsigned m=1;m<=20;m+=(m==1?3:m==4?1:15)) {
  fresh(b?1996800:2457600,m);
  input(p,0,12,-12,0x20);
  mouseif_o7fdd(0x7fdd,0);assert(!nevent_iswork(NEVENT_MOUSE));
  at(p+p/2);assert(mouseif.x==6&&mouseif.y==-6&&mouseif.b==0x20);
  MOUSE_TIME before=mouse_machine;
  for(unsigned n=0;n<100;n++)mouseif_i7fd9(0x7fd9);
  assert(memcmp(&before,&mouse_machine,sizeof(before))==0);
  CPU_CLOCK+=123456;CPU_REMCLOCK-=123;mouseif_sync();
  assert(memcmp(&before,&mouse_machine,sizeof(before))==0);
  mouseif_o7fdd(0x7fdd,0x80);assert(mouseif.latch_x==6&&mouseif.latch_y==-6&&mouseif.x==0&&mouseif.rx==6);
  at(2*p);assert(mouseif.x==6&&mouseif.y==-6&&mouseif.rx==0);
  assert(pic.pi[1].irr==0x20&&dispatches==0);
  pic_o02(0x0a,pic.pi[1].imr&~0x20);CPU_FLAG|=I_FLAG;pic_irq();
  assert(dispatches==1&&vector==0x15&&pic.pi[1].isr==0x20);
  at(3*p);pic_irq();assert(dispatches==1&&pic.pi[1].irr==0x20);
  pic_o00(8,0x20);pic_o00(0,0x20);pic_irq();assert(dispatches==2);
 }
 fresh(2457600,1);mouseif_o7fdd(0x7fdd,0);mouse_fake_now=MOUSE_IRQ_Q;
 mouseif_o7fdd(0x7fdd,0x10);assert(mouse_machine.publications==1&&pic.pi[1].irr==0x20);
 assert(mouse_machine.next_irq==2*MOUSE_IRQ_Q);at(2*MOUSE_IRQ_Q);assert(!mouse_machine.irq_pending);
 fresh(2457600,1);mouseif_o7fdd(0x7fdd,0);mouse_fake_now=MOUSE_IRQ_Q;
 mouseif_obfdb(0xbfdb,3);assert(mouse_machine.next_irq==2*MOUSE_IRQ_Q);
 at(2*MOUSE_IRQ_Q);assert(mouse_machine.next_irq==10*MOUSE_IRQ_Q);
 fresh(2457600,1);input(p,0,300,-300,0xa0);at(2*p);
 mouseif_o7fdd(0x7fdd,0x10);mouseif_o7fdd(0x7fdd,0x90);
 assert(mouseif.latch_x==127&&mouseif.latch_y==-128&&mouseif.x==0&&mouseif.y==0);
 for(unsigned i=0;i<8;i++)mouseif_i7fd9(0x7fd9);
 assert(mouseif.latch_x==127);mouseif_o7fdd(0x7fdd,0x10);mouseif_o7fdd(0x7fdd,0x90);assert(mouseif.latch_x==0);
 fresh(2457600,1);mouseif_o7fdf(0x7fdf,0x93);assert(mouseif.upd8255.portc==0&&mouse_machine.irq_pending);
 /* Exact simultaneous input/capture/IRQ: 2.5 s =141 captures=300 IRQs. */
 fresh(2457600,1);input(141*p,0,3,5,0x20);mouseif_o7fdd(0x7fdd,0);
 at(141*p);assert(mouse_machine.captures==141&&mouse_machine.expiries==300&&mouseif.sx==3&&mouseif.b==0x20);
 assert(mouseif.x==0);mouseif_o7fdd(0x7fdd,0x10);assert(mouse_machine.publications==300);
 for(unsigned kind=0;kind<5;kind++)reject_without_mutation(kind);
 puts("PASS_REAL_MOUSE_IO_PIC_BINDING_FAKE_TIME_BOTH_BASES_M1_M4_M5_M20");
 return 0;
}
