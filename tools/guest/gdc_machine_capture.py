# SPDX-License-Identifier: MIT
"""Private N4 mode-2 GDB adapter. Only fake-source/presentation controls are written."""
import gdb
import json
from pathlib import Path

p=json.loads(Path(PARAMETERS).read_text());out=Path(p['out'])
core='i286core.s' if p['backend']=='i286' else 'i386core.s'
trace=[];reads=[];services=[];errors=[];tokens=[]
epoch_ns=None;epoch_ticks=None;halted_serviced=False;canonical=False


def num(e):return int(gdb.parse_and_eval(e))
def word(o):return num('*(unsigned short*)&mem[%d]'%(0x30000+o))
def active():return num('*(unsigned int*)&mem[0x30000]')==0x4447344e
def memory(name):
    v=gdb.parse_and_eval(name)
    return bytes(gdb.selected_inferior().read_memory(v.address,v.type.sizeof)).hex()
def snap():
    names=['gdc_machine.time.'+x for x in ('anchor_ns','ticks','fraction','remaining','vsync','transitions','collapsed','base')]
    names+=['gdc_machine.'+x for x in ('generation','presented','coalesced','presentations','finite_steps','admission_error')]
    names+=['gdc.'+x for x in ('hclock','vclock','rasterclock','hsyncclock','dispclock','vsyncclock','clock','vsync','vsyncint')]
    names+=['pic.pi[0].'+x for x in ('irr','isr','imr')]
    names+=[core+'.'+x for x in ('clock','baseclock','remainclock')]
    names+=['pccore.baseclock','pccore.multiple','np2cfg.RASTER','drawcount']
    return dict(values={k:num(k) for k in names},
                master_sync=[num('gdc.m.para[%d]'%i) for i in range(8)],
                slave_sync=[num('gdc.s.para[%d]'%i) for i in range(8)],
                blink=[num('tramflag.'+k) for k in ('timing','count','renewal')])
def source(ns):
    if ns<num('gdc_fake_sample.ns'):raise RuntimeError('adapter time reversal')
    gdb.execute('set variable gdc_fake_sample.ns = %d'%ns,to_string=True)
def service(ns=None,label='checkpoint'):
    if ns is not None:source(ns)
    before=snap();ledger=memory(core)
    other={n:memory(n) for n in ('pit','artic','dmac','g_nevent')}
    gdb.execute('call (void)gdc_machine_service()',to_string=True)
    after=snap()
    if memory(core)!=ledger:raise RuntimeError('GDC service altered CPU ledger/register state')
    if {n:memory(n) for n in other}!=other:raise RuntimeError('GDC service altered excluded state')
    services.append(dict(label=label,case=word(26),before=before,after=after,cpu_unchanged=True,excluded_unchanged=True))
def next_boundary():
    a=num('gdc_machine.time.anchor_ns');r=num('gdc_machine.time.remaining');f=num('gdc_machine.time.fraction')
    n=780 if p['profile_base']==1996800 else 960
    return a+(r*78125-f+n-1)//n

def phase(target):
    service(label='wait-refresh')
    if num('gdc_machine.time.vsync')!=target:service(next_boundary(),'wait-boundary')

def state_at_case(case):
    return snap()

class ReadDone(gdb.FinishBreakpoint):
    def __init__(self,port):
        super().__init__(gdb.newest_frame(),internal=True);self.port=port;self.case=word(26)
    def stop(self):
        reads.append(dict(case=self.case,port=self.port,raw=int(self.return_value)&255,state=snap()))
        return False
class Read(gdb.Breakpoint):
    def __init__(self,name,port):
        super().__init__(name,internal=True);self.port=port;self.enabled=False
    def stop(self):
        self.enabled=False;ReadDone(self.port);return False

class WakeDone(gdb.FinishBreakpoint):
    def __init__(self,ledger,before):
        super().__init__(gdb.newest_frame(),internal=True);self.ledger=ledger;self.before=before
    def stop(self):
        try:
            if memory(core)!=self.ledger:raise RuntimeError('HLT service changed CPU ledger')
            if not num('pic.pi[0].irr')&4:raise RuntimeError('HLT service did not publish IRQ2')
            services.append(dict(label='halted-service',before=self.before,after=snap(),cpu_unchanged=True))
        except Exception as e:errors.append(str(e));return True
        return False
class Wake(gdb.Breakpoint):
    def stop(self):
        global halted_serviced
        if not active() or word(26)!=22 or halted_serviced:return False
        halted=bool(num('i386core.s.cpu_stat.hlt')) if p['backend']=='ia32' else False
        # The published sample22 precedes the guest's wake-label assignment.
        # i286 HLT leaves IP on opcode F4; check the actual halted instruction.
        if p['backend']=='i286':
            ip=num('i286core.s.r.w.ip');cs=num('i286core.s.r.w.cs')
            halted=num('mem[%d]'%(cs*16+ip))==0xf4
        if not halted:return False
        ledger=memory(core);before=snap();source(next_boundary())
        halted_serviced=True;self.enabled=False;WakeDone(ledger,before)
        return False

def handle_step():
    global epoch_ns,epoch_ticks,canonical
    try:
        if not active():return
        token=word(24);case=word(26)
        if len(tokens)<200:tokens.append([token,case])
        if token==0x1001:
            gdb.execute('set variable gdc_fake_step_ns = 0',to_string=True)
            service(label='program-complete')
        elif token in (0x1100,0x1120):phase(int(token==0x1120))
        elif token==0x1204:
            service(label='masked-arm')
            if num('gdc_machine.time.vsync'):service(next_boundary(),'next-display')
            service(next_boundary(),'masked-VSync')
        elif token==0x1200:
            service(label='IRR-refresh')
            if num('pic.pi[0].irr')&4:service(next_boundary(),'pending-expiry')
        elif token==0x3003:
            service(label='unmasked-arm')
            if num('gdc_machine.time.vsync'):service(next_boundary(),'next-display')
            service(next_boundary(),'unmasked-VSync')
        elif token==0x3005:
            service(label='HLT-arm');wake.enabled=True
        elif token==0x3010:
            point=p['points'][16]
            service(epoch_ns+point['first_ns_on_tick'],'CPU-held-time-advanced')
        elif 0x2001<=token<=0x201c and token==0x2000+case:
            if case==1:
                service(label='stable-epoch')
                if num('gdc_machine.time.vsync')!=0:raise RuntimeError('epoch is not display start')
                epoch_ns=num('gdc_fake_sample.ns');epoch_ticks=num('gdc_machine.time.ticks');canonical=True
                gdb.execute('set variable gdc_fake_suppress_presentation = %d'%p['suppress'],to_string=True)
            if case<=17:
                target=epoch_ns+p['points'][case-1]['first_ns_on_tick']
                if p.get('schedule')=='fractional_and_partitioned' and case!=17:
                    start=num('gdc_fake_sample.ns')
                    if target-start>3:
                        for ns in sorted(set([start+1,start+(target-start)//3,start+2*(target-start)//3])):
                            service(ns,'partition')
                service(target,'selected-phase')
            else:service(label='sample')
            trace.append(dict(case=case,token=token,state=state_at_case(case),source_ns=num('gdc_fake_sample.ns')))
            master.enabled=True;slave.enabled=True
    except Exception as e:
        errors.append(str(e));return
    return

pending_step=False
class Step(gdb.Breakpoint):
    def stop(self):
        global pending_step
        if not active():return False
        token=word(24)
        accepted=token in (0x1001,0x1100,0x1120,0x1200,0x1204,0x3003,0x3005,0x3010) or (0x2001<=token<=0x201c and token==0x2000+word(26))
        pending_step=accepted
        return accepted
class Done(gdb.Breakpoint):
    def stop(self):return word(4094) in (2,3,4)

gdb.execute('start',to_string=True)
if num('gdc_fake_binding_version')!=1:raise RuntimeError('unqualified binding ABI')
if gdb.parse_and_eval('gdc_machine_source_id').string()!=p['source_id']:raise RuntimeError('stale product source identity')
if gdb.lookup_global_symbol('pit0_fake_sample') is not None:raise RuntimeError('isolated N4 requires PIT fake OFF')
gdb.execute('set variable gdc_fake_step_ns = 1000000',to_string=True)
master=Read('*gdc_i60',96);slave=Read('*gdc_ia0',160)
wake=Wake('*gdc_machine_pic_service',internal=True);wake.enabled=False
Step('*(unsigned short*)&mem[0x30018]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
Done('*(unsigned short*)&mem[0x30ffe]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
if p.get('diagnostic_stop'):
    class BootDebug(gdb.Breakpoint):
        calls=0
        def stop(self):
            self.calls+=1
            if self.calls%5000==0:
                (out/'boot-progress.json').write_text(json.dumps(dict(calls=self.calls,state=snap(),cpu=gdb.execute('p '+core,to_string=True))))
            return self.calls>=p['diagnostic_stop']
    BootDebug('*gdc_machine_service',internal=True)
while True:
    pending_step=False
    gdb.execute('continue')
    if not pending_step:break
    handle_step()
    if errors:break
(out/'cpu-diagnostic.txt').write_text(gdb.execute('p '+core,to_string=True)+'\n'+gdb.execute('bt',to_string=True))
presentation={}
if not errors and word(4094)==2:
    # Request a host repaint explicitly: normal schedules may have already
    # consumed every dirty region before this held-CPU presentation check.
    # This is presentation-only state, not guest GDC/CPU state. Keep the
    # existing exact one-draw and unchanged-guest assertions below.
    gdb.execute('set variable pcstat.screenupdate = pcstat.screenupdate | 1',to_string=True)
    before=snap();raw_gdc=memory('gdc');ledger=memory(core)
    old_draw=num('pcstat.drawframe')
    gdb.execute('set variable gdc_fake_suppress_presentation = 0',to_string=True)
    gdb.execute('set variable pcstat.drawframe = 1',to_string=True)
    gdb.execute('call (void)gdc_machine_present()',to_string=True)
    gdb.execute('set variable pcstat.drawframe = %d'%old_draw,to_string=True)
    presentation=dict(before=before,after=snap(),gdc_unchanged=raw_gdc==memory('gdc'),cpu_unchanged=ledger==memory(core))
(out/'result.bin').write_bytes(bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval('&mem[0x30000]'),4096)))
(out/'machine-capture.json').write_text(json.dumps(dict(trace=trace,reads=reads,services=services,errors=errors,tokens=tokens,
    epoch_ns=epoch_ns,epoch_ticks=epoch_ticks,halted_serviced=halted_serviced,presentation=presentation,final=snap()),indent=2)+'\n')
gdb.execute('kill',to_string=True)
if errors:raise RuntimeError(errors)
