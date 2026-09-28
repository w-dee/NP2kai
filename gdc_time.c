/* SPDX-License-Identifier: MIT */
#include "gdc_time.h"
#include <string.h>

void gdc_add_sat(uint64_t *v, uint64_t n)
{
    *v = n > UINT64_MAX - *v ? UINT64_MAX : *v + n;
}
int gdc_profile_make(GDC_PROFILE *p, const uint8_t s[8], unsigned klass,
                     uint32_t base)
{
    uint32_t cr, w, x, y, lf, vf, xx, yy, source, lo, hi, yl, yh, frame;
    if (base != 1996800 && base != 2457600) return 0;
    if (klass == 15) { source=14318180/8; lo=104; hi=120; yl=200; yh=300; }
    else if (klass == 24) { source=21052600/8; lo=100; hi=112; yl=400; yh=575; }
    else if (klass == 31) { source=25260000/8; lo=92; hi=108; yl=400; yh=575; }
    else return 0;
    cr=s[1]+2; w=s[2]+256u*s[3];
    x=cr+(w&31)+(w>>10)+(s[4]&63)+3;
    vf=((w>>5)&31)+(s[5]&63);
    w=s[6]+256u*s[7]; lf=((w-1)&1023)+1; vf+=w>>10;
    y=lf+(vf ? vf : 1);
    xx=x<lo ? lo : (x>hi ? hi : x);
    yy=y<yl ? yl : (y>yh ? yh : y);
    cr=xx*cr/x; lf=yy*lf/y;
    p->hclock=source/xx; p->vclock=10*p->hclock/yy;
    /* Preserve the parent division BEFORE multiplication and M_ref=5. */
    frame=(base*yy/p->hclock)*5u;
    p->raster=frame/yy; p->horizontal=p->raster*cr/xx;
    p->display=p->raster*lf; p->vertical=frame-p->display;
    return p->raster && p->display && p->vertical;
}
void gdc_time_reset(GDC_TIME *s, uint32_t base, const GDC_PROFILE *p)
{
    memset(s,0,sizeof(*s)); s->base=base; s->profile=*p;
    s->remaining=p->display;
}
int gdc_time_sample(GDC_TIME *s, GDC_SAMPLE now, uint64_t *ticks)
{
    uint64_t d,part;
    uint32_t numerator=s->base==1996800 ? 780 : 960;
    *ticks=0; gdc_add_sat(&s->services,1);
    if (!now.valid || (s->anchored && now.ns<s->anchor_ns)) {
        gdc_add_sat(&s->rejected,1); return 0;
    }
    if (!s->anchored) { s->anchored=1; s->anchor_ns=now.ns; return 1; }
    d=now.ns-s->anchor_ns;
    /* Reduced exact 5*B_ref/1e9 conversion, including UINT64-scale inputs. */
    part=(d%78125u)*numerator+s->fraction;
    *ticks=(d/78125u)*numerator+part/78125u;
    s->fraction=(uint32_t)(part%78125u);
    s->anchor_ns=now.ns;
    if (d>s->max_gap_ns) s->max_gap_ns=d;
    gdc_add_sat(&s->ticks,*ticks);
    return 1;
}
GDC_EDGES gdc_time_skip(GDC_TIME *s, uint64_t q)
{
    GDC_EDGES e={0,0,!s->vsync};
    uint64_t n, period, tail, late;
    uint32_t duration;
    if (q<s->remaining) { s->remaining-=(uint32_t)q; return e; }
    late=q-s->remaining;
    if (late>s->max_late_ticks) s->max_late_ticks=late;
    q-=s->remaining; s->vsync=!s->vsync;
    period=(uint64_t)s->profile.display+s->profile.vertical;
    n=1+2*(q/period); tail=q%period;
    duration=s->vsync ? s->profile.vertical : s->profile.display;
    if (tail>=duration) { tail-=duration; s->vsync=!s->vsync; n++; }
    duration=s->vsync ? s->profile.vertical : s->profile.display;
    s->remaining=duration-(uint32_t)tail;
    e.vertical=(n+e.first_vertical)/2;
    e.display=n-e.vertical;
    gdc_add_sat(&s->transitions,n);
    if (n>1) gdc_add_sat(&s->collapsed,n-1);
    return e;
}
unsigned gdc_time_status(const GDC_TIME *s)
{
    return (s->vsync ? 0x20u : 0) |
           (s->remaining%s->profile.raster<s->profile.horizontal ? 0x40u : 0);
}
int gdc_time_deadline(const GDC_TIME *s, uint64_t *ns)
{
    uint32_t numerator=s->base==1996800 ? 780 : 960;
    uint64_t delta;
    if (!s->anchored) return 0;
    delta=((uint64_t)s->remaining*78125u-s->fraction+numerator-1)/numerator;
    if (delta>UINT64_MAX-s->anchor_ns) return 0;
    *ns=s->anchor_ns+delta; return 1;
}
