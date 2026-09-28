# SPDX-License-Identifier: MIT
"""Exact mode-2 assertions, separate from the unchanged N4 legacy contract."""
from gdc_contract import clocks, geometry, require
from gdc_machine_schedule import points


def verify_machine(records,capture,*,scan_class,profile_base,baseclock,multiple,schedule="canonical"):
    require(not capture['errors'],'capture errors')
    trace=capture['trace'];reads=capture['reads']
    require([t['case'] for t in trace]==list(range(1,29)) and len(reads)==56,'complete ordered observations')
    ref=points(scan_class,profile_base,schedule)
    by={r['case']:r for r in records}
    for r,t in zip(records,trace):
        c=r['case'];v=t['state']['values']
        require(v['pccore.baseclock']==baseclock and v['pccore.multiple']==multiple,'runtime identity')
        require(v['gdc_machine.time.base']==profile_base and v['np2cfg.RASTER']==0,'fixed display identity/admission')
        m,s=geometry(scan_class,c==27)
        require(t['state']['master_sync']==list(m) and t['state']['slave_sync']==list(s),'committed SYNC')
        expected=clocks(scan_class,profile_base,5,c==27)
        require(all(v['gdc.'+k]==x for k,x in expected.items()),'frozen M5 geometry clocks')
        h=int(v['gdc_machine.time.remaining']%expected['rasterclock']<expected['hsyncclock'])
        require(r['hblank_master']==r['hblank_slave']==h,'all selected H phases')
        require(r['master']&128 and r['slave']&128,'status identity')
        for port,key in [(96,'master'),(160,'slave')]:
            samples=[x for x in reads if x['case']==c and x['port']==port]
            require(len(samples)==1 and samples[0]['raw']==r[key],'actual IN return matches guest RAM')
        require(r['irq_count']==(0 if c<20 else 1 if c<23 else 2),'finite IRQ acceptance count')
        if c<=17:
            e=ref[c-1]['expected']
            require((r['vsync_master'],r['hblank_master'])==(e['vsync'],e['hblank']),'master exact phase')
            require((r['vsync_slave'],r['hblank_slave'])==(e['vsync'],e['hblank']),'slave exact phase')
            require(v['gdc_machine.time.remaining']==e['remaining'],'latched countdown')
        else:
            require(r['vsync_master']==r['vsync_slave']==int(c in (18,20,23,24,25,26)),'IRQ/SYNC sample V phase')
    require(by[16]['progress']-by[15]['progress']==32768,'CPU work')
    core='i286core.s' if 'i286core.s.clock' in trace[14]['state']['values'] else 'i386core.s'
    def position(t):
        v=t['state']['values']
        return (v[core+'.clock']+v[core+'.baseclock']-v[core+'.remainclock'])&0xffffffff
    require(0<((position(trace[15])-position(trace[14]))&0xffffffff)<0x80000000,'CPU ledger did not progress positively')
    fields=['gdc_machine.time.remaining','gdc_machine.time.fraction','gdc_machine.time.vsync','gdc_machine.time.ticks','gdc.vsyncint']
    require(all(trace[14]['state']['values'][k]==trace[15]['state']['values'][k] for k in fields),'GDC progressed during frozen-time CPU work')
    require((by[15]['irr']&4,by[15]['isr']&4)==(by[16]['irr']&4,by[16]['isr']&4),'IRQ2 changed during frozen CPU work')
    require(by[18]['imr']&4 and by[18]['irr']&4 and not by[19]['irr']&4,'masked pending/expiry')
    require(by[20]['isr']&4 and not by[20]['imr']&4,'accepted ISR')
    require(by[21]['isr']&4 and not by[21]['irr']&4,'ISR suppression')
    require(trace[20]['state']['values']['gdc_machine.time.transitions']-trace[19]['state']['values']['gdc_machine.time.transitions']>=4,'ISR across frames')
    require(not by[22]['isr']&4 and not by[22]['after_eoi']&4 and by[22]['eoi_count']==1,'specific EOI')
    h=by[23]
    require(h['hlt_entry']==0x1111 and h['hlt_wake']==0x2222 and h['saved_ip']==h['wake_ip'] and h['saved_cs']==0x2000 and h['saved_flags']&512 and h['handler_isr']&4,'architectural HLT wake')
    require(capture['halted_serviced'] and not by[24]['isr']&4 and by[24]['eoi_count']==2,'held HLT service / second EOI')
    require(by[26]['fifo_master']&4 and by[26]['fifo_slave']&4,'FIFO drain')
    held=[s for s in capture['services'] if s['label']=='CPU-held-time-advanced']
    require(len(held)==1 and held[0]['cpu_unchanged'] and held[0]['excluded_unchanged'],'held CPU / excluded-device isolation')
    require(held[0]['before']['values']['gdc_machine.time.vsync']==0 and held[0]['after']['values']['gdc_machine.time.vsync']==1,'held CPU independent V advance')
    huge=next(s for s in capture['services'] if s.get('case')==14 and s['label']=='selected-phase')
    work=huge['after']['values']['gdc_machine.finite_steps']-huge['before']['values']['gdc_machine.finite_steps']
    require(work<=7,'huge gap performed unbounded finite work')
    presentation=capture['presentation']
    require(presentation['gdc_unchanged'] and presentation['cpu_unchanged'],'presentation changed guest GDC/CPU')
    a=presentation['after']['values'];b=presentation['before']['values']
    if 'drawcount' in a:
        require(a['drawcount']==b['drawcount']+1,'latest host draw did not execute')
    require(a['gdc_machine.presentations']==b['gdc_machine.presentations']+1 and a['gdc_machine.presented']==a['gdc_machine.generation'],'one latest presentation')
    return dict(state='PASS_N4_GDC_MACHINE_TIME',records=28,direct_reads=56,huge_gap_finite_steps=work,
                authority='LEGACY_COMPATIBILITY_PROFILE',no_audio_assertion=True,
                live_realtime='NOT_QUALIFIED_BY_FAKE_TIME')
