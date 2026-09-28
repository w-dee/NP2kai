# SPDX-License-Identifier: MIT
"""GDB fixture: real N6-C board/timer/I/O, fake monotonic machine time only."""
import gdb, json
from pathlib import Path
p = json.loads(Path(PARAMETERS).read_text())
case = p['case']
backend = p['backend']
core = 'i286core.s' if backend == 'i286' else 'i386core.s'
num = lambda e: int(gdb.parse_and_eval(e))
call = lambda e: gdb.parse_and_eval(e)
def setv(e, v): gdb.execute('set variable ' + e + ' = ' + str(v), to_string=True)
def io(port, value): call('%s(%d,%d)' % ({0x188:'opna_o188',0x18a:'opna_o18a'}[port], port, value))
def write(reg, value): io(0x188, reg); io(0x18a, value)
def period(value): return 18 * (1024-value) * 1536 // 625
def deadline(n, per, anchor=0): return anchor + (n*per*78125 + 191)//192
def rows():
    count = num('opna_timer_machine.history_count')
    return [dict(epoch=num(f'opna_timer_machine.history[{i}].epoch'),
                 sequence=num(f'opna_timer_machine.history[{i}].sequence'),
                 deadline_ns=num(f'opna_timer_machine.history[{i}].deadline_ns'),
                 service_ns=num(f'opna_timer_machine.history[{i}].service_ns'),
                 ordinal=num(f'opna_timer_machine.history[{i}].timer_a_ordinal'),
                 kind=num(f'opna_timer_machine.history[{i}].kind'),
                 off=num(f'opna_timer_machine.history[{i}].key_off_subindex'),
                 on=num(f'opna_timer_machine.history[{i}].key_on_subindex')) for i in range(count)]
now = 0
operations = []
guest_hits = []
guest_arm = None
segments = []
expected = []
def reset():
    global now
    now = 0
    setv('opna_timer_fake_sample.ns', 0)
    call('nevent_allreset()'); call('pcm86_reset()'); call('board86_reset(&np2cfg,0)')
    call('board86_bind()'); call('pic_reset(&np2cfg)')
    setv(core+'.clock',0); setv(core+'.baseclock',0); setv(core+'.remainclock',0)
    call('nevent_get1stevent()')
    assert num('g_nSoundID') == 4 and num('enable_fmgen') == 0
    assert num('opna_timer_machine.history_count') == 0
    assert num('opna_timer_machine.time.anchor_ns') == 0
    assert num('opna_timer_machine.admission_error') == 0
    return num('opna_timer_machine.history_epoch')
def advance(target):
    global now
    assert target >= now
    now = target; setv('opna_timer_fake_sample.ns', target)
    call('opna_timer_machine_service()')
    assert num('opna_timer_machine.admission_error') == 0
def start(a=1023):
    write(0x24,a>>2); write(0x25,a&3); write(0x26,255); write(0x27,0x85)
    return period(a)
def guest(reg, value):
    global guest_arm
    before = len(rows())
    guest_arm = reg
    try: write(reg,value)
    finally: guest_arm = None
    operations.append(dict(register=reg,value=value,machine_ns=now,
                           before_write_csm=before,preceding_csm=len(rows()),
                           finalized=num('opna_timer_machine.history_finalized_count')))
def snapshot():
    assert num('opna_timer_machine.history_finalized_count') == len(rows())
    segments.append(dict(epoch=num('opna_timer_machine.history_epoch'),records=rows(),
                         finalized_count=num('opna_timer_machine.history_finalized_count'),
                         next_sequence=num('opna_timer_machine.history_next_sequence')))

class NoSynthesis(gdb.Breakpoint):
    def __init__(self,symbol):
        super().__init__(symbol,internal=True); self.hits=0
    def stop(self):
        if num('opna_timer_machine.servicing'): self.hits += 1
        return False

class GuestOrder(gdb.Breakpoint):
    def __init__(self,symbol):
        super().__init__(symbol,internal=True); self.symbol=symbol
    def stop(self):
        if guest_arm is not None:
            guest_hits.append(dict(register=guest_arm,operation=self.symbol,
                                   preceding_csm=len(rows()),
                                   servicing=num('opna_timer_machine.servicing')))
        return False

gdb.Breakpoint('pccore_exec',internal=True)
gdb.execute('run',to_string=True)
probes = [NoSynthesis(x) for x in ('sound_sync','opngen_csm','opngen_getpcm')]
guest_probes = [GuestOrder(x) for x in ('opngen_keyon','opngen_setreg')]
epoch = reset(); per = start(512 if case == 'p7_rewrite' else 1023)
if case == 'p0_baseline':
    pass
elif case == 'p1_single':
    d = deadline(1,per); advance(d); expected.append((epoch,0,d))
elif case in ('p2_repeated','p3_batched','p7_rewrite','p8_stop_restart'):
    if case == 'p3_batched':
        advance(deadline(10,per))
        expected.extend((epoch,i-1,deadline(i,per)) for i in range(1,11))
    elif case == 'p7_rewrite':
        # Rewrite after the first expiry. The old reload phase remains live;
        # subsequent deadlines are calculated from the qualified rational phase.
        advance(deadline(1,per)); expected.append((epoch,0,deadline(1,per)))
        guest(0x24,0xff); guest(0x25,3)
        for i in range(1,10):
            remaining = num('opna_timer_machine.time.timer[0].remaining')
            fraction = num('opna_timer_machine.time.timer[0].fraction')
            anchor = num('opna_timer_machine.time.anchor_ns')
            d = anchor + (remaining*78125-fraction+191)//192
            advance(d); expected.append((epoch,i,d))
    elif case == 'p8_stop_restart':
        advance(deadline(1,per)); expected.append((epoch,0,deadline(1,per)))
        write(0x27,0x80); advance(deadline(11,per))
        assert len(rows()) == 1
        write(0x27,0x85); anchor = now
        for i in range(1,10):
            d = deadline(i,per,anchor); advance(d); expected.append((epoch,i,d))
    else:
        for i in range(1,11):
            d = deadline(i,per); advance(d); expected.append((epoch,i-1,d))
elif case in ('p4_key','p5_frequency','p10_quiet','p10_quiet_large'):
    d=deadline(1,per)
    if case=='p4_key':
        now=d; setv('opna_timer_fake_sample.ns',d); guest(0x28,2)
    elif case=='p5_frequency':
        now=d; setv('opna_timer_fake_sample.ns',d); guest(0xa6,0x2a); guest(0xa2,0x41)
    else: advance(d)
    expected.append((epoch,0,d))
elif case=='p6_same_frontier':
    d=deadline(2,per); advance(d)
    expected.extend((epoch,i-1,deadline(i,per)) for i in range(1,3))
elif case=='p9_reset':
    d=deadline(1,per); advance(d); expected.append((epoch,0,d)); snapshot()
    epoch=reset(); per=start(); d=deadline(1,per); advance(d); expected.append((epoch,0,d))
elif case=='p11_active':
    for i in range(1,8):
        d=deadline(i,per); advance(d); expected.append((epoch,i-1,d))
else: raise AssertionError(case)
snapshot()
actual = [(r['epoch'],r['sequence'],r['deadline_ns']) for s in segments for r in s['records']]
assert actual == expected,(case,actual,expected)
assert all(r['kind']==1 and (r['off'],r['on'])==(0,1) for s in segments for r in s['records'])
assert all(x.hits==0 for x in probes)
if case=='p4_key':
    assert any(x['register']==0x28 and x['operation']=='opngen_keyon' and
               x['preceding_csm']==1 and x['servicing']==0 for x in guest_hits),guest_hits
if case=='p5_frequency':
    assert any(x['register']==0xa6 and x['operation']=='opngen_setreg' and
               x['preceding_csm']==1 and x['servicing']==0 for x in guest_hits),guest_hits
result=dict(case=case,backend=backend,baseclock=2457600,board=4,
            segments=segments,expected=[dict(epoch=e,sequence=s,deadline_ns=d) for e,s,d in expected],
            operations=operations,guest_hits=guest_hits,machine_owner_synthesis_calls={x.location:x.hits for x in probes},
            result='PASS')
Path(p['out'],'semantic.json').write_text(json.dumps(result,indent=2)+'\n')
gdb.execute('kill',to_string=True); gdb.execute('quit')
