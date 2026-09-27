/* SPDX-License-Identifier: MIT */
#include "pit0_time.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint64_t ns_at(uint64_t q, unsigned numerator)
{
    return (q*78125+numerator-1)/numerator;
}
static int apply(int irr, PIT0_EFFECT e)
{
    return e.irr_effect ? e.irr_effect > 0 : irr;
}
int main(void)
{
    PIT0_TIME s,a,b;
    PIT0_EFFECT e;
    uint64_t deadline;
    unsigned family,mode,masked,armed,n,k;
    unsigned counts[]={0,1,8,9,10,11,12,65535};
    for(family=0;family<2;family++)for(mode=0;mode<2;mode++)
    for(masked=0;masked<2;masked++)for(armed=0;armed<2;armed++)
    for(n=0;n<8;n++){
        int ia=0,ib=0,aa=armed,ab=armed;
        pit0_time_reset(&a,family);pit0_time_schedule(&a,counts[n]);
        pit0_time_observe(&a,(PIT0_SAMPLE){0,1},counts[n],mode,aa,masked);
        b=a;
        /* Large jump versus a thousand unequal services, constant programming. */
        uint64_t end=UINT64_C(1000000000000000);
        e=pit0_time_observe(&a,(PIT0_SAMPLE){end,1},counts[n],mode,aa,masked);
        ia=apply(ia,e);aa=e.armed;
        for(k=1;k<=1000;k++){
            e=pit0_time_observe(&b,(PIT0_SAMPLE){end*k/1000,1},counts[n],mode,ab,masked);
            ib=apply(ib,e);ab=e.armed;
        }
        assert(ia==ib && aa==ab && a.remaining==b.remaining &&
               a.mask_remaining==b.mask_remaining && a.fraction==b.fraction);
    }
    for(family=0;family<2;family++){
        pit0_time_reset(&s,family);pit0_time_schedule(&s,9);
        pit0_time_observe(&s,(PIT0_SAMPLE){0,1},9,1,1,1);
        assert(pit0_time_deadline(&s,&deadline) && deadline==ns_at(45,s.numerator));
        e=pit0_time_observe(&s,(PIT0_SAMPLE){deadline-1,1},9,1,1,1);
        assert(!e.irr_effect && s.remaining==1);
        e=pit0_time_observe(&s,(PIT0_SAMPLE){deadline,1},9,1,1,1);
        assert(e.irr_effect==1 && s.mask_remaining==11);
        e=pit0_time_observe(&s,(PIT0_SAMPLE){ns_at(55,s.numerator),1},9,1,1,1);
        assert(!e.irr_effect && s.mask_remaining==1);
        assert(pit0_time_deadline(&s,&deadline) && deadline==ns_at(56,s.numerator));
        e=pit0_time_observe(&s,(PIT0_SAMPLE){deadline,1},9,1,1,1);
        assert(e.irr_effect==-1 && !s.mask_remaining);
        a=s;e=pit0_time_observe(&s,(PIT0_SAMPLE){deadline,1},9,1,1,1);
        assert(!e.irr_effect && a.remaining==s.remaining && a.fraction==s.fraction);
        pit0_time_observe(&s,(PIT0_SAMPLE){0,1},9,1,1,1);
        pit0_time_observe(&s,(PIT0_SAMPLE){UINT64_MAX,0},9,1,1,1);
        assert(s.rejected==2 && s.anchor_ns==a.anchor_ns && s.remaining==a.remaining);
        e=pit0_time_observe(&s,(PIT0_SAMPLE){UINT64_MAX,1},9,1,1,1);
        assert(s.remaining>0 && s.remaining<=45 && s.collapsed>UINT64_C(1000000000));
        assert(!pit0_time_deadline(&s,&deadline)); /* representability, no wrap */
    }
    puts("PASS analytical huge-jump partition invariance, fractional deadline, count9 M5, rejection/overflow");
}
