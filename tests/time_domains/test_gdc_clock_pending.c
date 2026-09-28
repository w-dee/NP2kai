/* SPDX-License-Identifier: MIT */
/* Appended to actual GDC/PIC binding by tools/test_gdc_binding.py.
 * Renderer/cache/bank peripherals are stubs. Clock writes and resets are the
 * mechanically extracted real handlers. This tests state, not screen pixels. */
static void renderer_consumes_ext(void)
{
    /* Exact consumption performed by experimental drawscreen. */
    gdcs.grphdisp &= ~GDCSCRN_EXT;
}
static unsigned derived_pitch(void)
{
    /* Same derivation as makegrphex, no special-case product path. */
    unsigned pitch=gdc.s.para[GDC_PITCH];
    if(!(gdc.clock & 0x80)) pitch <<= 1;
    return pitch & 0xfe;
}
static unsigned test_clock_pending(void)
{
    unsigned checks=0;
    for(unsigned sync=0;sync<2;sync++) for(unsigned order=0;order<4;order++) {
        setup(0,sync);unsigned d=gdc.dispclock,f=d+gdc.vsyncclock;
        unsigned frontier=sync?d:f;
        gdc.s.para[GDC_PITCH]=128;
        gdc_o6a(0x6a,0x83);gdc_o6a(0x6a,0x85);
        assert(gdc.clock==3 && gdc_machine.clock_pending && derived_pitch()==0);
        UINT32 c=test_committed;SINT32 b=test_slice,r=test_remaining;
        advance_q(frontier-1);
        assert(gdc.clock==3 && gdc_machine.clock_pending);checks++;
        if(order==1)renderer_consumes_ext();
        if(order==2)for(unsigned i=0;i<8;i++)renderer_consumes_ext();
        /* order 0: pipeline first; order 3: no rendering at all. */
        advance_q(frontier);
        assert(gdc.clock==0x83 && !gdc_machine.clock_pending && derived_pitch()==128);
        assert(test_committed==c && test_slice==b && test_remaining==r);checks++;
        if(order==0)renderer_consumes_ext();
        _GDC snapshot=gdc;
        for(unsigned i=0;i<8;i++)advance_q(frontier);
        assert(!memcmp(&snapshot,&gdc,sizeof(gdc)) && !gdc_machine.clock_pending);checks++;
        advance_q(frontier+3*f);
        assert(gdc.clock==0x83 && !gdc_machine.clock_pending);checks++;
        /* Turn bit 7 off again at the NEXT selected frontier, never forever on. */
        gdc_o6a(0x6a,0x84);
        assert(gdc.clock==0x81 && gdc_machine.clock_pending);
        renderer_consumes_ext();advance_q(frontier+4*f-1);
        assert(gdc.clock==0x81 && gdc_machine.clock_pending);
        advance_q(frontier+4*f);
        assert(gdc.clock==1 && !gdc_machine.clock_pending && derived_pitch()==0);checks++;
    }
    /* All four actual I/O producers, same-value writes, and latest-write wins. */
    for(unsigned command=0x82;command<=0x85;command++) {
        setup(0,1);gdc.clock=0x83;
        gdc_o6a(0x6a,command);assert(gdc_machine.clock_pending);checks++;
        gdc_o6a(0x6a,command);assert(gdc_machine.clock_pending);checks++;
        gdc_o6a(0x6a,0x83);gdc_o6a(0x6a,0x85);gdc_o6a(0x6a,0x82);
        renderer_consumes_ext();advance_q(gdc.dispclock);
        assert(gdc.clock==2 && !gdc_machine.clock_pending);checks++;
    }
    /* Independent truth table over all reachable raw clock combinations,
     * every actual I/O command, both frontiers and multiple pitch values. */
    for(unsigned high=0;high<2;high++) for(unsigned low=0;low<4;low++)
    for(unsigned command=0x82;command<=0x85;command++)
    for(unsigned sync=0;sync<2;sync++) for(unsigned render=0;render<3;render++)
    for(unsigned pitch_index=0;pitch_index<3;pitch_index++) {
        static const unsigned pitches[]={40,80,128};
        setup(0,sync);gdc.clock=low+128*high;
        gdc.s.para[GDC_PITCH]=pitches[pitch_index];
        gdc_o6a(0x6a,command);
        unsigned raw_low=gdc.clock & 3;
        unsigned expected=raw_low+(raw_low==3?128:0);
        for(unsigned i=0;i<render*3;i++)renderer_consumes_ext();
        advance_q(gdc.dispclock+(sync?0:gdc.vsyncclock));
        assert(gdc.clock==expected && !gdc_machine.clock_pending);
        assert(derived_pitch()==((pitches[pitch_index]*(raw_low==3?1:2))&254));
        checks++;
    }
    /* Non-clock dirt does not introduce a clock obligation. */
    setup(0,1);gdcs.grphdisp|=GDCSCRN_EXT;gdc.s.para[GDC_PITCH]=80;
    gdc_o6a(0x6a,0x41);advance_q(gdc.dispclock);
    assert(!gdc_machine.clock_pending && gdc.clock==0 && derived_pitch()==160);checks++;
    /* Huge gap: bounded existing work, one coalesced clock obligation. */
    setup(0,1);gdc_o6a(0x6a,0x83);gdc_o6a(0x6a,0x85);renderer_consumes_ext();
    advance_q((uint64_t)(gdc.dispclock+gdc.vsyncclock)*1000000000000ULL);
    assert(gdc.clock==0x83 && !gdc_machine.clock_pending && gdc_machine.finite_steps<=7);checks++;
    /* Actual BIOS display reset, actual cold GDC reset, independent object reset. */
    for(unsigned reset=0;reset<3;reset++) {
        setup(0,1);gdc_o6a(0x6a,0x83);gdc_o6a(0x6a,0x85);
        assert(gdc_machine.clock_pending);
        if(reset==0)gdc_biosreset();
        else if(reset==1)gdc_reset(&np2cfg);
        else gdc_machine_reset();
        assert(!gdc_machine.clock_pending);checks++;
        if(reset<2)assert(gdc.clock==0 && gdc.m.para[GDC_PITCH]==80 && gdc.s.para[GDC_PITCH]==40);
        if(reset==2)gdc.clock=0; /* independent owner reset does not reset guest registers */
        gdc_updateclock();
        advance_q(gdc.dispclock);
        assert(gdc.clock==0 && !gdc_machine.clock_pending);checks++;
        gdc_o6a(0x6a,0x83);gdc_o6a(0x6a,0x85);renderer_consumes_ext();
        advance_q((uint64_t)gdc.dispclock*2+gdc.vsyncclock);
        assert(gdc.clock==0x83 && !gdc_machine.clock_pending);checks++;
    }
    return checks;
}
