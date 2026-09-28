# SPDX-License-Identifier: MIT
# Executed by GDB against the complete production emulator.
import gdb,json,time
from pathlib import Path
p=json.loads(Path(PARAMETERS).read_text());out=Path(p['out']);fake=p['mode']=='fake'
core='i286core.s' if p['backend']=='i286' else 'i386core.s'
num=lambda e:int(gdb.parse_and_eval(e))
def call(e):return gdb.parse_and_eval(e)
def setv(e,v):gdb.execute('set variable '+e+' = '+str(v),to_string=True)
def blob(e):
    v=gdb.parse_and_eval(e);return bytes(gdb.selected_inferior().read_memory(v.address,v.type.sizeof)).hex()
def io(port,data):
    # Invoke the actual bound device handlers with CPU held. The dispatcher's
    # CPU wait debit belongs to the real-guest fixture, not this timer timeline.
    handler={0x188:'opna_o188',0x18a:'opna_o18a'}[port]
    call('%s(%d,%d)'%(handler,port,data))
def write(reg,data):
    # Differential schedules start on an exactly representable base-clock point.
    # Arbitrary nanosecond starts are covered separately in the fake fixture.
    if reg==0x27 and (data & 3 & ~num('g_opna[0].s.reg[0x27]')):
        numerator=156 if p['baseclock']==1996800 else 192
        advance((-q)%numerator)
    io(0x188,reg);io(0x18a,data)
def read():return num('opna_i188(0x188)')
def period(a,b):
    k=1248 if p['baseclock']==1996800 else 1536
    return (18*(1024-a)*k//625,288*(256-b)*k//625)
def values(a,b):write(0x24,a>>2);write(0x25,a&3);write(0x26,b)
q=0;rows=[];matrix=[]
def reset():
    global q
    q=0
    if fake:setv('opna_timer_fake_sample.ns',0)
    # Reset actual peripherals, isolate unrelated NEVENT devices while CPU is held.
    call('nevent_allreset()')
    call('pcm86_reset()')
    call('board86_reset(&np2cfg,0)')
    call('board86_bind()')
    call('pic_reset(&np2cfg)')
    setv(core+'.clock',0);setv(core+'.baseclock',0);setv(core+'.remainclock',0)
    call('nevent_get1stevent()')
    assert num('g_nSoundID')==4 and num('enable_fmgen')==0
    assert num('g_opna[0].s.cCaps')==0x9f and num('g_opna[0].s.irq')==12
    assert read()==0
    assert num('g_pcm86.fifo')&0xa0==0 and num('g_pcm86.reqirq')==num('g_pcm86.irqflag')==0
    assert num('g_pcm86.realbuf')==num('g_pcm86.virbuf')==0
    assert num('nevent_iswork(25)')==0
    if fake:assert num('opna_timer_machine.time.timer[0].active')==num('opna_timer_machine.time.timer[1].active')==0

def advance(delta):
    global q
    q+=delta
    if fake:
        ns=(q*10**9+p['baseclock']-1)//p['baseclock']
        setv('opna_timer_fake_sample.ns',ns)
        before=[blob(x) for x in [core,'g_nevent','g_pcm86','gdc','dmac','artic']]
        call('opna_timer_machine_service()')
        assert before==[blob(x) for x in [core,'g_nevent','g_pcm86','gdc','dmac','artic']]
        assert num('nevent_iswork(5)')==num('nevent_iswork(6)')==0
    else:
        target=q*p['multiple']
        for count in range(10000):
            now=num(core+'.clock')+num(core+'.baseclock')-num(core+'.remainclock')
            if now>=target:break
            rem=num(core+'.remainclock')
            if rem<=target-now:
                setv(core+'.remainclock',0);call('nevent_progress()')
            else:setv(core+'.remainclock',rem-(target-now))
        else:raise AssertionError('legacy bounded schedule overflow')
        assert now==target or num(core+'.clock')+num(core+'.baseclock')-num(core+'.remainclock')==target

def snap(label):
    rows.append(dict(label=label,q=q,status=read(),reg27=num('g_opna[0].s.reg[0x27]'),
        irr=[num('pic.pi[%d].irr'%i) for i in range(2)],isr=[num('pic.pi[%d].isr'%i) for i in range(2)]))

gdb.Breakpoint('pccore_exec',internal=True)
gdb.execute('run',to_string=True)
assert num('g_nSoundID')==4
if p.get('negative'):
    assert fake
    case=p['negative'];code={'board':1,'fmgen':2,'adpcm':3,'csm':4,'pcm':5,'base':6}[case]
    try:
        if case=='board':call('opna_timer_machine_admit(0x20)')
        elif case=='fmgen':
            setv('enable_fmgen',1);call('opna_timer_machine_service()')
        elif case=='adpcm':
            setv('g_opna[0].s.cCaps',0xbf);call('opna_timer_machine_service()')
        elif case=='csm':write(0x27,0x80)
        elif case=='pcm':
            call('iocore_out8(0xa468,0x80)');call('opna_timer_machine_service()')
        else:
            setv('pccore.baseclock',12345);call('opna_timer_machine_reset()')
    except gdb.error:pass # Expected abort from the explicit scope gate.
    assert num('opna_timer_machine.admission_error')==code
    if case=='csm':assert num('g_opna[0].s.reg[0x27]')==0
    (out/'report.json').write_text(json.dumps(dict(result='PASS',negative=case,admission_error=code,claim='outside N6 scope rejected explicitly'))+'\n')
    gdb.execute('kill',to_string=True);gdb.execute('quit')
for a,b in [(1023,255),(0,0),(1022,254),(992,250),(512,128),(127,15)]:
    reset();pa,pb=period(a,b);values(a,b)
    write(0x27,5);snap('A-start')
    advance(pa//2);write(0x27,5);advance(pa-pa//2-1);snap('A-Dminus')
    assert read()==0
    advance(1);snap('A-D');assert read()==1
    advance(1);snap('A-Dplus');write(0x27,0);snap('A-stop-latched');assert read()==1
    write(0x27,0x10);assert read()==0 and num('g_opna[0].s.reg[0x27]')==0;snap('A-clear-stopped')
    write(0x27,0xa);advance(pb-1);assert read()==0;snap('B-Dminus')
    advance(1);assert read()==2;snap('B-D')
    write(0x27,0x2a);assert read()==0;snap('B-clear-running')
    advance(pb);assert read()==2;snap('B-rearm')
    matrix.append('periods-%d-%d'%(a,b))
# Current deadline survives register mutation; subsequent reload uses new period.
for channel in range(2):
    reset();values(512,128);p1=period(512,128)[channel];p2=period(1023,255)[channel]
    ctl=(1<<channel)|(4<<channel);write(0x27,ctl)
    advance(p1//2);values(1023,255);write(0x27,ctl);snap('rewrite-and-repeat-start-running')
    advance(p1-p1//2-1);assert read()==0;advance(1);assert read()==1<<channel;snap('old-expiry')
    write(0x27,ctl|(0x10<<channel));advance(p2-1);assert read()==0
    advance(1);assert read()==1<<channel;snap('new-rearm')
    matrix.append('running-value-%d'%channel)
# Timer continues with status disabled, then enabling does not synthesize expiry.
reset();values(1008,255);pa,pb=period(1008,255);assert pa==pb
write(0x27,3);advance(pa*3);assert read()==0;snap('disabled-status')
write(0x27,15);assert read()==0;advance(pa);assert read()==3;snap('simultaneous')
write(0x27,0x1f);assert read()==2 and not(num('pic.pi[1].irr')&16);snap('clear-A-shared-IRQ-quirk')
advance(pa);assert read()==3 and num('pic.pi[1].irr')&16;snap('A-relatch')
write(0x27,3);call('pic_resetirq(12)');advance(pa)
assert read()==3 and not(num('pic.pi[1].irr')&16);snap('disable-status-while-latched')
write(0x27,0);assert read()==3;snap('stop-both')
write(0x27,0x30);assert read()==0;write(0x27,15);advance(pa);assert read()==3;snap('restart')
matrix.extend(['status-enable','simultaneous','shared-IRQ-clear','restart'])
for a,b in [(1023,255),(0,255)]:
    reset();values(a,b);pa,pb=period(a,b);write(0x27,15)
    advance(min(pa,pb));snap('near-first');assert read()==(1 if pa<pb else 2)
    advance(abs(pa-pb));snap('near-second');assert read()==3
matrix.append('both-expiry-orders')
for first in [5,10]:
    reset();values(1008,255);pa,pb=period(1008,255)
    write(0x27,first);write(0x27,15);advance(pa)
    assert read()==3;snap('tie-insertion-%d'%first)
    # A request consumed/reset while status stays latched is not regenerated.
    call('pic_resetirq(12)');advance(pa*3)
    assert read()==3 and not(num('pic.pi[1].irr')&16)
    snap('already-latched-no-republication')
matrix.extend(['reverse-tie-insertion','already-latched-no-republication'])
# Equal-time clear/write: materialize previous state at the I/O boundary.
reset();values(1023,255);pa,pb=period(1023,255);write(0x27,5);advance(pa)
write(0x27,0x15);assert read()==0;snap('equal-time-clear')
values(512,128);advance(pa);assert read()==1;snap('equal-time-rewrite-uses-old-rearm')
matrix.append('same-time-I/O')
if fake:
    reset();values(1023,255);write(0x27,15)
    for i in range(40):assert read()==0
    before=blob('opna_timer_machine.time.timer')
    setv(core+'.clock',num(core+'.clock')+10000000)
    assert read()==0 and before==blob('opna_timer_machine.time.timer')
    matrix.append('frozen-source-CPU-counter-independent')
    def semantic():return [blob('opna_timer_machine.time.timer'),blob('opna_timer_machine.time.expired'),read(),blob('pic')]
    reset();values(991,211);write(0x27,15);advance(987654);single=semantic()
    reset();values(991,211);write(0x27,15)
    for d in [1,987,333333,653333]:advance(d)
    assert semantic()==single
    matrix.append('partition')
    reset();values(1023,255);write(0x27,15)
    start=time.monotonic();setv('opna_timer_fake_sample.ns',18446744073709551615);call('opna_timer_machine_service()');elapsed=time.monotonic()-start
    ticks=((2**64-1)*p['baseclock'])//10**9;frac=((2**64-1)*(156 if p['baseclock']==1996800 else 192))%78125
    huge=[]
    for i,per in enumerate(period(1023,255)):
        path='opna_timer_machine.time.'
        assert num(path+'expired[%d]'%i)==ticks//per
        assert num(path+'timer[%d].remaining'%i)==per-ticks%per
        assert num(path+'timer[%d].fraction'%i)==frac
        huge.append(dict(expired=ticks//per,remaining=per-ticks%per,fraction=frac))
    assert read()==3 and num('pic.pi[1].irr')&16 and num('pic.pi[1].isr')==0
    assert elapsed<2
    matrix.append('huge-gap-held-CPU')
    before=blob('opna_timer_machine.time.timer');anchor=num('opna_timer_machine.time.anchor_ns')
    setv('opna_timer_fake_sample.ns',0);call('opna_timer_machine_service()');assert before==blob('opna_timer_machine.time.timer') and anchor==num('opna_timer_machine.time.anchor_ns')
    reset();assert num('opna_timer_machine.time.expired[0]')==0
    matrix.extend(['backward-source','reset-epoch'])
    # Nanosecond boundary and I/O linearization with NO prior explicit service.
    for operation in ['read','clear','stop','rewrite']:
        reset();values(1023,255)
        setv('opna_timer_fake_sample.ns',17)
        io(0x188,0x27);io(0x18a,5)
        per=period(1023,255)[0];d=17+(per*10**9+p['baseclock']-1)//p['baseclock']
        setv('opna_timer_fake_sample.ns',d-1);assert read()==0
        setv('opna_timer_fake_sample.ns',d)
        if operation=='read':assert read()==1
        elif operation=='clear':write(0x27,0x15);assert read()==0
        elif operation=='stop':write(0x27,0);assert read()==1 and not num('opna_timer_machine.time.timer[0].active')
        else:
            write(0x24,128);assert read()==1
            # Expiry rearmed from the OLD value, before the rewrite.
            assert num('opna_timer_machine.time.timer[0].remaining')==per
        assert num('opna_timer_machine.time.expired[0]')==1
        matrix.append('ns-equality-'+operation)
    setv('opna_timer_fake_sample.ns',0);call('pccore_reset()')
    assert num('opna_timer_machine.ready')==1 and read()==0
    assert num('opna_timer_machine.time.timer[0].active')==num('opna_timer_machine.time.timer[1].active')==0
    assert num('opna_timer_machine.time.anchor_ns')==0
    matrix.append('guest-hard-reset')
(out/'observations.json').write_text(json.dumps(rows,indent=2)+'\n')
report=dict(result='PASS',profile=p,schedules=matrix,observations=len(rows),claims='actual production board86/native OPNA/I/O/PIC; CPU held, acceptance separately required')
if fake:report.update(huge=huge,huge_service_seconds=elapsed)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
gdb.execute('kill',to_string=True)
