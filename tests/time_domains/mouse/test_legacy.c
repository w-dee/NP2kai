/* SPDX-License-Identifier: MIT */
/* Executable legacy baseline: actual mouseif, SDL manager, PIC and NEVENT. */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <io/iocore.h>
#include <mousemng.h>
#include <legacycpu.h>
#include <opna_timer_machine.h>
#include <gdc_machine.h>
#include <mouse_machine.h>
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#if defined(CPUCORE_IA32)
I386CORE i386core;
#else
I286CORE i286core;
#endif
PCCORE pccore;
PCSTAT pcstat;
NP2CFG np2cfg;
_MOUSEIF mouseif;
_PIC pic;
_PIT pit;
_GDC gdc;
static unsigned callbacks,publications,dispatches;
static unsigned last_vector;
#if defined(CPUCORE_IA32)
void CPUCALL ia32_interrupt(int v,int soft){dispatches++;last_vector=v;(void)soft;}
#else
void CPUCALL i286c_interrupt(REG8 v){dispatches++;last_vector=v;}
#endif
REG8 keystat_getmouse(SINT16 *x,SINT16 *y){(void)x;(void)y;return 0xff;}
#include "pic-body.inc"
static void audit_irq(REG8 irq){publications++;pic_setirq(irq);}
static void trace_callback(NEVENTITEM item){callbacks++;mouseint(item);}
static void audit_set(NEVENTID id,SINT32 cycles,NEVENTCB cb,NEVENTPOSITION pos){
 nevent_set(id,cycles,cb==mouseint?trace_callback:cb,pos);
}
#define pic_setirq audit_irq
#define nevent_set audit_set
#include "mouseif-body.inc"
#undef nevent_set
#undef pic_setirq
static void fresh(unsigned base,unsigned multiple){
 memset(&np2cfg,0,sizeof(np2cfg));memset(&pccore,0,sizeof(pccore));
 pccore.baseclock=base;pccore.multiple=multiple;pccore.realclock=base*multiple;
 CPU_CLOCK=0;CPU_BASECLOCK=0x400000;CPU_REMCLOCK=CPU_BASECLOCK;CPU_FLAG=0;
 nevent_allreset();pic_reset(&np2cfg);mouseif_reset(&np2cfg);mousemng_initialize();
 mouseif_limitcounter=0;mouseif_absflag=0;callbacks=publications=dispatches=last_vector=0;
}
static void delta(int x,int y){SDL_MouseMotionEvent m;memset(&m,0,sizeof(m));m.xrel=x;m.yrel=y;mousemng_onmove(&m);}
static void button(int down){SDL_MouseButtonEvent b;memset(&b,0,sizeof(b));b.button=SDL_BUTTON_LEFT;b.type=down?SDL_MOUSEBUTTONDOWN:SDL_MOUSEBUTTONUP;mousemng_buttonevent(&b);}
static void snapshot(const char *name){
 printf("{\"case\":\"%s\",\"cpu_now\":%u,\"base\":%u,\"multiple\":%u,\"period\":%u,\"moveclock\":%u,\"next_remaining\":%d,\"host\":[%d,%d,%u],\"device\":[%d,%d,%d,%d,%d,%d,%u],\"latch\":[%d,%d],\"portc\":%u,\"lastc\":%u,\"rapid\":%u,\"limit\":%d,\"absflag\":%d,\"callbacks\":%u,\"publications\":%u,\"irr\":%u,\"isr\":%u,\"dispatches\":%u,\"vector\":%u}\n",
 name,legacy_cpu_device_now(),pccore.baseclock,pccore.multiple,mouseif.intrclock<<mouseif.timing,mouseif.moveclock,
 nevent_iswork(NEVENT_MOUSE)?nevent_getremain(NEVENT_MOUSE):-1,mousemng.x,mousemng.y,mousemng.btn,
 mouseif.x,mouseif.y,mouseif.sx,mouseif.sy,mouseif.rx,mouseif.ry,mouseif.b,mouseif.latch_x,mouseif.latch_y,
 mouseif.upd8255.portc,mouseif.lastc,mouseif.rapid,mouseif_limitcounter,mouseif_absflag,callbacks,publications,pic.pi[1].irr,pic.pi[1].isr,dispatches,last_vector);
}
static void advance(uint64_t cycles){
 while(cycles){
  if(CPU_REMCLOCK<=0){nevent_progress();continue;}
  uint64_t n=cycles<(uint64_t)CPU_REMCLOCK?cycles:(uint64_t)CPU_REMCLOCK;
  CPU_REMCLOCK-=(SINT32)n;cycles-=n;
  if(CPU_REMCLOCK<=0)nevent_progress();
 }
}
static void setnow(UINT32 cycles){CPU_CLOCK=cycles;CPU_BASECLOCK=CPU_REMCLOCK=1000000;}
static void forced_tick(void){_NEVENTITEM item;memset(&item,0,sizeof(item));item.flag=NEVENT_SETEVENT;trace_callback(&item);}
int main(int argc,char **argv){
 setvbuf(stdout,NULL,_IONBF,0);
 if(argc>1){fresh(2457600,1);delta(32767,0);mouseif_sync();setportc(0x10);setnow(100000000);mouseif_i7fd9(0x7fd9);snapshot("overflow_diagnostic");return 0;}
 (void)argv;
 fresh(2457600,1);snapshot("reset_before_sync");mouseif_sync();setportc(0);snapshot("timer_start");
 unsigned period=mouseif.intrclock;advance(period-1);snapshot("timer_before");advance(1);snapshot("timer_exact");
 advance(6u*period);assert(callbacks==7&&publications==7&&pic.pi[1].irr==0x20);snapshot("seven_ticks_IF0");
 pic_o02(0x0a,pic.pi[1].imr&~0x20);CPU_FLAG|=I_FLAG;pic_irq();assert(dispatches==1&&last_vector==0x15);snapshot("dispatch_hook_after_IF1");
 advance(period);pic_irq();assert(dispatches==1&&pic.pi[1].irr==0x20);snapshot("request_while_ISR");
 pic_o00(8,0x20);pic_o00(0,0x20);pic_irq();assert(dispatches==2);snapshot("EOI_then_dispatch_hook");
 for(unsigned timing=0;timing<4;timing++){
  fresh(2457600,1);mouseif_obfdb(0xbfdb,timing);setportc(0);advance((uint64_t)mouseif.intrclock<<timing);
  assert(callbacks==1);char tag[64];snprintf(tag,sizeof(tag),"rate_mode_%u",timing);snapshot(tag);
 }
 fresh(2457600,1);setportc(0);unsigned before=nevent_getremain(NEVENT_MOUSE);mouseif_obfdb(0xbfdb,3);
 assert(nevent_getremain(NEVENT_MOUSE)==before);advance(before);snapshot("rate_change_keeps_current_deadline");
 fresh(2457600,1);setportc(0);setportc(0x10);assert(nevent_iswork(NEVENT_MOUSE));advance(mouseif.intrclock);
 assert(callbacks==1&&publications==0&&!nevent_iswork(NEVENT_MOUSE));snapshot("disable_leaves_one_callback_no_rearm");
 fresh(2457600,1);setportc(0);advance(mouseif.intrclock);setportc(0x10);assert(pic.pi[1].irr==0x20);snapshot("expiry_then_disable_pending_retained");
 fresh(2457600,1);mouseif_o7fdf(0x7fdf,0x93);assert(mouseif.upd8255.portc==0&&nevent_iswork(NEVENT_MOUSE));snapshot("mode_write_clears_portc_enables_timer");
 fresh(2457600,1);delta(3,4);delta(5,-1);button(1);setportc(0);forced_tick();snapshot("held_t3_no_sync");
 delta(-2,7);button(0);forced_tick();assert(mousemng.x==6&&mousemng.y==10&&mouseif.x==0&&mouseif.sx==0);snapshot("held_t5_no_sync");
 mouseif_sync();snapshot("resume_first_sync");mouseif_sync();setportc(0x80);snapshot("resume_second_sync_latch");assert(mouseif.latch_x==6&&mouseif.latch_y==10);
 fresh(2457600,1);delta(3,4);delta(5,-1);button(1);mouseif_sync();setportc(0);forced_tick();snapshot("held_t3_with_sync");
 delta(-2,7);button(0);mouseif_sync();forced_tick();snapshot("held_t5_with_sync");setportc(0x80);assert(mouseif.latch_x==8&&mouseif.rx==-2);snapshot("held_latch_before_residual_flush");
 for(unsigned split=0;split<2;split++){
  fresh(2457600,1);if(split){for(unsigned n=0;n<4;n++)delta(1,-1);}else delta(4,-4);
  mouseif_sync();mouseif_sync();assert(mouseif.x==4&&mouseif.y==-4);snapshot(split?"host_four_ones":"host_single_four");
 }
 fresh(2457600,1);delta(32767,-32768);delta(1,-1);snapshot("host_signed16_wrap");assert(mousemng.x==-32768&&mousemng.y==32767);
 fresh(2457600,1);delta(10,-10);delta(-10,10);mouseif_sync();assert(mouseif.sx==0&&mouseif.sy==0);snapshot("opposite_deltas_before_sync");
 fresh(2457600,1);button(1);button(0);mouseif_sync();snapshot("button_pulse_between_syncs_lost");assert(mouseif.b==0xa0);
 for(unsigned split=0;split<2;split++){
  fresh(2457600,1);delta(10,-10);mouseif_sync();setportc(0x10);
  if(split)for(unsigned c=2000;c<=42000;c+=2000){setnow(c);mouseif_i7fd9(0x7fd9);}
  setnow(43000);mouseif_i7fd9(0x7fd9);snapshot(split?"movement_many_reads":"movement_one_read");
  assert(mouseif.x==(split?0:10));
 }
 for(unsigned m=1;m<=20;m+=(m==1?3:m==4?1:15)){
  for(unsigned b=0;b<2;b++){
   fresh(b?1996800:2457600,m);delta(100,-100);mouseif_sync();setportc(0x10);setnow(pccore.realclock/100);mouseif_i7fd9(0x7fd9);snapshot("ten_ms_movement_scale");
  }
 }
 fresh(2457600,1);delta(300,-300);mouseif_sync();mouseif_sync();setportc(0);setportc(0x80);assert(mouseif.latch_x==127&&mouseif.latch_y==-128&&mouseif.x==0);snapshot("latch_clamp_drops_excess");
 for(unsigned n=0;n<8;n++)mouseif_i7fd9(0x7fd9);assert(mouseif.latch_x==127);setportc(0);setportc(0x80);assert(mouseif.latch_x==0);snapshot("relatch_empty_after_clamp");
 fresh(2457600,1);delta(127,-128);mouseif_sync();mouseif_sync();setportc(0);setportc(0x80);assert(mouseif.latch_x==127&&mouseif.latch_y==-128);snapshot("latch_boundaries");
 fresh(2457600,1);mouseif.x=300;mouseif_limitcounter=4;setportc(0x10);unsigned r[5];for(unsigned n=0;n<5;n++)r[n]=mouseif_i7fd9(0x7fd9);printf("{\"case\":\"live_read_clamp_four_then_wrap\",\"reads\":[%u,%u,%u,%u,%u]}\n",r[0],r[1],r[2],r[3],r[4]);
 fresh(2457600,1);delta(9,8);button(1);mouseif_limitcounter=3;mouseif_absflag=5;mouseif_reset(&np2cfg);snapshot("device_reset_preserves_host_and_statics");assert(mousemng.x==9&&mousemng.btn==0x20&&mouseif_limitcounter==3&&mouseif_absflag==5);
 mouseif_sync();snapshot("reset_then_sync_abs_suppression");
 fresh(2457600,1);setportc(0);advance((uint64_t)mouseif.intrclock*1000000);assert(callbacks==1000000&&pic.pi[1].irr==0x20);snapshot("million_no_input_real_nevent_callbacks");
 fresh(2457600,1);setportc(0);snapshot("frozen_cpu_no_scheduler_service");
 for(unsigned order=0;order<2;order++){
  fresh(2457600,1);delta(10,-10);mouseif_sync();setportc(0);CPU_REMCLOCK=0;
  if(order)mouseif_i7fd9(0x7fd9);nevent_progress();if(!order)mouseif_i7fd9(0x7fd9);
  snapshot(order?"same_T_read_then_expiry":"same_T_expiry_then_read");
  fresh(2457600,1);setportc(0);CPU_REMCLOCK=0;
  if(order)setportc(0x10);nevent_progress();if(!order)setportc(0x10);
  snapshot(order?"same_T_disable_then_expiry":"same_T_expiry_then_disable");
  fresh(2457600,1);setportc(0);CPU_REMCLOCK=0;
  if(order){delta(3,5);button(1);}nevent_progress();if(!order){delta(3,5);button(1);}
  snapshot(order?"same_T_host_then_expiry":"same_T_expiry_then_host");
  fresh(2457600,1);setnow(1000);
  if(order){delta(3,5);button(1);}mouseif_sync();if(!order){delta(3,5);button(1);}
  snapshot(order?"same_T_host_then_sync":"same_T_sync_then_host");
  fresh(2457600,1);setportc(0);CPU_REMCLOCK=0;
  if(order)mouseif_obfdb(0xbfdb,3);nevent_progress();if(!order)mouseif_obfdb(0xbfdb,3);
  snapshot(order?"same_T_rate_then_expiry":"same_T_expiry_then_rate");
  fresh(2457600,1);
  if(order){for(unsigned i=0;i<4;i++){delta(1,0);mouseif_sync();}}else{delta(4,0);mouseif_sync();}
  snapshot(order?"four_input_sync_batches":"one_input_sync_batch");
  fresh(2457600,1);setportc(0);
  if(order){for(unsigned i=0;i<7;i++)advance(mouseif.intrclock);}else advance(7u*mouseif.intrclock);
  snapshot(order?"seven_small_scheduler_advances":"one_large_scheduler_advance");
 }
 puts("{\"result\":\"PASS_REAL_SOURCE_AUDIT_PROBES\"}");return 0;
}
