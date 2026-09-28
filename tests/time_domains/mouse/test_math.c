/* SPDX-License-Identifier: MIT */
#include "mouse_time.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static MOUSE_INPUT event(uint64_t t, uint64_t seq, int x, int y, unsigned b)
{ MOUSE_INPUT r; memset(&r,0,sizeof(r)); r.q=t;r.sequence=seq;r.x=x;r.y=y;r.buttons=b;return r; }
static void equal(const MOUSE_TIME *a,const MOUSE_TIME *b)
{ assert(memcmp(a,b,sizeof(*a))==0); }
int main(void)
{
    MOUSE_TIME a,b,old;
    const uint64_t p=MOUSE_CAPTURE_Q;
    assert(mouse_time_reset(&a,0));
    assert(mouse_time_admit(&a,event(p,0,12,-12,0x20)));
    assert(mouse_time_admit(&a,event(p,1,2,-2,0xa0)));
    assert(mouse_time_settle(&a,p));
    assert(a.batch[0]==14 && a.live[0]==0 && a.buttons==0xa0);
    assert(mouse_time_settle(&a,p+p/2));
    assert(a.live[0]==7 && a.live[1]==-7 && a.residue[0]==0);
    a.live[0]=a.live[1]=0; /* real binding imports C7 clear */
    assert(mouse_time_settle(&a,2*p));
    assert(a.live[0]==7 && a.live[1]==-7);
    /* Partition exactness against absolute rational reference, across capture
     * boundaries, signs, latest levels and two independent axes. */
    for(unsigned seed=1;seed<=50;seed++) {
        uint32_t rng=seed;
        assert(mouse_time_reset(&a,0));
        int expected[2]={0,0};
        int delta[100][2];
        for(unsigned i=0;i<100;i++) {
            rng=rng*1664525u+1013904223u;
            int x=(int)(rng%31)-15,y=(int)((rng>>8)%31)-15;
            assert(mouse_time_admit(&a,event((i+1)*p-((i%3)*123),i,x,y,(i&1)?0x20:0xa0)));
            expected[0]+=x;expected[1]+=y;delta[i][0]=x;delta[i][1]=y;
        }
        assert(mouse_time_enable(&a,1));b=a;
        assert(mouse_time_settle(&a,102*p));
        uint64_t t=0;
        while(t<102*p) {
            rng=rng*1664525u+1013904223u;
            t+=1+rng%4000000000u;if(t>102*p)t=102*p;
            assert(mouse_time_settle(&b,t));
            /* Independent absolute rational oracle; one event per capture. */
            int oracle[2]={0,0};
            for(unsigned i=0;i<100;i++) {
                uint64_t start=(i+1)*p;
                uint64_t e=t<=start?0:t>=start+p?p:t-start;
                for(unsigned axis=0;axis<2;axis++) {
                    int d=delta[i][axis];
                    oracle[axis]+=(d<0?-1:1)*(int)((uint64_t)(d<0?-d:d)*e/p);
                }
            }
            assert(b.live[0]==oracle[0]&&b.live[1]==oracle[1]);
        }
        equal(&a,&b);
        assert(a.live[0]==expected[0] && a.live[1]==expected[1]);
    }
    /* Fine service partitions, with floor(abs(delta)*elapsed/P) authority. */
    assert(mouse_time_reset(&a,0));assert(mouse_time_admit(&a,event(p,0,113,-127,0xa0)));
    for(uint64_t t=0;t<=3*p;t+=1000000) {
        assert(mouse_time_settle(&a,t));
        uint64_t elapsed=t<=p?0:t>=2*p?p:t-p;
        assert(a.live[0]==(int)(113*elapsed/p));assert(a.live[1]==-(int)(127*elapsed/p));
    }
    /* No input: analytical million-tick collapse plus canonical capture phase. */
    assert(mouse_time_reset(&a,0));assert(mouse_time_enable(&a,1));b=a;
    assert(mouse_time_settle(&a,1000000*MOUSE_IRQ_Q));
    for(unsigned i=1;i<=1000;i++)assert(mouse_time_settle(&b,i*1000*MOUSE_IRQ_Q));
    equal(&a,&b);assert(a.expiries==1000000 && a.publications==1000000);
    assert(a.next_irq==1000001*MOUSE_IRQ_Q);
    for(unsigned k=0;k<4;k++) {
        assert(mouse_time_reset(&a,0));a.rate=k;assert(mouse_time_enable(&a,1));
        assert(mouse_time_settle(&a,(MOUSE_IRQ_Q<<k)-1));assert(!a.expiries);
        assert(mouse_time_settle(&a,MOUSE_IRQ_Q<<k));assert(a.expiries==1);
    }
    /* Disabled outstanding deadline survives, then retires without publication. */
    assert(mouse_time_reset(&a,0));assert(mouse_time_enable(&a,1));
    assert(mouse_time_enable(&a,0));assert(a.irq_pending);
    assert(mouse_time_settle(&a,MOUSE_IRQ_Q));assert(a.expiries==1&&!a.publications&&!a.irq_pending);
    /* Failure must not change time, queue, motion or publication counters. */
    old=a;assert(!mouse_time_settle(&a,MOUSE_TIME_LIMIT_Q+1));equal(&a,&old);
    assert(!mouse_time_settle(&a,0));equal(&a,&old);
    assert(!mouse_time_admit(&a,event(a.frontier,0,1,0,0xa0)));equal(&a,&old);
    assert(!mouse_time_admit(&a,event(a.frontier+1,0,32768,0,0xa0)));equal(&a,&old);
    assert(mouse_time_reset(&a,0));assert(mouse_time_admit(&a,event(p,0,32767,0,0xa0)));
    old=a;assert(!mouse_time_admit(&a,event(p,1,1,0,0xa0)));equal(&a,&old);
    assert(!mouse_time_admit(&a,event(p-1,1,0,0,0xa0)));equal(&a,&old);
    assert(!mouse_time_admit(&a,event(p,0,0,0,0xa0)));equal(&a,&old);
    assert(mouse_time_admit(&a,event(2*p,1,1,0,0xa0)));
    assert(mouse_time_enable(&a,1));old=a;
    assert(!mouse_time_settle(&a,3*p));equal(&a,&old); /* live overflow: no partial IRQ */
    assert(mouse_time_reset(&a,0));
    for(unsigned i=0;i<MOUSE_INPUT_CAPACITY;i++)assert(mouse_time_admit(&a,event(p,i,0,0,0xa0)));
    old=a;assert(!mouse_time_admit(&a,event(p,256,0,0,0xa0)));equal(&a,&old);
    puts("PASS_NORMALIZED_MOUSE_RATIONAL_PARTITION_AND_TRANSACTIONAL_DOMAIN");
    return 0;
}
