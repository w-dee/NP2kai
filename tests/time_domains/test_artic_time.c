/* SPDX-License-Identifier: MIT */
#include "artic_time.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static void at(ARTIC_TIME *s, uint64_t ns)
{
    ARTIC_SAMPLE v = {ns, 1};
    assert(artic_time_observe(s, v));
}
static void zero(ARTIC_TIME *s)
{
    artic_time_reset(s);
    at(s, 0);
}
static void reference(const ARTIC_TIME *s, uint64_t ns)
{
    __uint128_t n = (__uint128_t)ns * 307200u;
    assert(s->phase == (uint32_t)((n / 1000000000u) & 0xffffffu));
    assert((__uint128_t)s->remainder * 1000000000u ==
           (n % 1000000000u) * 78125u);
}
int main(void)
{
    ARTIC_TIME a, b, before;
    uint64_t now = 0, seed = 98;
    const uint64_t times[] = {0, 3255, 3256, 5000000, 20000000, 1000000000,
        54613333333ull, 54613333334ull, 200000000000ull, UINT64_MAX};
    for (unsigned i=0; i<sizeof(times)/sizeof(times[0]); ++i) {
        zero(&a); at(&a,times[i]); reference(&a,times[i]);
        before=a; at(&a,times[i]); assert(!memcmp(&a,&before,sizeof(a)));
    }
    zero(&a);
    for (unsigned i=0; i<10000; ++i) {
        seed=seed*6364136223846793005ull+1;
        now+=(seed>>32)%1000000000u;
        at(&a,now); reference(&a,now);
    }
    zero(&b); at(&b,now);
    assert(a.phase==b.phase && a.remainder==b.remainder);
    before=a;
    assert(!artic_time_observe(&a,(ARTIC_SAMPLE){0,0}));
    assert(!artic_time_observe(&a,(ARTIC_SAMPLE){now-1,1}));
    assert(a.phase==before.phase && a.remainder==before.remainder && a.anchor_ns==now);
    assert(a.rejected==2);
    a.rejected=UINT64_MAX;
    assert(!artic_time_observe(&a,(ARTIC_SAMPLE){0,0}));
    assert(a.rejected==UINT64_MAX);
    at(&a,now+20000000); assert(a.phase==((before.phase+6144)&0xffffff));
    artic_time_reset(&a);
    assert(!a.phase && !a.remainder && !a.anchored && !a.rejected);
    assert(!artic_time_observe(&a,(ARTIC_SAMPLE){0,0}));
    at(&a,UINT64_MAX-20000000); assert(!a.phase);
    at(&a,UINT64_MAX); assert(a.phase==6144);
    puts("PASS rational/fraction/partition/wrap/uint64/invalid/reset (F01-F07,F15-F16)");
}
