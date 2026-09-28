#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N4 mode-2 private qualification; guest source and RAM assertions are unchanged."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
from build_i286_time_gdc import ROOT,build,sha
from gdc_contract import reference_points,require,parse_result
from gdc_machine_contract import verify_machine
from gdc_machine_schedule import points, SCHEDULES

INPUTS=['pit0_time.h','pit0_machine.c','gdc_time.h','gdc_time.c','gdc_time_fake.c','gdc_time_posix.c','gdc_machine.h','gdc_machine.c',
        'pccore.c','io/gdc.c','io/pic.c','bios/bios18.c','bios/bios1c.c','mem/memtram.c','mem/memvram.c','mem/memegc.c','statsave.c','CMakeLists.txt','sdl/cpupacing.h','sdl/cpupacing.c','sdl/np2.c','i286c/i286c.c','i286c/v30patch.c','i386c/ia32/interface.c','i386c/ia32/cpu.c']
def source_id():return sha(''.join(f'{p}:{sha((ROOT/p).read_bytes())}\n' for p in INPUTS).encode())

def qualify(a):
    out=a.output.resolve();binary=a.binary.resolve()
    require(not out.exists() or not any(out.iterdir()),'stale output directory')
    out.mkdir(parents=True,exist_ok=True)
    require(not(a.backend=='i286' and a.scan_class==31),'UNSUPPORTED_GDC_SCAN_CLASS')
    cache=(binary.parent/'CMakeCache.txt').read_text()
    for flag in ['NP2_GDC_MACHINE_TIME:BOOL=ON','NP2_GDC_FAKE_TIME:BOOL=ON','USE_HAXM:BOOL=OFF','USE_ASYNCCPU:BOOL=OFF',f'NP2_GDC_PROFILE_BASE:STRING={a.profile_base}']:
        require(flag in cache,'unqualified build: '+flag)
    identity=source_id();bh=sha(binary.read_bytes())
    report=build(out/'gdc.hdm',a.scan_class,2)
    config=out/'xdg'/('sdlnp2kai' if a.backend=='i286' else 'sdlnp21kai');config.mkdir(parents=True)
    roms={}
    for name in ('bios.rom','font.rom'):
        src=ROOT/'.local/oracle/pristine'/name;roms[name]=sha(src.read_bytes());shutil.copyfile(src,config/name)
    section='NekoProjectIIkai' if a.backend=='i286' else 'NekoProject21kai'
    (config/('np2kai.cfg' if a.backend=='i286' else 'np21kai.cfg')).write_text(
        f'[{section}]\nclk_base = {a.baseclock}\nclk_mult = {a.multiple}\npc_model = VX\nExMemory = 1\nDIPswtch = {"3f" if a.scan_class==15 else "3e"} e3 7b\nDispSync = true\nReal_Pal = false\nASYNCCPU = false\n')
    params=dict(out=str(out),backend=a.backend,profile_base=a.profile_base,source_id=identity,
                points=points(a.scan_class,a.profile_base,a.schedule),schedule=a.schedule,suppress=int(a.suppress),diagnostic_stop=a.diagnostic_stop)
    (out/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    script=ROOT/'tools/guest/gdc_machine_capture.py'
    (out/'capture-entry.py').write_text('PARAMETERS='+repr(str(out/'parameters.json'))+'\nexec(compile(open('+repr(str(script))+').read(),'+repr(str(script))+',"exec"))\n')
    env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(out/'xdg'),SDL_AUDIODRIVER='dummy',OMP_NUM_THREADS='1',LP_NUM_THREADS='1')
    with (out/'xvfb.log').open('w') as log:
        xv=subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.PIPE,stderr=log)
    try:
        ready,_,_=select.select([xv.stdout],[],[],15);require(bool(ready),'Xvfb timeout')
        display=xv.stdout.readline().decode().strip();require(display.isdecimal(),'Xvfb failed');env['DISPLAY']=':'+display
        with (out/'gdb.log').open('w') as log:
            proc=subprocess.Popen(['gdb','-q','-batch','-ex','set pagination off','-ex','set confirm off','-ex','source '+str(out/'capture-entry.py'),'--args',str(binary),str(out/'gdc.hdm')],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            try:require(proc.wait(timeout=120)==0,'GDB failed')
            finally:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
        data=(out/'result.bin').read_bytes();records=parse_result(data,mode=2,scan_class=a.scan_class,build_id=report['build_id'])
        capture=json.loads((out/'machine-capture.json').read_text())
        result=verify_machine(records,capture,scan_class=a.scan_class,profile_base=a.profile_base,
                              baseclock=a.baseclock,multiple=a.multiple,schedule=a.schedule)
        require(identity==source_id() and bh==sha(binary.read_bytes()),'source/binary changed')
        report.update(state=result['state'],qualification=result,source_id=identity,binary_sha256=bh,rom_sha256=roms,
                      backend=a.backend,profile_base=a.profile_base,baseclock=a.baseclock,multiple=a.multiple,
                      suppress=a.suppress,schedule=a.schedule,host_sha256={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in (ROOT/"tools/guest").glob("*gdc*.py")},records=records,result_sha256=sha(data),capture_sha256=sha((out/'machine-capture.json').read_bytes()))
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('state','backend','scan_class','profile_base','baseclock','multiple','suppress')}),flush=True)
        return report
    finally:
        xv.terminate()
        try:xv.wait(timeout=5)
        except subprocess.TimeoutExpired:xv.kill();xv.wait()
        xv.stdout.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--backend',choices=['i286','ia32'],required=True);p.add_argument('--scan-class',type=int,choices=[15,24,31],default=24)
    p.add_argument('--profile-base',type=int,choices=[1996800,2457600],default=2457600);p.add_argument('--baseclock',type=int,choices=[1996800,2457600],default=2457600)
    p.add_argument('--multiple',type=int,choices=[1,4,5,20],default=5);p.add_argument('--suppress',action='store_true');p.add_argument('--diagnostic-stop',type=int,default=0)
    p.add_argument("--schedule",choices=SCHEDULES,default="canonical")
    qualify(p.parse_args())
