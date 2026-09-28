# SPDX-License-Identifier: MIT
import gdb,json
from pathlib import Path
p=json.loads(Path(PARAMETERS).read_text());out=Path(p['out']);core='i286core.s' if p['backend']=='i286' else 'i386core.s'
num=lambda e:int(gdb.parse_and_eval(e))
def word(off):return num('*(unsigned short*)&mem[%d]'%(0x29000+off))
def position():return (num(core+'.clock')+num(core+'.baseclock')-num(core+'.remainclock'))&0xffffffff
def blob(e):
    v=gdb.parse_and_eval(e);return bytes(gdb.selected_inferior().read_memory(v.address,v.type.sizeof)).hex()
fields=[core,'g_nevent','g_pcm86','artic','gdc','dmac']
log=dict(hlt_serviced=False,cpu_frozen_service=False,frozen_cpu_progress=False,steps=[]);fail=[];start=0

def next_deadline():
    t='opna_timer_machine.time.'
    ns=num(t+'anchor_ns')+(num(t+'timer[0].remaining')*78125-num(t+'timer[0].fraction')+num(t+'numerator')-1)//num(t+'numerator')
    gdb.execute('set variable opna_timer_fake_sample.ns = '+str(ns),to_string=True)
    return ns
class ServiceDone(gdb.FinishBreakpoint):
    def __init__(self,before):super().__init__(gdb.newest_frame(),internal=True);self.before=before
    def stop(self):
        try:
            assert self.before==[blob(e) for e in fields]
            assert num('g_opna[0].s.status')&1 and num('pic.pi[1].irr')&16 and word(30)==1
            log['cpu_frozen_service']=True
        except Exception as e:fail.append(repr(e));return True
        return False
class Service(gdb.Breakpoint):
    def stop(self):
        if word(12)!=5 or log['hlt_serviced']:return False
        try:
            halted=(num(core+'.r.w.ip')==word(44)-1 if p['backend']=='i286' else bool(num(core+'.cpu_stat.hlt')))
            if not halted:return False
            before=[blob(e) for e in fields];ns=next_deadline();log['hlt_serviced']=True
            log['held_ns']=ns;ServiceDone(before)
        except Exception as e:fail.append(repr(e));return True
        return False
class Step(gdb.Breakpoint):
    def stop(self):
        global start
        if num('*(unsigned int*)&mem[0x29000]')!=0x544f364e:return False
        try:
            step=word(12);log['steps'].append(dict(step=step,cpu=position(),ns=num('opna_timer_fake_sample.ns'),handlers=word(30)))
            if step==1:
                assert num('g_nSoundID')==4 and num('enable_fmgen')==0 and num('g_opna[0].s.cCaps')==0x9f
                assert num('g_opna[0].s.irq')==12 and num('g_pcm86.fifo')&0xa0==0
                assert num('g_pcm86.irqflag')==num('g_pcm86.reqirq')==0
                assert num('g_pcm86.realbuf')==num('g_pcm86.virbuf')==0
                start=position()
            elif step==2:
                assert 0<(position()-start)&0xffffffff<0x80000000
                assert num('opna_timer_fake_sample.ns')==0 and num('g_opna[0].s.status')==0
                log['frozen_cpu_progress']=True
            elif step==3:next_deadline()
            elif step==4:
                assert num('pic.pi[1].irr')&16 and word(30)==0
            elif step==5:Service('*opna_timer_machine_service',internal=True)
        except Exception as e:fail.append(repr(e));return True
        return False
class Done(gdb.Breakpoint):
    def stop(self):return num('*(unsigned int*)&mem[0x29000]')==0x544f364e and word(126)==2
gdb.execute('start',to_string=True)
Step('*(unsigned short*)&mem[0x2900c]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
Done('*(unsigned short*)&mem[0x2907e]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
gdb.execute('continue',to_string=True)
assert not fail,fail
assert word(126)==2 and log['hlt_serviced']
(out/'result.bin').write_bytes(bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval('&mem[0x29000]'),128)))
(out/'service.json').write_text(json.dumps(log,indent=2)+'\n')
gdb.execute('kill',to_string=True)
