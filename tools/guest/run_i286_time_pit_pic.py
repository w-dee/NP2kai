#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Private GDB fake-time qualification through real guest IN instructions."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import select
import shutil
import subprocess
from pit_pic_contract import verify_result
from build_i286_time_pit_pic import build, ROOT


def qualify(binary, output, backend, mode, multiple, baseclock):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('private GDB runner requires Linux x86_64 host ABI')
    binary, output = Path(binary).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = output/'pit-pic.hdm'
    profile=1 if backend=="i286" else 2
    report = build(image, mode, profile)
    config = output/'xdg'/('sdlnp2kai' if backend == 'i286' else 'sdlnp21kai')
    config.mkdir(parents=True, exist_ok=True)
    for name in ('bios.rom','font.rom'):
        shutil.copyfile(ROOT/'.local/oracle/pristine'/name,config/name)
    ini = 'np2kai.cfg' if backend == 'i286' else 'np21kai.cfg'
    section = 'NekoProjectIIkai' if backend == 'i286' else 'NekoProject21kai'
    (config/ini).write_text(f'[{section}]\nclk_base = {baseclock}\nclk_mult = {multiple}\npc_model = VX\nExMemory = 1\n')
    params = dict(out=str(output), profile=profile, backend=backend, mode=mode,
                  multiple=multiple, baseclock=baseclock)
    (output/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    # GDB sees only a private host test source. No guest command/API is added.
    script = r'''
import gdb,json
from pathlib import Path
p=json.loads(Path(PARAMETERS).read_text());out=Path(p['out'])
log=[];fail=[];q=0;latched_advanced=False;hlt_serviced=False
core='i286core.s' if p['backend']=='i286' else 'i386core.s'
def num(e):return int(gdb.parse_and_eval(e))
def word(off):return num('*(unsigned short*)&mem['+str(0x29000+off)+']')
def snap(names):
    result={}
    for name in names:
        v=gdb.parse_and_eval(name)
        result[name]=bytes(gdb.selected_inferior().read_memory(v.address,v.type.sizeof)).hex()
    return result
def advance(delta):
    global q
    q+=delta
    numerator=780 if p['baseclock']==1996800 else 960
    ns=(q*78125+numerator-1)//numerator
    if p['mode']==2:gdb.execute('set variable pit0_fake_sample.ns = '+str(ns),to_string=True)
    log.append(dict(step=word(12),quanta=q,ns=ns,cpu_clock=num(core+'.clock'),
                    cpu_base=num(core+'.baseclock'),cpu_remaining=num(core+'.remainclock')))
class ServiceDone(gdb.FinishBreakpoint):
    def __init__(self,before):
        super().__init__(gdb.newest_frame(),internal=True);self.before=before
    def stop(self):
        try:
            after=snap([core,'artic','gdc','dmac','g_nevent','pit.ch[1]','pit.ch[2]','pit.ch[3]','pit.ch[4]'])
            assert after==self.before,'service mutated CPU/other clocks'
            assert num('pic.pi[0].irr')&1,'HLT service must materialize IRR0'
            log.append(dict(hlt_cpu_frozen_service=True,other_state_unchanged=True))
        except Exception as e:fail.append(str(e));return True
        return False
class Service(gdb.Breakpoint):
    def stop(self):
        global hlt_serviced
        try:
            if word(12)!=6 or hlt_serviced:return False
            halted=(num('i286core.s.r.w.ip')==word(44)-1 if p['backend']=='i286'
                    else bool(num('i386core.s.cpu_stat.hlt')))
            if not halted:return False
            before=snap([core,'artic','gdc','dmac','g_nevent','pit.ch[1]','pit.ch[2]','pit.ch[3]','pit.ch[4]'])
            advance(200);hlt_serviced=True
            ServiceDone(before)
        except Exception as e:fail.append(str(e));return True
        return False
class Step(gdb.Breakpoint):
    def stop(self):
        try:
            if num('*(unsigned int*)&mem[0x29000]')!=0x43504950:return False
            step=word(12)
            if step in [1,2]:advance(0)
            elif step==3:advance(125)
            elif step==4:advance(45)
            elif step==5:advance(10)
            elif step==6 and p['mode']==2:Service('*pit0_machine_service',internal=True)
        except Exception as e:fail.append(str(e));return True
        return False
class Read(gdb.Breakpoint):
    def stop(self):
        global latched_advanced
        try:
            if num('*(unsigned int*)&mem[0x29000]')==0x43504950 and word(12)==3 and not latched_advanced:
                advance(125);latched_advanced=True
        except Exception as e:fail.append(str(e));return True
        return False
gdb.execute('start',to_string=True)
assert (gdb.lookup_global_symbol('pit0_fake_sample') is not None)==(p['mode']==2)
Step('*(unsigned short*)&mem[0x2900c]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
Read('*pit_i71',internal=True)
class Done(gdb.Breakpoint):
    def stop(self):
        return num('*(unsigned int*)&mem[0x29000]')==0x43504950 and word(126)==2
Done('*(unsigned short*)&mem[0x2907e]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
gdb.execute('continue')
if fail:raise RuntimeError(fail)
assert word(126)==2,'terminal marker'
if p['mode']==2:assert hlt_serviced,'no controlled HLT'
data=bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval('&mem[0x29000]'),128))
(out/'result.bin').write_bytes(data)
(out/'service.json').write_text(json.dumps(log,indent=2)+'\n')
gdb.execute('kill',to_string=True)
'''
    (output/'capture.py').write_text('PARAMETERS='+repr(str(output/'parameters.json'))+'\n'+script)
    env=os.environ.copy()
    env.update(XDG_CONFIG_HOME=str(output/'xdg'),SDL_AUDIODRIVER='dummy',OMP_NUM_THREADS='1',LP_NUM_THREADS='1')
    with (output/'xvfb.log').open('wb') as xvlog:
        xv=subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.PIPE,stderr=xvlog)
    try:
        ready,_,_=select.select([xv.stdout],[],[],15)
        if not ready:raise RuntimeError('Xvfb startup')
        env['DISPLAY']=':'+xv.stdout.readline().decode().strip()
        with (output/'gdb.log').open('w') as log:
            subprocess.run(['gdb','-q','-batch','-ex','set pagination off','-ex','set confirm off',
                            '-ex','source '+str(output/'capture.py'),'--args',str(binary),str(image)],
                           cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90,check=True)
        result=verify_result((output/'result.bin').read_bytes(),mode,profile)
        service=json.loads((output/'service.json').read_text())
        if mode==2:
            a,b=service[:2]
            def pos(r):return (r['cpu_clock']+r['cpu_base']-r['cpu_remaining'])&0xffffffff
            assert 0 < ((pos(b)-pos(a))&0xffffffff) < 0x80000000
            assert a['ns']==b['ns']
        report.update(backend=backend,multiple=multiple,baseclock=baseclock,
                      binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                      result=result,source='private fake' if mode==2 else 'legacy CPU ledger',
                      live_realtime='NOT_QUALIFIED_DEBUGGER_CONTROLLED')
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='result'}),flush=True)
        print(result['state'],flush=True)
        return report
    finally:
        xv.terminate()
        try:xv.wait(timeout=5)
        except subprocess.TimeoutExpired:xv.kill();xv.wait()


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--binary',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--backend',choices=['i286','ia32'],required=True)
    ap.add_argument('--mode',type=int,choices=[1,2],default=2)
    ap.add_argument('--multiple',type=int,default=4)
    ap.add_argument('--baseclock',type=int,choices=[1996800,2457600],default=2457600)
    a=ap.parse_args();qualify(a.binary,a.output,a.backend,a.mode,a.multiple,a.baseclock)
