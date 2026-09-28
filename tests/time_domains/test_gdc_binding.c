/* SPDX-License-Identifier: MIT */
/* Appended to mechanically extracted production functions by the host runner. */
static const unsigned char master24[8]={16,78,7,37,7,7,144,101};
static uint64_t ns_tick(uint64_t q)
{
    /* q in these tests stays within the supported uint64 ns range. */
    unsigned rate=NP2_GDC_PROFILE_BASE*5u;
    return (q/rate)*1000000000u + ((q%rate)*1000000000u+rate-1)/rate;
}
static void advance_q(uint64_t q)
{
    gdc_fake_sample.ns=ns_tick(q);
#ifdef NP2_PIT_PIC_MACHINE_TIME
    pit0_fake_sample=gdc_fake_sample.valid ? (PIT0_SAMPLE){gdc_fake_sample.ns,1} : (PIT0_SAMPLE){0,0};
#endif
    gdc_machine_service();
}
static void setup(unsigned bits,int sync)
{
    nevent_allreset();test_committed=123;test_slice=100000;test_remaining=80000;
    test_ei=0;test_accepted=test_vector=0;
    memset(&gdc,0,sizeof(gdc));memset(&gdcs,0,sizeof(gdcs));memset(&tramflag,0,sizeof(tramflag));
    memcpy(gdc.m.para,master24,8);
    pccore.baseclock=2457600;pccore.multiple=4;pccore.realclock=pccore.baseclock*4;pccore.cpumode=0;
    np2cfg=(NP2CFG){{1,2,6,3,8,4},sync,0,0};
    pic_reset(NULL);itimer_reset(NULL);
    gdc_fake_sample=(GDC_SAMPLE){0,1};
#ifdef NP2_PIT_PIC_MACHINE_TIME
    pit0_fake_sample=(PIT0_SAMPLE){0,1};pit0_machine_reset();
#endif
    gdc_machine_reset();gdc_updateclock();
    pic.pi[0].irr=(bits&2)?4:0;pic.pi[0].isr=(bits&4)?4:0;pic.pi[0].imr=(bits&8)?255:251;
    gdc.vsyncint=bits&1;
    memset(work_calls,0,sizeof(work_calls));
}
static unsigned bits(void)
{
    return gdc.vsyncint | ((pic.pi[0].irr&4)?2:0) | ((pic.pi[0].isr&4)?4:0) | ((pic.pi[0].imr&4)?8:0);
}
static unsigned model_edge(unsigned b,int v)
{
    if (v && (b&1)) {
        if (b&4) b=(b|1)&~2u;
        else b=(b|2)&~1u;
    } else if (!v && (b&2)) b=(b|1)&~2u;
    return b;
}
static void blink_reference(TRAM_T *t,unsigned threshold,unsigned n)
{
    while(n--) {
        t->timing++;
        if(t->timing>=threshold){t->timing=0;t->count++;t->renewal|=((t->count^2)&2)|1;}
    }
}
int main(int argc,char **argv)
{
    unsigned checks=0;
    if(argc==2 && !strcmp(argv[1],"benchmark")) {
        const uint64_t counts[]={0,1,5,1000000000000ULL};
        printf("[ ");
        for(unsigned k=0;k<4;k++) {
            setup(1,1);GDC_MACHINE initial=gdc_machine;
            uint64_t ns=ns_tick(counts[k]*(gdc.dispclock+gdc.vsyncclock));
            clock_t start=clock();
            for(unsigned j=0;j<100000;j++) {
                gdc_machine=initial;gdc.vsyncint=1;pic.pi[0].irr=pic.pi[0].isr=0;
                gdc_fake_sample=(GDC_SAMPLE){ns,1};
                if(k)gdc_machine_service();else (void)gdc_i60(0x60);
            }
            double per=(double)(clock()-start)*1e9/CLOCKS_PER_SEC/100000;
            printf("%s{\"frames\":%llu,\"ns_per_reset_and_service\":%.2f,\"finite_steps\":%llu}",k?",":"",
                   (unsigned long long)counts[k],per,(unsigned long long)gdc_machine.finite_steps);
        }
        printf(" ]\n");return 0;
    }

    if(argc==2 && !strcmp(argv[1],"reject-raster")) {setup(0,1);np2cfg.RASTER=1;gdc_machine_service();return 2;}
    for(unsigned b=0;b<16;b++) for(unsigned frames=0;frames<20;frames++) for(unsigned end=0;end<2;end++) {
        setup(b,1);unsigned d=gdc.dispclock,f=d+gdc.vsyncclock,expected=b;
        for(unsigned n=0;n<frames;n++){expected=model_edge(expected,1);expected=model_edge(expected,0);}
        if(end)expected=model_edge(expected,1);
        UINT32 k=test_committed;SINT32 sb=test_slice,sr=test_remaining;
        advance_q((uint64_t)frames*f+(end?d:0));assert(bits()==expected);
        assert(test_committed==k && test_slice==sb && test_remaining==sr);
        assert(work_calls[0]+work_calls[1]<=4);checks++;
    }
    for(unsigned b=0;b<16;b++) {
        setup(b,1);uint64_t f=(uint64_t)gdc.dispclock+gdc.vsyncclock;
        unsigned expected=model_edge(model_edge(b,1),0);
        advance_q(f*1000000000000ULL);
        assert(bits()==expected && gdc_machine.finite_steps<=7);checks++;
    }
    /* The exact production blink routine matches byte wrap/threshold changes. */
    setup(0,1);
    for(unsigned threshold=2;threshold<=64;threshold+=2) for(unsigned initial=0;initial<256;initial++) {
        unsigned encoded=threshold==64?0:threshold;
        gdc.m.para[GDC_CSRFORM+1]=(encoded<<5)&255;
        gdc.m.para[GDC_CSRFORM+2]=(encoded<<5)>>8;
        tramflag=(TRAM_T){0};tramflag.timing=initial;tramflag.count=253;
        TRAM_T expected=tramflag;blink_reference(&expected,threshold,513);
        gdc_machine_blink(513);
        assert(tramflag.timing==expected.timing && tramflag.count==expected.count && tramflag.renewal==expected.renewal);checks++;
    }
    for(int sync=0;sync<=1;sync++) {
        setup(0,sync);unsigned d=gdc.dispclock,v=gdc.vsyncclock;
        gdc.m.para[4]++;gdcs.textdisp|=GDCSCRN_EXT;
        advance_q(d);assert(gdc_machine.time.remaining==v);
        if(sync)assert(gdc_machine.committed_sync[4]==8);
        else assert(gdc_machine.committed_sync[4]==7);
        advance_q((uint64_t)d+v);
        assert(gdc_machine.committed_sync[4]==8 && gdc_machine.time.remaining==gdc_machine.time.profile.display);checks++;
    }
    /* Actual recognized polling bytes: ON must not force-yield CPU budget.
     * The extracted production policy controls SEARCH_SYNC/TURE_SYNC. */
    setup(0,1);test_inp=0x100;mem[0x100]=0xa8;mem[0x101]=0x20;
    mem[0x102]=0x74;mem[0x103]=0xfa;
    SINT32 search_before=test_remaining;
    unsigned old_status=gdc_i60(0x60);
    assert(!(old_status&0x20) && test_remaining==search_before);
    assert(gdc_i60(0x60)==old_status && test_remaining==search_before);
    advance_q(gdc.dispclock);
    assert((gdc_i60(0x60)&0x20) && test_remaining==search_before);checks+=3;
    /* Actual mixed status keeps legacy busy while machine scan advances. */
    setup(0,1);gdc.s_drawing=8;gdc.s.cnt=1;
    unsigned first_status=gdc_ia0(0xa0);assert((first_status&8) && !(first_status&4));
    assert(gdc_ia0(0xa0)&4);
    advance_q((uint64_t)(gdc.dispclock+gdc.vsyncclock)*1000000000000ULL+gdc.dispclock);
    assert((gdc_ia0(0xa0)&0x28)==0x28 && gdc.s_drawing==8);checks+=3;
    /* Actual TRAM read selects new phase then debits the existing charge. */
    setup(0,1);unsigned d=gdc.dispclock;
    mem[0xa0000]=0x55;SINT32 before=test_remaining;
    assert(memtram_rd8(0xa0000)==0x55 && before-test_remaining==1);
    advance_q(d);before=test_remaining;
    assert(memtram_rd8(0xa0000)==0x55 && before-test_remaining==2);
    assert(MEMWAIT_VRAM==3 && MEMWAIT_GRCG==4);checks+=2;
#ifdef NP2_PIT_PIC_MACHINE_TIME
    /* Both real producers materialize requests before existing arbitration. */
    setup(1,1);pic_o02(2,250);pit_o77(0x77,0x34);pit_o71(0x71,9);pit_o71(0x71,0);
    gdc_fake_sample.ns=ns_tick(gdc.dispclock);pit0_fake_sample.ns=gdc_fake_sample.ns;
    test_ei=1;pic_irq();assert(test_vector==8 && (pic.pi[0].irr&4));
    assert(pit0_machine_time.anchor_ns==gdc_machine.time.anchor_ns);
    pic_o00(0,0x60);pic_irq();assert(test_vector==10 && test_accepted==2);checks++;
#endif
    unsigned clock_checks=test_clock_pending();
    printf("PASS %u effective-clock pending ownership checks\n",clock_checks);
    printf("PASS %u checks: IRQ table/huge gap, bounded work, blink wrap, SYNC latch, real wait debit, composition\n",checks);
    return 0;
}
