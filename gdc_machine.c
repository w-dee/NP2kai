/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <io/iocore.h>
#include <vram/vram.h>
#if defined(SUPPORT_WAB)
#include <wab/wab.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gdc_machine.h"
#if defined(NP2_PIT_PIC_MACHINE_TIME)
#include "pit0_time.h"
#endif

#if defined(SUPPORT_ASYNC_CPU) || defined(SUPPORT_IA32_HAXM)
#error GDC machine time requires the single-owner interpreter
#endif
GDC_MACHINE gdc_machine;
const char gdc_machine_source_id[]=NP2_GDC_SOURCE_ID;

static unsigned scan_class(void)
{
#if defined(SUPPORT_CRT31KHZ)
    if (gdc.display & 128) return 31;
#endif
    return gdc.crt15khz & 2 ? 15 : 24;
}
static void reject(int code)
{
    gdc_machine.admission_error=code;
    fprintf(stderr,"GDC machine-time configuration outside admitted profile (%d)\n",code);
    abort();
}
static void admission(void)
{
    if (np2cfg.RASTER) reject(1);
#if defined(SUPPORT_WAB)
    if (np2wab.relay & 3) reject(2);
#endif
    /* The bounded normal master profile, including observed Windows31.
     * Other SYNC mode encodings are deliberately not interpreted as hardware. */
    if (gdc.m.para[GDC_SYNC] != 0x10) reject(3);
}
static void publish(uint64_t frames)
{
    if (!frames) return;
    if (gdc_machine.generation!=gdc_machine.presented)
        gdc_add_sat(&gdc_machine.coalesced,frames);
    else if (frames>1) gdc_add_sat(&gdc_machine.coalesced,frames-1);
    gdc_add_sat(&gdc_machine.generation,frames);
    /* Bounded dirty union: retain raw palette/font flags and rebuild once. */
    gdcs.textdisp |= GDCSCRN_ALLDRAW2;
    gdcs.grphdisp |= GDCSCRN_ALLDRAW2;
}
void gdc_machine_clock_commit(void)
{
    GDC_PROFILE p;
    GDC_TIME *t=&gdc_machine.time;
    /* These two values belong only to the retained CPU-time housekeeping. */
    gdc_machine.heartbeat_display=gdc.dispclock;
    gdc_machine.heartbeat_vertical=gdc.vsyncclock;
    if (!gdc_machine.ready || gdc_machine.servicing) {
        admission();
        if (!gdc_profile_make(&p,gdc.m.para+GDC_SYNC,scan_class(),NP2_GDC_PROFILE_BASE)) reject(4);
        if (!gdc_machine.ready) {
            uint64_t ignored;
            gdc_time_reset(t,NP2_GDC_PROFILE_BASE,&p);
            gdc_time_sample(t,gdc_time_source(),&ignored);
            gdc_machine.ready=1;
        } else t->profile=p; /* Already armed current segment end is unchanged. */
        memcpy(gdc_machine.committed_sync,gdc.m.para+GDC_SYNC,8);
        gdc_machine.committed_class=(uint8_t)scan_class();
    }
    gdc.hclock=t->profile.hclock; gdc.vclock=t->profile.vclock;
    gdc.rasterclock=t->profile.raster; gdc.hsyncclock=t->profile.horizontal;
    gdc.dispclock=t->profile.display; gdc.vsyncclock=t->profile.vertical;
}
void gdc_machine_reset(void)
{
    memset(&gdc_machine,0,sizeof(gdc_machine));
}
static void irq_edge(int vertical)
{
    if (vertical) {
        if (gdc.vsyncint) { gdc.vsyncint=0; pic_setirq(2); }
    } else if (pic.pi[0].irr & PIC_CRTV) {
        pic.pi[0].irr &= ~PIC_CRTV; gdc.vsyncint=1;
    }
}
static void pipeline(uint64_t frames)
{
    if (!frames) return;
    gdc_machine_blink(frames);
    if (memcmp(gdc_machine.committed_sync,gdc.m.para+GDC_SYNC,8) ||
        gdc_machine.committed_class!=scan_class()) gdc_updateclock();
    /* Consume at the existing DISPSYNC-selected pipeline frontier only.
     * A renderer may have consumed EXT since the write, but cannot erase
     * this obligation. Multiple writes coalesce to their latest register bits. */
    if (gdc_machine.clock_pending &&
        (((gdc.clock & 0x80) && gdc.clock!=0x83) || gdc.clock==3)) {
        gdc.clock ^= 0x80;
        gdcs.grphdisp |= GDCSCRN_ALLDRAW2;
    }
    gdc_machine.clock_pending=0;
    publish(frames);
}
void gdc_machine_service_at(GDC_SAMPLE now)
{
    GDC_TIME *t=&gdc_machine.time;
    uint64_t q,frames,n;
    unsigned i;
    GDC_EDGES e;
    if (!gdc_machine.ready || gdc_machine.servicing) return;
    if (np2cfg.RASTER) reject(1);
#if defined(SUPPORT_WAB)
    if (np2wab.relay & 3) reject(2);
#endif
    gdc_machine.servicing=1;
    if (!gdc_time_sample(t,now,&q)) {
        gdc_machine.servicing=0; return;
    }
    if (q>=t->remaining && q-t->remaining>t->max_late_ticks)
        t->max_late_ticks=q-t->remaining;
    /* At most two full alternating pairs drain finite FIFOs, commit their
     * timing, and finish an old latched interval. No elapsed-frame loop. */
    for (i=0;i<4 && q>=t->remaining;i++) {
        q-=t->remaining; t->vsync=!t->vsync;
        gdc.vsync=t->vsync ? 0x20 : 0;
        gdc_work(t->vsync ? GDCWORK_MASTER : GDCWORK_SLAVE);
        irq_edge(t->vsync);
        t->remaining=t->vsync ? t->profile.vertical : t->profile.display;
        if (!!np2cfg.DISPSYNC==t->vsync) pipeline(1);
        /* DISPSYNC=0 commits before the next display interval is armed. */
        if (!t->vsync) t->remaining=t->profile.display;
        gdc_add_sat(&t->transitions,1);
        gdc_add_sat(&gdc_machine.finite_steps,1);
    }
    e=gdc_time_skip(t,q);
    n=e.vertical+e.display;
    /* Alternating pairs are idempotent on the audited 16 IRQ states. */
    if (n) {
        irq_edge(e.first_vertical);
        if (n>=2) irq_edge(!e.first_vertical);
        if (n>=3 && (n&1)) irq_edge(e.first_vertical);
        gdc_add_sat(&gdc_machine.finite_steps,n<3 ? n : 3);
    }
    frames=np2cfg.DISPSYNC ? e.vertical : e.display;
    pipeline(frames);
    gdc.vsync=t->vsync ? 0x20 : 0;
    MEMWAIT_TRAM=np2cfg.wait[t->vsync];
    MEMWAIT_VRAM=np2cfg.wait[2+t->vsync];
    MEMWAIT_GRCG=np2cfg.wait[4+t->vsync];
    gdc_machine.servicing=0;
}
void gdc_machine_service(void)
{
    if (!gdc_machine.ready || gdc_machine.servicing) return;
    gdc_machine_service_at(gdc_time_source());
}
void gdc_machine_pic_service(void)
{
    /* Both admitted producers share one observation frontier before arbitration.
     * No arbitration occurs between the two disjoint finite publications. */
    GDC_SAMPLE now=gdc_time_source();
#if defined(NP2_PIT_PIC_MACHINE_TIME)
    PIT0_SAMPLE pit_now={now.ns,now.valid};
    pit0_machine_service_at(pit_now);
#endif
    gdc_machine_service_at(now);
}
unsigned gdc_machine_status(void)
{
    gdc_machine_service();
    return gdc_time_status(&gdc_machine.time);
}
unsigned gdc_machine_wait(unsigned kind, unsigned legacy)
{
    gdc_machine_service();
    return gdc_machine.ready ? np2cfg.wait[2*kind+gdc_machine.time.vsync] : legacy;
}
int gdc_machine_present_allowed(void)
{
#if defined(NP2_GDC_FAKE_TIME)
    extern int gdc_fake_suppress_presentation;
    if (gdc_fake_suppress_presentation) return 0;
#endif
    return gdc_machine.ready;
}
void gdc_machine_present_done(void)
{
    gdc_machine.presented=gdc_machine.generation;
    gdc_add_sat(&gdc_machine.presentations,1);
}
