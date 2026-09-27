# SPDX-License-Identifier: MIT
"""Private read-only GDB capture. PARAMETERS is supplied by the N4 runner.

Never writes guest memory, fake time, GDC, PIC, or CPU state. The future adapter
must be separately qualified before mode 2 can execute.
"""
import json
from pathlib import Path
import gdb

p=json.loads(Path(PARAMETERS).read_text())
out=Path(p['out'])
trace=[]
reads=[]
events={'screenvsync':0,'screendisp':0}
errors=[]
core='i286core.s' if p['backend']=='i286' else 'i386core.s'


def num(e):
    return int(gdb.parse_and_eval(e))


def word(offset):
    return num('*(unsigned short*)&mem[%d]' % (0x30000+offset))


def active():
    return num('*(unsigned int*)&mem[0x30000]')==0x4447344e


def snapshot():
    names=['pccore.baseclock','pccore.multiple','np2cfg.RASTER','np2cfg.DISPSYNC',
           'gdc.crt15khz','gdc.display','gdc.vsync','gdc.vsyncint',
           'gdc.hclock','gdc.vclock','gdc.rasterclock','gdc.hsyncclock',
           'gdc.dispclock','gdc.vsyncclock','pic.pi[0].irr','pic.pi[0].isr',
           'pic.pi[0].imr',core+'.clock',core+'.baseclock',core+'.remainclock']
    result={name:num(name) for name in names}
    result.update(token=word(24),case=word(26),events=events.copy(),
                  master_sync=[num('gdc.m.para[%d]'%i) for i in range(8)],
                  slave_sync=[num('gdc.s.para[%d]'%i) for i in range(8)])
    return result


class ReadDone(gdb.FinishBreakpoint):
    def __init__(self,port):
        super().__init__(gdb.newest_frame(),internal=True)
        self.port=port
        self.case=word(26)
    def stop(self):
        try:
            reads.append(dict(case=self.case,port=self.port,
                              raw=int(self.return_value)&255))
        except Exception as e:
            errors.append(str(e));return True
        return False


class Read(gdb.Breakpoint):
    def __init__(self,name,port):
        super().__init__(name,internal=True)
        self.port=port
        self.enabled=False
    def stop(self):
        self.enabled=False
        ReadDone(self.port)
        return False


class Event(gdb.Breakpoint):
    def __init__(self,name):
        super().__init__(name,internal=True)
        self.name=name.lstrip("*")
    def stop(self):
        if active():events[self.name]+=1
        return False


class Step(gdb.Breakpoint):
    def stop(self):
        try:
            if not active():return False
            token=word(24)
            if 0x2001<=token<=0x201c and token==0x2000+word(26):
                trace.append(snapshot())
                master_read.enabled=True
                slave_read.enabled=True
        except Exception as e:
            errors.append(str(e));return True
        return False


class Done(gdb.Breakpoint):
    def stop(self):
        return word(4094) in (2,3,4)


gdb.execute('start',to_string=True)
if p['mode']!=1:
    raise RuntimeError('NOT_EXECUTABLE_UNTIL_MACHINE_TIME_GDC')
if gdb.lookup_global_symbol('pit0_fake_sample') is not None:
    raise RuntimeError('N4 legacy qualification requires PIT fake source OFF')
num(core+'.clock')                    # reject a mismatched backend
master_read=Read('*gdc_i60',0x60)
slave_read=Read('*gdc_ia0',0xa0)
Event('*screenvsync')
Event('*screendisp')
Step('*(unsigned short*)&mem[0x30018]',type=gdb.BP_WATCHPOINT,
     wp_class=gdb.WP_WRITE,internal=True)
Done('*(unsigned short*)&mem[0x30ffe]',type=gdb.BP_WATCHPOINT,
     wp_class=gdb.WP_WRITE,internal=True)
gdb.execute('continue')
data=bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval('&mem[0x30000]'),4096))
(out/'result.bin').write_bytes(data)
(out/'capture.json').write_text(json.dumps(dict(trace=trace,reads=reads,events=events,
                                               errors=errors),indent=2)+'\n')
gdb.execute('kill',to_string=True)
if errors:
    raise RuntimeError(errors)
