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
from artic_contract import expected_samples, verify_result
from build_i286_time_artic import build, ROOT


def qualify(binary, output, backend, mode, multiple, baseclock):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('private GDB runner requires Linux x86_64 host ABI')
    binary, output = Path(binary).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = output/'artic.hdm'
    report = build(image, mode)
    config = output/'xdg'/('sdlnp2kai' if backend == 'i286' else 'sdlnp21kai')
    config.mkdir(parents=True, exist_ok=True)
    for name in ('bios.rom','font.rom'):
        shutil.copyfile(ROOT/'.local/oracle/pristine'/name,config/name)
    ini = 'np2kai.cfg' if backend == 'i286' else 'np21kai.cfg'
    section = 'NekoProjectIIkai' if backend == 'i286' else 'NekoProject21kai'
    (config/ini).write_text(f'[{section}]\nclk_base = {baseclock}\nclk_mult = {multiple}\npc_model = VX\nExMemory = 1\n')
    params = dict(out=str(output), samples=expected_samples(), backend=backend, mode=mode,
                  multiple=multiple, baseclock=baseclock)
    (output/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    # GDB sees only a private host test source. No guest command/API is added.
    script = r'''
import gdb,json
from pathlib import Path
p=json.loads(Path(PARAMETERS).read_text());out=Path(p['out']);samples=p['samples']
log=[];fail=[];index=0
core='i286core.s' if p['backend']=='i286' else 'i386core.s'
def number(e): return int(gdb.parse_and_eval(e))
def snap(names):
    result={}
    for name in names:
        v=gdb.parse_and_eval(name)
        result[name]=bytes(gdb.selected_inferior().read_memory(v.address,v.type.sizeof)).hex()
    return result
class DoneRead(gdb.FinishBreakpoint):
    def __init__(self,row,before):
        super().__init__(gdb.newest_frame(),internal=True);self.row=row;self.before=before
    def stop(self):
        try:
            row=self.row
            row['observed']=number('$eax')&65535
            row['after']=snap([core,'pic','pit','gdc','dmac'])
            row['no_other_mutation']=row['after']==self.before
            if p['mode']==2:
                row['phase']=number('artic_machine_time.phase')
                row['remainder']=number('artic_machine_time.remainder')
                row['rejected']=number('artic_machine_time.rejected')
                assert row['observed']==row['expected'],row
                assert row['phase']==row['expected_phase'],row
                assert row['remainder']==row['expected_remainder'],row
                assert row['no_other_mutation'],row
            log.append(row)
            if len(log)==len(samples):
                gdb.execute('watch -l *(unsigned short*)&mem[0x2921e]',to_string=True)
        except Exception as e: fail.append(str(e));return True
        return False
class Read(gdb.Breakpoint):
    def stop(self):
        global index
        try:
            if number('*(unsigned int*)&mem[0x29000]')!=0x43545241: return False
            assert index<len(samples),'unexpected extra ARTIC read'
            s=samples[index];index+=1
            assert number('$edi')==s['port'],'guest port sequence'
            assert number('pccore.multiple')==p['multiple'],'multiplier config'
            assert number('pccore.baseclock')==p['baseclock'],'base config'
            before=snap([core,'pic','pit','gdc','dmac'])
            if p['mode']==2:
                gdb.execute('set variable artic_fake_sample.ns = '+str(s['ns']),to_string=True)
                gdb.execute('set variable artic_fake_sample.valid = '+str(s['valid']),to_string=True)
            row=dict(sequence=index,case=s['case'],ns=s['ns'],valid=s['valid'],port=s['port'],
                     expected=s['expected'],expected_phase=s['phase'],expected_remainder=s['remainder'],
                     cpu_clock=number(core+'.clock'),cpu_base=number(core+'.baseclock'),
                     cpu_remaining=number(core+'.remainclock'),before=before)
            DoneRead(row,before)
        except Exception as e:fail.append(str(e));return True
        return False
gdb.execute('start',to_string=True)
experimental=gdb.lookup_global_symbol('artic_machine_time') is not None
fake=gdb.lookup_global_symbol('artic_fake_sample') is not None
assert (experimental,fake)==((True,True) if p['mode']==2 else (False,False)), 'binary/source mode mismatch'
Read('*artic_r16',internal=True)
gdb.execute('continue')
if fail: raise RuntimeError(fail)
assert number('*(unsigned short*)&mem[0x2921e]') in (2,3),'no terminal fixture result'
assert index==len(samples) and len(log)==len(samples),'missing real reads'
data=bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval('&mem[0x29000]'),544))
(out/'result.bin').write_bytes(data)
(out/'reads.json').write_text(json.dumps(log,indent=2)+'\n')
if p['mode']==2:
    assert number('artic_machine_time.rejected')==2,'invalid/backward count'
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
        result=verify_result((output/'result.bin').read_bytes(),mode)
        reads=json.loads((output/'reads.json').read_text())
        if mode==2:
            def position(row): return (row['cpu_clock']+row['cpu_base']-row['cpu_remaining']) & 0xffffffff
            assert 0 < ((position(reads[7])-position(reads[5])) & 0xffffffff) < 0x80000000
            assert reads[7]['phase']==reads[5]['phase'], 'F08 frozen source'
            assert reads[8]['phase']-reads[7]['phase']==6144, 'F09 twenty ms'
            assert all(r['no_other_mutation'] for r in reads)

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
