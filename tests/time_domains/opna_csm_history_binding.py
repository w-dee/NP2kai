# SPDX-License-Identifier: MIT
# GDB controls fake time only; the complete production board/timer/PIC/I/O executes.
import gdb,json,time
from pathlib import Path
params=json.loads(Path(PARAMETERS).read_text());out=Path(params['out']);case=params['case']
core='i286core.s' if params['backend']=='i286' else 'i386core.s'
num=lambda expression:int(gdb.parse_and_eval(expression))
def call(expression):return gdb.parse_and_eval(expression)
def setv(expression,value):gdb.execute('set variable '+expression+' = '+str(value),to_string=True)
def io(port,value):call('%s(%d,%d)'%({0x188:'opna_o188',0x18a:'opna_o18a'}[port],port,value))
def write(reg,value):io(0x188,reg);io(0x18a,value)
def status():return num('opna_i188(0x188)')
numerator=156 if params['baseclock']==1996800 else 192
legacy_scale=1248 if numerator==156 else 1536
def period_a(value):return 18*(1024-value)*legacy_scale//625
def deadline(n,period,anchor=0):return anchor+(n*period*78125+numerator-1)//numerator
def rows():
    count=num('opna_timer_machine.history_count')
    return [dict(epoch=num(f'opna_timer_machine.history[{i}].epoch'),seq=num(f'opna_timer_machine.history[{i}].sequence'),deadline=num(f'opna_timer_machine.history[{i}].deadline_ns'),service=num(f'opna_timer_machine.history[{i}].service_ns'),ordinal=num(f'opna_timer_machine.history[{i}].timer_a_ordinal'),kind=num(f'opna_timer_machine.history[{i}].kind'),off=num(f'opna_timer_machine.history[{i}].key_off_subindex'),on=num(f'opna_timer_machine.history[{i}].key_on_subindex')) for i in range(count)]
def state():
    return dict(timer=[(num(f'opna_timer_machine.time.timer[{i}].remaining'),num(f'opna_timer_machine.time.timer[{i}].fraction'),num(f'opna_timer_machine.time.timer[{i}].active')) for i in range(2)],expired=[num(f'opna_timer_machine.time.expired[{i}]') for i in range(2)],status=num('g_opna[0].s.status'),pic_irr=[num('pic.pi[0].irr'),num('pic.pi[1].irr')],pic_isr=[num('pic.pi[0].isr'),num('pic.pi[1].isr')],anchor=num('opna_timer_machine.time.anchor_ns'),accepted=num('opna_timer_machine.accepted_frontier_ns'),epoch=num('opna_timer_machine.history_epoch'),finalized=num('opna_timer_machine.history_finalized_count'),next_sequence=num('opna_timer_machine.history_next_sequence'),rows=rows())
now=0
def reset():
    global now
    now=0;setv('opna_timer_fake_sample.ns',0)
    call('nevent_allreset()');call('pcm86_reset()');call('board86_reset(&np2cfg,0)');call('board86_bind()');call('pic_reset(&np2cfg)')
    setv(core+'.clock',0);setv(core+'.baseclock',0);setv(core+'.remainclock',0)
    call('nevent_get1stevent()')
    assert num('g_nSoundID')==4 and num('enable_fmgen')==0 and num('g_opna[0].s.cCaps')==0x9f
    assert num('opna_timer_machine.history_count')==0 and status()==0
    assert num('opna_timer_machine.time.anchor_ns')==0

def advance(target):
    global now
    assert target>=now;now=target;setv('opna_timer_fake_sample.ns',target);call('opna_timer_machine_service()')
def value(a,b=255):
    write(0x24,a>>2);write(0x25,a&3);write(0x26,b)
def start(a=1023,ctl=0x85,b=255):
    value(a,b);write(0x27,ctl);return period_a(a)

class SynthesisBreakpoint(gdb.Breakpoint):
    def __init__(self,symbol):
        super().__init__(symbol,internal=True);self.count=0
    def stop(self):
        if num('opna_timer_machine.servicing'):self.count+=1
        return False

class OrderBreakpoint(gdb.Breakpoint):
    def __init__(self,symbol,label):
        super().__init__(symbol,internal=True);self.label=label
    def stop(self):
        if num('opna_timer_machine.servicing'):
            order_trace.append(dict(stage=self.label,status=num('g_opna[0].s.status'),
                history=num('opna_timer_machine.history_count'),
                timer_remaining=num('opna_timer_machine.time.timer[0].remaining')))
        return False

class GuestOperationBreakpoint(gdb.Breakpoint):
    def __init__(self,symbol):
        super().__init__(symbol,internal=True);self.symbol=symbol
    def stop(self):
        if guest_arm:
            guest_hits.append(dict(operation=self.symbol,history=num('opna_timer_machine.history_count'),
                servicing=num('opna_timer_machine.servicing')))
        return False

order_trace=[];guest_hits=[];guest_arm=False
gdb.Breakpoint('pccore_exec',internal=True)
gdb.execute('run',to_string=True)
synth=[SynthesisBreakpoint(symbol) for symbol in ['sound_sync','opngen_csm','opngen_getpcm']]
order_probes=[OrderBreakpoint('fmport_a','timer_a'),OrderBreakpoint('pic_setirq','pic'),OrderBreakpoint('set_fmtimeraevent','rearm')]
guest_probes=[GuestOperationBreakpoint('opngen_keyon'),GuestOperationBreakpoint('opngen_setreg')]
result=dict(case=case,result='PASS',backend=params['backend'])
if case=='positive':
    reset();p=start();d=deadline(1,p);advance(d-1);assert not rows() and status()==0
    advance(d);r=rows();assert len(r)==1 and r[0]['deadline']==d and r[0]['service']==d and r[0]['seq']==0
    assert r[0]['kind']==1 and (r[0]['off'],r[0]['on'])==(0,1) and status()==1 and state()['pic_irr'][1]&16
    assert num('opna_timer_machine.history_finalized_count')==1
    assert [x['stage'] for x in order_trace]==['timer_a','pic','rearm'],order_trace
    assert order_trace[0]['status']==0 and order_trace[1]['status']==1
    assert all(x['history']==0 for x in order_trace)
    result['single_order']=order_trace.copy();result['single']=state()
    reset();p=start(1023,0x81);advance(deadline(1,p));assert len(rows())==1 and status()==0 and not(state()['pic_irr'][1]&16)
    result['status_disabled']=state()
    reset();p=start();cpu_before=tuple(num(core+'.'+field) for field in ('clock','baseclock','remainclock'));trace_start=len(order_trace);advance(deadline(100,p));r=rows();assert len(r)==100 and status()==1
    trace=order_trace[trace_start:]
    assert sum(x['stage']=='timer_a' for x in trace)==100 and sum(x['stage']=='rearm' for x in trace)==100
    assert sum(x['stage']=='pic' for x in trace)==1
    assert [x['deadline'] for x in r]==[deadline(i,p) for i in range(1,101)]
    assert [x['seq'] for x in r]==list(range(100)) and [x['ordinal'] for x in r]==list(range(1,101))
    assert cpu_before==tuple(num(core+'.'+field) for field in ('clock','baseclock','remainclock'))
    assert state()['pic_isr']==[0,0]
    result['hundred_one_service']=dict(first=r[0],last=r[-1],count=len(r),pic_publications=1,cpu_clock=num(core+'.clock'),state=state())
    large=state()
    reset();p=start()
    for i in range(1,101):advance(deadline(i,p))
    small=state()
    for snapshot in (large,small):
        snapshot.pop('epoch')
        for record in snapshot['rows']:
            record.pop('service');record.pop('epoch')
    assert small==large,'partition changed qualified state or logical history'
    result['partition_invariant']=True
    reset();p=start();d=deadline(1,p);setv('opna_timer_fake_sample.ns',d);now=d
    write(0x27,0x01);assert len(rows())==1 and rows()[0]['deadline']==d and num('g_opna[0].s.reg[0x27]')==1
    advance(deadline(3,p));assert len(rows())==1
    result['same_time_disable']=state()
    reset();p=start();d=deadline(1,p);setv('opna_timer_fake_sample.ns',d);now=d
    guest_arm=True;write(0x28,0xf2);guest_arm=False
    assert len(rows())==1 and rows()[0]['deadline']==d
    assert any(x['operation']=='opngen_keyon' and x['history']==1 and x['servicing']==0 for x in guest_hits),guest_hits
    result['same_time_key']=dict(state=state(),guest_hits=guest_hits.copy())
    reset();p=start();d=deadline(1,p);setv('opna_timer_fake_sample.ns',d);now=d
    guest_hits.clear();guest_arm=True;write(0xa6,0x22);guest_arm=False
    assert len(rows())==1 and rows()[0]['deadline']==d
    assert any(x['operation']=='opngen_setreg' and x['history']==1 and x['servicing']==0 for x in guest_hits),guest_hits
    result['same_time_frequency']=dict(state=state(),guest_hits=guest_hits.copy())
    reset();p=start();d=deadline(1,p);setv('opna_timer_fake_sample.ns',d);now=d
    assert status()==1 and len(rows())==1 and rows()[0]['deadline']==d
    result['same_time_status_read']=state()
    reset();p=start(512);old=deadline(1,p);advance(old//2)
    value(1023);assert num('opna_timer_machine.time.timer[0].remaining')>0
    advance(old);assert len(rows())==1 and rows()[0]['deadline']==old
    nxt=state()['anchor']+(num('opna_timer_machine.time.timer[0].remaining')*78125-num('opna_timer_machine.time.timer[0].fraction')+numerator-1)//numerator
    advance(nxt-1);assert len(rows())==1;advance(nxt);assert len(rows())==2 and rows()[1]['deadline']==nxt
    result['value_rewrite']=dict(old=old,next=nxt)
    reset();p=start();advance(deadline(1,p));write(0x27,0x80);prior=rows();advance(deadline(10,p));assert rows()==prior
    write(0x27,0x85);restart=now;new_deadline=deadline(1,p,restart);advance(new_deadline);assert len(rows())==2 and rows()[1]['deadline']==new_deadline
    result['stop_restart']=state()
    reset();p=start(1008,0x8f,255);assert p==288*(256-255)*legacy_scale//625
    advance(deadline(1,p));assert len(rows())==1 and status()==3 and state()['pic_irr'][1]&16
    result['ab_simultaneous']=state()
    reset();p=start();advance(deadline(1,p));prior_epoch=rows()[0]['epoch'];reset();assert num('opna_timer_machine.history_epoch')==prior_epoch+1 and not rows()
    p=start();advance(deadline(1,p));assert len(rows())==1 and rows()[0]['epoch']==prior_epoch+1 and rows()[0]['seq']==0
    result['reset_epoch']=state()
    reset();p=start();advance(deadline(255,p));assert len(rows())==255
    result['capacity_minus_one']=len(rows())
    advance(deadline(256,p));assert len(rows())==256 and num('opna_timer_machine.history_finalized_count')==256
    result['capacity']=len(rows())
    reset();p=start();advance(deadline(1,p));assert len(rows())==1
    result['fresh_capacity_after_reset']=True
    reset();p=start(0,0x05);begin=time.monotonic();advance(18446744073709551615);elapsed=time.monotonic()-begin
    assert num('opna_timer_machine.history_count')==0 and num('opna_timer_machine.time.expired[0]')>1000000000
    result['csm_off_huge_gap_seconds']=elapsed
elif case in ('capacity_plus_one','insufficient_first','insufficient_after_finalized','huge_gap','sequence_overflow','incomplete_prefix','retroactive_sequence','incompatible_base','corrupt_phase','corrupt_timer_state'):
    reset();p=start();
    if case=='insufficient_first':
        setv('opna_timer_machine.history_count',256);setv('opna_timer_machine.history_finalized_count',256);setv('opna_timer_machine.history_next_sequence',256)
    if case=='insufficient_after_finalized':
        advance(deadline(255,p));assert len(rows())==255
    if case=='sequence_overflow':setv('opna_timer_machine.history_next_sequence',18446744073709551615)
    if case=='incomplete_prefix':
        advance(deadline(1,p));setv('opna_timer_machine.history_finalized_count',0)
    if case=='retroactive_sequence':
        advance(deadline(1,p));setv('opna_timer_machine.history_next_sequence',0)
    if case=='incompatible_base':setv('pccore.baseclock',12345)
    if case=='corrupt_phase':setv('opna_timer_machine.time.numerator',0)
    if case=='corrupt_timer_state':setv('opna_timer_machine.time.timer[0].remaining',0)
    before_full=state()
    before_counters=[num('opna_timer_machine.time.services'),num('opna_timer_machine.time.rejected'),num('opna_timer_machine.time.max_gap_ns')]
    before=dict(time_anchor=num('opna_timer_machine.time.anchor_ns'),accepted=num('opna_timer_machine.accepted_frontier_ns'),expired=num('opna_timer_machine.time.expired[0]'),history_count=num('opna_timer_machine.history_count'),status=num('g_opna[0].s.status'),pic=num('pic.pi[1].irr'))
    target=18446744073709551615 if case=='huge_gap' else deadline(257,p) if case=='capacity_plus_one' else deadline(257,p) if case=='insufficient_after_finalized' else deadline(2,p) if case=='retroactive_sequence' else deadline(1,p)
    setv('opna_timer_fake_sample.ns',target)
    begin=time.monotonic()
    try:call('opna_timer_machine_service()')
    except gdb.error:pass
    elapsed=time.monotonic()-begin
    code=num('opna_timer_machine.admission_error')
    assert code==(9 if case in ('incomplete_prefix','retroactive_sequence','corrupt_timer_state') else 6 if case in ('incompatible_base','corrupt_phase') else 8 if case=='sequence_overflow' else 7),(case,code)
    assert state()==before_full,'rejected service changed semantic state or published history'
    assert before_counters==[num('opna_timer_machine.time.services'),num('opna_timer_machine.time.rejected'),num('opna_timer_machine.time.max_gap_ns')]
    assert before==dict(time_anchor=num('opna_timer_machine.time.anchor_ns'),accepted=num('opna_timer_machine.accepted_frontier_ns'),expired=num('opna_timer_machine.time.expired[0]'),history_count=num('opna_timer_machine.history_count'),status=num('g_opna[0].s.status'),pic=num('pic.pi[1].irr'))
    assert elapsed<5,elapsed
    result.update(rejection=code,required=num('opna_timer_machine.rejection_required'),target=target,before=before,elapsed_seconds=elapsed)
else:raise AssertionError(case)
assert all(x.count==0 for x in synth),[(x.location,x.count) for x in synth]
result['machine_owner_synthesis_calls']={x.location:x.count for x in synth}
(out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
gdb.execute('kill',to_string=True);gdb.execute('quit')
