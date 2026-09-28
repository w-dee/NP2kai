/* SPDX-License-Identifier: MIT */
#include "opna_timer_time.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned rng=617;
static unsigned random32(void) { rng=rng*1664525u+1013904223u;return rng; }
int main(void)
{
    unsigned mode,n;
    for(mode=0;mode<2;mode++) {
        for(n=0;n<20000;n++) {
            OPNA_TIMER_TIME a,b;
            uint32_t p[2]={1+random32()%45298,1+random32()%181194};
            uint64_t t=(uint64_t)random32()*12345,cut=t/3,d,preview,first,last,next;
            opna_timer_time_reset(&a,mode);
            opna_timer_time_observe(&a,(OPNA_TIMER_SAMPLE){7,1},p);
            opna_timer_time_control(&a,3,p);b=a;
            preview=opna_timer_time_expiries_until(&b,(OPNA_TIMER_SAMPLE){t+7,1},0,p[0]);
            if (preview) {
                assert(opna_timer_time_nth_deadline(&b,0,p[0],1,&first) && first<=t+7);
                assert(opna_timer_time_nth_deadline(&b,0,p[0],preview,&last) && last<=t+7);
                assert(opna_timer_time_nth_deadline(&b,0,p[0],preview+1,&next) && next>t+7);
            }
            opna_timer_time_observe(&a,(OPNA_TIMER_SAMPLE){t+7,1},p);
            assert(a.expired[0]==preview);
            opna_timer_time_observe(&b,(OPNA_TIMER_SAMPLE){cut+7,1},p);
            opna_timer_time_observe(&b,(OPNA_TIMER_SAMPLE){t+7,1},p);
            assert(!memcmp(a.timer,b.timer,sizeof(a.timer)));
            assert(!memcmp(a.expired,b.expired,sizeof(a.expired)));
            assert(opna_timer_time_deadline(&a,0,&d) && d>t+7);
            opna_timer_time_observe(&a,(OPNA_TIMER_SAMPLE){d-1,1},p);
            assert(a.expired[0]==b.expired[0]);
            opna_timer_time_observe(&a,(OPNA_TIMER_SAMPLE){d,1},p);
            assert(a.expired[0]==b.expired[0]+1);
            b=a;
            opna_timer_time_observe(&a,(OPNA_TIMER_SAMPLE){0,1},p);
            opna_timer_time_observe(&a,(OPNA_TIMER_SAMPLE){UINT64_MAX,0},p);
            assert(!memcmp(a.timer,b.timer,sizeof(a.timer)) && a.anchor_ns==b.anchor_ns);
        }
        {
            OPNA_TIMER_TIME s; uint32_t p[2]={mode?35:44,mode?575:707};
            uint64_t ticks,phase,deadline; unsigned i;
            opna_timer_time_reset(&s,mode);
            opna_timer_time_observe(&s,(OPNA_TIMER_SAMPLE){0,1},p);
            opna_timer_time_control(&s,3,p);
            opna_timer_time_observe(&s,(OPNA_TIMER_SAMPLE){UINT64_MAX,1},p);
            /* Independent widened arithmetic, beyond any realistic uptime. */
            ticks=(__uint128_t)UINT64_MAX*s.numerator/78125;
            phase=(__uint128_t)UINT64_MAX*s.numerator%78125;
            for(i=0;i<2;i++) {
                assert(s.expired[i]==ticks/p[i]);
                assert(s.timer[i].remaining==p[i]-ticks%p[i]);
                assert(s.timer[i].fraction==phase);
                assert(!opna_timer_time_deadline(&s,i,&deadline));
                printf("clock8=%u timer=%u expired=%llu remaining=%u fraction=%u\n",mode,i,(unsigned long long)s.expired[i],s.timer[i].remaining,s.timer[i].fraction);
            }
        }
    }
    puts("PASS OPNA rational partition/boundary/rejected-source/uint64 huge-gap arithmetic");
    return 0;
}
