/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <io/iocore.h>
#include <keystat.h>
#include "tier1_machine.h"
#include <stdio.h>
#include <stdlib.h>
TIER1_MACHINE tier1_machine;
uint64_t tier1_fake_now;
int tier1_dispatching;
static int servicing;
void tier1_reject(void)
{
 fputs("Tier1 normalized fake profile: rejected time/input/configuration/resource domain\n", stderr);
 abort();
}
static int configuration(void)
{
 return (pccore.baseclock == 1996800 || pccore.baseclock == 2457600) &&
        pccore.baseclock == tier1_machine.base && !np2cfg.keyrepeat_enable &&
        !np2cfg.KEY_MODE;
}
static uint64_t now(void) { return servicing ? tier1_machine.cursor : tier1_fake_now; }
int tier1_start(uint64_t q, unsigned base)
{
 if (q > TIER1_LIMIT || (base != 1996800 && base != 2457600)) return 0;
 memset(&tier1_machine, 0, sizeof(tier1_machine));
 tier1_machine.frontier = tier1_machine.cursor = q;
 tier1_machine.base = base; tier1_machine.ready = 1;
 return 1;
}
int tier1_admit(TIER1_EDGE e)
{
 TIER1_MACHINE *s=&tier1_machine;
 if (!s->ready || !configuration() || e.q > TIER1_LIMIT || e.q < s->frontier ||
     (s->sealed && e.q == s->frontier) || e.source < 1 || e.source > TIER1_SOURCES ||
     e.key >= TIER1_KEYS || e.down > 1 || s->count == TIER1_INPUT_CAPACITY ||
     (s->have_sequence && (e.sequence <= s->sequence || e.q < s->input_q))) return 0;
 s->input[s->count++] = e; s->sequence=e.sequence; s->input_q=e.q; s->have_sequence=1;
 return 1;
}
void tier1_key_arm(void)
{
 TIER1_MACHINE *s=&tier1_machine;
 if (!s->key_armed) { s->key_due=now()+TIER1_KEY_PERIOD; s->key_armed=1; }
}
void tier1_key_reset(void)
{
 tier1_service();
 tier1_machine.key_armed=0; tier1_machine.key_due=0; ++tier1_machine.epoch;
 /* Preserve per-source held ownership. The existing reset signal resends
  * keystat held keys; already admitted future edges retain original time. */
}
void tier1_fdc_irq(void)
{
 tier1_service();
 tier1_machine.fdc_due=now()+512*(TIER1_HZ/tier1_machine.base);
 tier1_machine.fdc_armed=1;
}
void tier1_fdc_seek(unsigned drive, unsigned frames)
{
 if (drive >= 4 || frames > 255) tier1_reject();
 tier1_service();
 tier1_machine.seek_due[drive]=frames ? now()+frames*TIER1_FRAME : 0;
 fdc.int_timer[drive]=(UINT8)frames;
}
void tier1_fdc_reset(void)
{
 tier1_service();
 memset(tier1_machine.seek_due,0,sizeof(tier1_machine.seek_due));
 tier1_machine.fdc_armed=0; tier1_machine.fdc_due=0;
}
int tier1_gdc_duration(unsigned dots, uint64_t *duration)
{
 uint64_t k,unit;
 if (!tier1_machine.ready || !configuration()) return 0;
 k=(pccore.cpumode & CPUMODE_8MHZ) ? 22464 : 27648;
 unit=TIER1_HZ/(UINT64_C(15625)*tier1_machine.base);
 /* UINT32 dots * K * unit fits uint64 for both bases. */
 *duration=(uint64_t)dots*k*unit+30*(TIER1_HZ/tier1_machine.base);
 return 1;
}
static void busy(uint64_t duration)
{
 uint64_t start;
 /* Preflight BEFORE settling other devices: an invalid command duration
  * cannot partially publish unrelated timers/input either. */
 if (!tier1_machine.ready || !configuration() || tier1_fake_now < tier1_machine.frontier || tier1_fake_now > TIER1_LIMIT)
  tier1_reject();
 start=tier1_machine.busy_armed && tier1_machine.busy_due > now() ? tier1_machine.busy_due : now();
 if (duration > TIER1_LIMIT-start) tier1_reject();
 tier1_service();
 tier1_machine.busy_due=start+duration; tier1_machine.busy_armed=1; gdc.s_drawing=8;
}
void tier1_gdc_wait(unsigned dots)
{
 uint64_t d;
 if (!tier1_gdc_duration(dots,&d)) tier1_reject();
 busy(d);
}
void tier1_gdc_raw(unsigned cycles)
{
 if (!tier1_machine.ready || !configuration()) tier1_reject();
 busy((uint64_t)cycles*(TIER1_HZ/tier1_machine.base));
}
void tier1_gdc_reset(void)
{ tier1_service(); tier1_machine.busy_armed=0; tier1_machine.busy_due=0; }
int tier1_settle(uint64_t target)
{
 TIER1_MACHINE *s=&tier1_machine;
 unsigned n,i;
 uint64_t t;
 _NEVENTITEM event;
 if (!s->ready || servicing || !configuration() || target < s->frontier || target > TIER1_LIMIT) return 0;
 /* Conservative finite admission envelope: even with no transfers, all
  * pending edges through target fit the actual device FIFO. Reject before
  * ANY device/PIC/keystat mutation. Duplicates still count in this bound. */
 for (n=0;n<s->count && s->input[n].q<=target;++n) {}
 if (keybrd.buffers > KB_BUF || keybrd.ctrls > KB_CTR || n > KB_BUF-keybrd.buffers) return 0;
 memset(&event,0,sizeof(event));event.flag=NEVENT_SETEVENT;
 servicing=1;
 for (;;) {
  t=target+1;
  if (s->count && s->input[0].q<t) t=s->input[0].q;
  if (s->key_armed && s->key_due<t) t=s->key_due;
  if (s->fdc_armed && s->fdc_due<t) t=s->fdc_due;
  if (s->busy_armed && s->busy_due<t) t=s->busy_due;
  for (i=0;i<4;++i) if (s->seek_due[i] && s->seek_due[i]<t) t=s->seek_due[i];
  if (t>target) break;
  s->cursor=t;
  /* Apply edges in timestamp/sequence order before the exact-T transfer. */
  while (s->count && s->input[0].q==t) {
   TIER1_EDGE e=s->input[0];unsigned bit=1u<<(e.source-1),old=s->owners[e.key];
   UINT8 key=(UINT8)e.key;
   s->owners[e.key]=e.down ? old|bit : old&~bit;
   tier1_dispatching=1;
   if (!old && s->owners[e.key]) keystat_down(&key,1,key);
   if (old && !s->owners[e.key]) keystat_up(&key,1,key);
   tier1_dispatching=0;
   --s->count;memmove(s->input,s->input+1,s->count*sizeof(s->input[0]));
   memset(s->input+s->count,0,sizeof(s->input[0]));++s->edges_applied;
  }
  if (s->key_armed && s->key_due==t) {
   s->key_armed=0;++s->key_expiries;keyboard_callback(&event);
   /* Repeated full-register expiries have only the same finite PIC bit.
    * Stop before the next edge; external guest observations end service. */
   if (s->key_armed && (keybrd.status&2)) {
    uint64_t limit=target,skip;
    if (s->count && s->input[0].q<=limit) limit=s->input[0].q-1;
    if (s->key_due<=limit) {
     skip=(limit-s->key_due)/TIER1_KEY_PERIOD+1;
     /* When queues emptied, the next callback would simply stop rearming. */
     if (keybrd.ctrls || keybrd.buffers) {s->key_due+=skip*TIER1_KEY_PERIOD;s->key_expiries+=skip;}
     else {s->key_armed=0;++s->key_expiries;}
    }
   }
  }
  for (i=0;i<4;++i) if (s->seek_due[i] && s->seek_due[i]==t) {
   s->seek_due[i]=0;fdc.int_timer[i]=0;fdc.stat[i]=fdc.int_stat[i];fdc_interrupt();
  }
  if (s->fdc_armed && s->fdc_due==t) {s->fdc_armed=0;fdc_intwait(&event);}
  if (s->busy_armed && s->busy_due==t) {s->busy_armed=0;gdc.s_drawing=0;}
 }
 for (i=0;i<4;++i) if (s->seek_due[i])
  fdc.int_timer[i]=(UINT8)((s->seek_due[i]-target+TIER1_FRAME-1)/TIER1_FRAME);
 s->frontier=s->cursor=target;s->sealed=1;servicing=0;
 return 1;
}
void tier1_service(void)
{
 if (!tier1_machine.ready || servicing) return;
 if (!tier1_settle(tier1_fake_now)) tier1_reject();
}
