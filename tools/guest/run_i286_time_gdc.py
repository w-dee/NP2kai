#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N4 Linux x86_64 private GDB/Xvfb runner; all current captures are read-only."""
import argparse
import json
import os
from pathlib import Path
import platform
import select
import shutil
import signal
import subprocess

from build_i286_time_gdc import ROOT, build, sha
from gdc_contract import MODES, PROFILES, clocks, geometry, require, verify_result

FUTURE_SYMBOLS=('gdc_fake_sample','gdc_machine_service')  # proposed private seam


def source_identity():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    sources={name:sha((ROOT/name).read_bytes()) for name in paths if name and
             (Path(name).suffix in ('.c','.cpp','.h','.S','.cmake') or name=='CMakeLists.txt')}
    for name in ('gdc_capture.py','run_i286_time_gdc.py'):
        sources['tools/guest/'+name]=sha((ROOT/'tools/guest'/name).read_bytes())
    return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                source_sha256=sources)


def validate_capture(capture, result, *, backend, scan_class, baseclock, multiple):
    require(not capture['errors'], 'capture errors')
    trace=capture['trace']
    require([s['case'] for s in trace]==list(range(1,29)), 'missing/duplicate sample checkpoints')
    require(len(capture['reads'])==56, 'missing direct status reads')
    core='i286core.s' if backend=='i286' else 'i386core.s'
    for s,r in zip(trace,result['records']):
        require(all(core+'.'+field in s for field in ('clock','baseclock','remainclock')), 'captured backend identity')
        require(s['token']==0x2000+r['case'], 'trace case freshness')
        require((s['pccore.baseclock'],s['pccore.multiple'])==(baseclock,multiple),'runtime clock identity')
        require(s['np2cfg.RASTER']==0 and s['np2cfg.DISPSYNC']==1,'RASTER/DISPSYNC/async admission')
        require(bool(s['gdc.crt15khz']&2)==(scan_class==15) and
                bool(s['gdc.display']&128)==(scan_class==31),'actual scan class')
        m,sl=geometry(scan_class,r['case']==27)
        require(s['master_sync']==list(m) and s['slave_sync']==list(sl),'committed SYNC mismatch')
        expected=clocks(scan_class,baseclock,multiple,r['case']==27)
        require(all(s['gdc.'+k]==v for k,v in expected.items()),'committed clock model mismatch')
        for port,key in ((0x60,'master'),(0xa0,'slave')):
            values=[v['raw'] for v in capture['reads'] if v['case']==r['case'] and v['port']==port]
            require(values==[r[key]],'guest RAM differs from real status return')
    def position(s):
        return (s[core+'.clock']+s[core+'.baseclock']-s[core+'.remainclock'])&0xffffffff
    require(0 < ((position(trace[15])-position(trace[14]))&0xffffffff) < 0x80000000,
            'no positive CPU ledger progress during guest work')
    require(trace[20]['events']['screenvsync']-trace[19]['events']['screenvsync']>=2,
            'ISR did not span repeated VSync callbacks')
    return dict(committed_geometry_verified=True,direct_status_returns_verified=56,
                isr_spanned_repeated_frames=True,backend=backend,
                timing_authority='legacy observation; debugger affects host pacing')


def qualify(binary,output,backend,mode,scan_class,multiple,baseclock,profile_base,timeout):
    require(platform.system()=='Linux' and platform.machine()=='x86_64','requires Linux x86_64 GDB ABI')
    require(multiple>0 and multiple<=32,'runtime multiplier range')
    binary,output=Path(binary).resolve(),Path(output).resolve()
    require(binary.is_file(),'binary missing')
    require(not output.exists() or not any(output.iterdir()),'refusing stale/nonempty output directory')
    output.mkdir(parents=True,exist_ok=True)
    symbols=subprocess.check_output(['nm','-a',str(binary)],text=True)
    names={line.split()[-1] for line in symbols.splitlines() if line.split()}
    if mode==2:
        present={name:name in names for name in FUTURE_SYMBOLS}
        report=dict(state='NOT_EXECUTABLE_UNTIL_MACHINE_TIME_GDC',mode=MODES[mode],
                    proposed_private_symbols=present,qualified_adapter=False,
                    binary_sha256=sha(binary.read_bytes()),
                    reason='Product fake-time binding and qualified adapter are required; no guest/state writes attempted.')
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        raise ValueError(report['state'])
    if scan_class==31 and 'gdc_o9a8' not in names:
        report=dict(state='UNSUPPORTED_GDC_SCAN_CLASS',backend=backend,scan_class=scan_class,
                    binary_sha256=sha(binary.read_bytes()),
                    reason='Binary lacks the SUPPORT_CRT31KHZ port 9A8 handler; stock i286 excludes this feature.')
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        raise ValueError(report['state'])
    require(profile_base==baseclock,'legacy observation cannot decouple runtime and display base')
    cache=binary.parent/'CMakeCache.txt'
    require(cache.is_file(),'CMake build identity required')
    cache_text=cache.read_text()
    require('USE_HAXM:BOOL=OFF' in cache_text and 'USE_ASYNCCPU:BOOL=OFF' in cache_text,
            'interpreter/no-async build required')
    identity=source_identity()
    binary_hash=sha(binary.read_bytes())
    report=build(output/'gdc.hdm',scan_class,mode)
    config=output/'xdg'/('sdlnp2kai' if backend=='i286' else 'sdlnp21kai')
    config.mkdir(parents=True)
    rom_hashes={}
    for name in ('bios.rom','font.rom'):
        source=ROOT/'.local/oracle/pristine'/name
        rom_hashes[name]=sha(source.read_bytes())
        shutil.copyfile(source,config/name)
    section='NekoProjectIIkai' if backend=='i286' else 'NekoProject21kai'
    ini=config/('np2kai.cfg' if backend=='i286' else 'np21kai.cfg')
    ini.write_text(f'[{section}]\nclk_base = {baseclock}\nclk_mult = {multiple}\npc_model = VX\n'
                   f'ExMemory = 1\nDIPswtch = {PROFILES[scan_class]["dip"]:02x} e3 7b\n'
                   'DispSync = true\nReal_Pal = false\nASYNCCPU = false\n')
    ini_hash=sha(ini.read_bytes())
    params=dict(out=str(output),backend=backend,mode=mode)
    (output/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    capture=ROOT/'tools/guest/gdc_capture.py'
    (output/'capture-entry.py').write_text('PARAMETERS='+repr(str(output/'parameters.json'))+'\n'+
        'exec(compile(open('+repr(str(capture))+').read(), '+repr(str(capture))+', "exec"))\n')
    env=os.environ.copy()
    env.update(XDG_CONFIG_HOME=str(output/'xdg'),SDL_AUDIODRIVER='dummy',OMP_NUM_THREADS='1',LP_NUM_THREADS='1')
    with (output/'xvfb.log').open('wb') as log:
        xv=subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],
                            stdout=subprocess.PIPE,stderr=log)
    try:
        ready,_,_=select.select([xv.stdout],[],[],15)
        require(bool(ready),'Xvfb startup timeout')
        display=xv.stdout.readline().decode().strip()
        require(display.isdecimal(),'Xvfb display allocation')
        env['DISPLAY']=':'+display
        with (output/'gdb.log').open('w') as log:
            proc=subprocess.Popen(['gdb','-q','-batch','-ex','set pagination off','-ex','set confirm off',
                '-ex','source '+str(output/'capture-entry.py'),'--args',str(binary),str(output/'gdc.hdm')],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                require(proc.wait(timeout=timeout)==0,'GDB capture failed; see gdb.log')
            finally:
                # GDB may leave an inferior on script failure; clean the dedicated group.
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait()
        data=(output/'result.bin').read_bytes()
        result=verify_result(data,mode=mode,scan_class=scan_class,build_id=report['build_id'])
        captured=json.loads((output/'capture.json').read_text())
        checks=validate_capture(captured,result,backend=backend,scan_class=scan_class,
                                baseclock=baseclock,multiple=multiple)
        require(identity==source_identity(),'source changed during run')
        require(binary_hash==sha(binary.read_bytes()),'binary changed during run')
        require(report['image_sha256']==sha((output/'gdc.hdm').read_bytes()),'image changed during run')
        for name,value in rom_hashes.items():
            require(value==sha((config/name).read_bytes())==sha((ROOT/'.local/oracle/pristine'/name).read_bytes()),
                    'ROM changed during run')
        (output/'source-manifest.json').write_text(json.dumps(identity,indent=2)+'\n')
        report.update(state=result['state'],backend=backend,binary_sha256=binary_hash,
                      build_cache_sha256=sha(cache.read_bytes()),source_head=identity['head'],
                      source_manifest_sha256=sha((output/'source-manifest.json').read_bytes()),
                      rom_sha256=rom_hashes,initial_config_sha256=ini_hash,
                      runtime=dict(baseclock=baseclock,multiple=multiple),
                      display_profile=dict(base_family=profile_base,M_ref=5,scan_class=scan_class,
                          authority='LEGACY_COMPATIBILITY_PROFILE',
                          frozen_M5_clocks=clocks(scan_class,profile_base)),
                      result_sha256=sha(data),capture_sha256=sha((output/'capture.json').read_bytes()),
                      result=result,capture_checks=checks,RASTER=0,
                      future='NOT_EXECUTABLE_UNTIL_MACHINE_TIME_GDC')
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(state=report['state'],backend=backend,scan_class=scan_class,
                             image_sha256=report['image_sha256'])),flush=True)
        return report
    finally:
        xv.terminate()
        try:xv.wait(timeout=5)
        except subprocess.TimeoutExpired:xv.kill();xv.wait()
        xv.stdout.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--backend',required=True,choices=['i286','ia32'])
    ap.add_argument('--mode',type=int,choices=MODES,default=1)
    ap.add_argument('--scan-class',type=int,choices=PROFILES,default=24)
    ap.add_argument('--multiple',type=int,default=5)
    ap.add_argument('--baseclock',type=int,choices=[1996800,2457600],default=2457600)
    ap.add_argument('--profile-base',type=int,choices=[1996800,2457600],default=None)
    ap.add_argument('--timeout',type=int,default=90)
    a=ap.parse_args()
    qualify(a.binary,a.output,a.backend,a.mode,a.scan_class,a.multiple,a.baseclock,
            a.profile_base or a.baseclock,a.timeout)

if __name__=='__main__':
    main()
