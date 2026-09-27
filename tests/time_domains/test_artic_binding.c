/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <io/iocore.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#if defined(NP2_ARTIC_MACHINE_TIME)
#include "artic_time.h"
extern ARTIC_SAMPLE artic_fake_sample;
#endif
UINT32 CPU_CLOCK;
SINT32 CPU_BASECLOCK, CPU_REMCLOCK;
struct PCCORE_TEST pccore;
_ARTIC artic;
void (*test_out[256])(UINT,REG8);
REG8 (*test_in[256])(UINT);
#include "../../io/artic.c"

int main(void)
{
    pccore.multiple=1; artic_bind(); artic_reset(0);
    assert(sizeof(artic)==8);
#if defined(NP2_ARTIC_MACHINE_TIME)
    artic_fake_sample=(ARTIC_SAMPLE){20000000,1};
    /* Freeze the entire CPU ledger, not merely instruction retirement. */
    UINT32 c=CPU_CLOCK; SINT32 b=CPU_BASECLOCK,r=CPU_REMCLOCK;
    assert(artic_r16(0x5c)==6144);
    assert(CPU_CLOCK==c && CPU_BASECLOCK==b && CPU_REMCLOCK==r);
    for(unsigned mode=0;mode<2;mode++) for(unsigned m=1;m<=20;m++) {
        pccore.cpumode=mode?CPUMODE_8MHZ:0;pccore.multiple=m;
        CPU_CLOCK+=1234;artic_callback();
        assert(artic_r16(0x5c)==6144);
    }
    artic_fake_sample.ns=1000000000;
    assert(artic_r16(0x5c)==(307200&65535));
    assert(artic_r16(0x5e)==(307200>>8));
    artic_fake_sample.valid=0;
    CPU_CLOCK+=1000; assert(artic_r16(0x5c)==(307200&65535));
    artic_fake_sample.valid=1;artic_fake_sample.ns=0;
    assert(artic_r16(0x5c)==(307200&65535));
    assert(artic_machine_time.rejected==2);
    artic_fake_sample.ns=200000000000ull;
    uint32_t phase=artic_machine_read();
    assert(test_in[0x5c](0)==(phase&255));
    assert(test_in[0x5d](0)==((phase>>8)&255));
    assert(test_in[0x5e](0)==((phase>>8)&255));
    assert(test_in[0x5f](0)==((phase>>16)&255));
    assert(artic_r16(0x5d)==artic_r16(0x5c));
    assert(artic_r16(0x5f)==artic_r16(0x5e));
    CPU_REMCLOCK=100;test_out[0x5f](0x5f,123);assert(CPU_REMCLOCK==80);
    assert(artic_machine_read()==phase);
    artic_reset(0);assert(!artic_machine_time.phase && !artic_machine_time.remainder);
    assert(artic_machine_time.anchor_ns==artic_fake_sample.ns);
    /* Accepted advancement across multiplier/base-mode changes is continuous. */
    for (unsigned mode=0;mode<2;mode++) for (unsigned m=1;m<=20;m++) {
        uint32_t prior=artic_machine_time.phase;
        pccore.cpumode=mode?CPUMODE_8MHZ:0;pccore.multiple=m;
        artic_fake_sample.ns+=20000000;
        assert(artic_machine_read()==((prior+6144)&0xffffff));
    }
    puts("PASS actual experimental ARTIC binding F08-F14,F16-F17; CPU frozen and no CPU fallback");
#else
    for(unsigned mode=0;mode<2;mode++) for(unsigned m=1;m<=20;m++) {
        pccore.cpumode=mode?CPUMODE_8MHZ:0;pccore.multiple=m;artic_reset(0);
        for(unsigned c=0;c<10000;c+=7) {
            CPU_CLOCK=c;unsigned expect=2*c/((mode?13:16)*m);
            assert(artic_getcnt()==expect);artic_callback();
            assert((unsigned)artic.counter==expect);
        }
    }
    pccore.multiple=1;pccore.cpumode=0;CPU_CLOCK=0;artic.lastclk2=0;artic.counter=0xabcdef;
    assert(test_in[0x5c](0)==0xef && test_in[0x5d](0)==0xcd);
    assert(test_in[0x5e](0)==0xcd && test_in[0x5f](0)==0xab);
    assert(artic_r16(0x5c)==0xcdef && artic_r16(0x5d)==0xcdef);
    assert(artic_r16(0x5e)==0xabcd && artic_r16(0x5f)==0xabcd);
    CPU_REMCLOCK=100;test_out[0x5f](0x5f,0);assert(CPU_REMCLOCK==80);
    puts("PASS legacy safe-range selection, aliases and OUT005F debit (F17)");
#endif
}
