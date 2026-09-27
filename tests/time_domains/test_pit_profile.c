/* SPDX-License-Identifier: MIT */
/* Compile twice: immutable parent sources and experimental sources.
 * Peripheral stubs do not implement PIT/PIC or the legacy scheduler. */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <io/iocore.h>
#include <legacycpu.h>
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <pit0_time.h>
#include "io/pit.c"
#include "io/pic.c"
UINT32 test_committed;
SINT32 test_slice,test_remaining;
int test_ei;
unsigned test_accepted;
struct test_pccore pccore;
struct test_pcstat pcstat;
struct test_gdc gdc;
struct test_rs232c rs232c;
struct test_beep g_beep;
unsigned beep_data[BEEPDATACOUNT],beep_time[BEEPDATACOUNT];
COMMNG cm_rs232c;
_PIT pit;
_PIC pic;
void beep_lheventset(int v){(void)v;}
void beep_hzset(unsigned v){(void)v;}
void beep_modeset(void){}
void rs232c_callback(void){}
void rs232c_open(void){}
unsigned board14_pitcount(void){return 0;}
#ifdef NP2_PIT_PIC_MACHINE_TIME
extern PIT0_SAMPLE pit0_fake_sample;
#endif
static unsigned elapsed,sequence;
static void advance(unsigned q)
{
    elapsed+=q;
#ifdef NP2_PIT_PIC_MACHINE_TIME
    unsigned numerator=pccore.cpumode?780:960;
    UINT32 before=test_committed;
    pit0_fake_sample.ns=((uint64_t)elapsed*78125+numerator-1)/numerator;
    pit0_machine_service();
    assert(before==test_committed);
    assert(!nevent_iswork(NEVENT_ITIMER) && !nevent_iswork(NEVENT_PICMASK));
#else
    while(legacy_cpu_device_now()<elapsed) {
        unsigned remain=elapsed-legacy_cpu_device_now();
        if (test_remaining<=0 || (unsigned)test_remaining<=remain) {
            test_remaining=0;nevent_progress();
        } else test_remaining-=(SINT32)remain;
    }
#endif
}
static void snapshot(unsigned op,unsigned arg)
{
    /* Byte-for-byte state plus current count and actual arbitration count. */
    printf("%u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u\n",
        sequence++,op,arg,elapsed,pit.ch[0].ctrl,pit.ch[0].flag,
        pit.ch[0].value,pit.ch[0].latch,pit.ch[0].stat,getcount(pit.ch),
        pic.pi[0].irr,pic.pi[0].isr,pic.pi[0].imr,pic.pi[0].pry,
        pic.pi[0].ocw3,pic.pi[1].irr,test_accepted,gdc.vsyncint);
}
static void operation(unsigned op,unsigned arg)
{
    switch(op){
    case 0:advance(arg);break;
    case 1:pit_o77(0x77,arg);break;
    case 2:pit_o71(0x71,arg);break;
    case 3:arg=pit_i71(0x71);break;
    case 4:pic_o02(2,arg);break;
    case 5:pic_o00(0,arg);break;
    case 6:test_ei=arg;pic_irq();break;
    case 7:pic_setirq(arg);break; /* controlled legacy other IRQ */
    case 8:arg=pic_i00(0);break;
    case 9:arg=pic_i02(2);break;
    }
    snapshot(op,arg);
}
static void reset(unsigned mult,unsigned clock8)
{
    nevent_allreset();test_committed=0;test_slice=0;test_remaining=0;
    elapsed=0;test_accepted=0;test_ei=0;memset(&gdc,0,sizeof(gdc));
    pccore.multiple=mult;pccore.cpumode=clock8;
    pccore.realclock=(clock8?1996800:2457600)*mult;
#ifdef NP2_PIT_PIC_MACHINE_TIME
    pit0_fake_sample.ns=0;pit0_fake_sample.valid=1;
#endif
    pic_reset(NULL);itimer_reset(NULL);
    nevent_get1stevent();
}
static unsigned rng=8128;
static unsigned random32(void){rng=rng*1664525u+1013904223u;return rng;}
int main(int argc,char **argv)
{
    unsigned multiple=argc>1?(unsigned)atoi(argv[1]):5;
    unsigned clock8=argc>2?(unsigned)atoi(argv[2]):0;
    unsigned modes[]={0x30,0x34,0x36,0x32,0x14,0x24};
    unsigned counts[]={0,1,8,9,10,11,12,255,256,65535};
    unsigned m,c,k;
    for(m=0;m<6;m++)for(c=0;c<10;c++){
        unsigned n=counts[c],period=(n>8?n:65536)*5;
        reset(multiple,clock8);snapshot(99,c);
        operation(4,255);operation(1,modes[m]);
        operation(2,n&255);operation(0,1);operation(3,0);
        operation(2,n>>8);
        operation(0,0);operation(0,4);operation(3,0);
        operation(0,period-5);operation(8,0);
        operation(0,10); /* owner count9: at exactly 2 clocks after expiry */
        operation(8,0);operation(4,254);operation(6,1);
        operation(0,1);operation(6,1);operation(5,0x20);
        operation(0,period*4+5);operation(6,1);operation(6,1);
        operation(1,0);operation(0,7);operation(3,0);
        operation(1,0);operation(3,0);operation(3,0);
        operation(1,0xc2);operation(3,0);operation(3,0);operation(3,0);
        operation(1,0x36);operation(2,9);operation(2,0);
        operation(0,45);operation(7,1);operation(4,252);
        operation(5,0x20);operation(6,1);operation(5,0x20);operation(6,1);
        /* Arbitrary programming, active partial rewrite, masks, ISR/EOI,
         * status/readback and independent legacy IRQ publication. */
        for(k=0;k<800;k++){
            unsigned r=random32(),op=(r>>16)%10,arg=random32();
            switch(op){
            case 0:arg%=2000;break;
            case 1: {unsigned ctrl[]={0,0x30,0x34,0x36,0x32,0x14,0x24,0xc2,0xd2,0xe2};arg=ctrl[arg%10];break;}
            case 2:arg&=255;break;
            case 4:arg=(arg&1)?255:252;break;
            case 5: {unsigned ctrl[]={0x20,0x60,0x61,0x0a,0x0b,0x11};arg=ctrl[arg%6];break;}
            case 6:arg&=1;break;
            case 7:arg=1;break;
            default:arg=0;
            }
            operation(op,arg);
        }
    }
    return 0;
}
