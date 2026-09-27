#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify N3 under private Xvfb; read N3 result and RAM through stock GDB."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
from build_i286_time_n1 import ROOT
from build_i286_time_n3 import build, check_reference
from n3_contract import payload
from run_i286_time_n1 import BINARY, EXPECTED_BINARY, LIB, XDO, communicate_until, gdb_cmd
from verify_i286_time_n3 import verify_result


def main() -> None:
    out=ROOT/'.local/n3-fixture/qualification'
    out.mkdir(parents=True,exist_ok=True)
    report=build(out/'n3.hdm')
    check_reference(report)
    for name in ('report.json','failure.json','result.bin','screen.png','buffer-s7.bin','buffer-s8.bin'):
        (out/name).unlink(missing_ok=True)
    binary_hash=hashlib.sha256(BINARY.read_bytes()).hexdigest()
    if binary_hash!=EXPECTED_BINARY:raise RuntimeError('stock i286 binary identity mismatch')
    env=os.environ.copy()
    env['XDG_CONFIG_HOME']=str(ROOT/'.local/oracle/xdg')
    env['LD_LIBRARY_PATH']=str(LIB)+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    env['SDL_AUDIODRIVER']='dummy'
    env['OMP_NUM_THREADS']='1'
    env['OPENBLAS_NUM_THREADS']='1'
    xvlog=(out/'xvfb.log').open('wb')
    xv=subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],
                        stdout=subprocess.PIPE,stderr=xvlog)
    xvlog.close()
    gdb=None
    log=bytearray()
    try:
        ready,_,_=select.select([xv.stdout],[],[],15)
        if not ready:raise RuntimeError('Xvfb startup timeout')
        display=':'+xv.stdout.readline().decode().strip()
        env['DISPLAY']=display
        started=time.monotonic()
        emlog=(out/'emulator.log').open('wb')
        gdb=subprocess.Popen(['gdb','-q','--interpreter=mi2','--args',str(BINARY),str(out/'n3.hdm')],
                             cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=emlog)
        emlog.close()
        log=bytearray()
        log.extend(communicate_until(gdb,b'(gdb)',15))
        log.extend(gdb_cmd(gdb,'-gdb-set pagination off',b'^done'))
        log.extend(gdb_cmd(gdb,'-gdb-set mi-async on',b'^done'))
        log.extend(gdb_cmd(gdb,'-exec-run',b'^running',20))
        window=None
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            p=subprocess.run([str(XDO),'search','--onlyvisible','--name','Neko Project'],
                             env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=5)
            if p.returncode==0 and p.stdout.strip():
                window=p.stdout.decode().splitlines()[0]
                break
            if gdb.poll() is not None:raise RuntimeError('emulator exited before display')
            time.sleep(.2)
        if not window:raise RuntimeError('emulator window absent')
        state=0
        elapsed=0
        for attempt in range(25):
            time.sleep(1)
            log.extend(gdb_cmd(gdb,'-exec-interrupt --all',b'*stopped',25))
            dump=out/'result.bin'
            log.extend(gdb_cmd(gdb,f'-interpreter-exec console "dump binary memory {dump} &mem[0x29000] &mem[0x29100]"',b'^done',8))
            data=dump.read_bytes()
            state=data[252] if len(data)==256 and data[:4]==b'N3FD' else 0
            if state in (2,3):
                elapsed=round(time.monotonic()-started,3)
                break
            log.extend(gdb_cmd(gdb,'-exec-continue',b'^running',8))
        if state not in (2,3):raise RuntimeError(f'N3 result not terminal: state={state}')
        result=verify_result(data)
        # Read both DMA buffers independently and compare to generated sectors.
        buffer_reports = []
        for sector, start in ((7,0x40100),(8,0x40900)):
            dump = out/f'buffer-s{sector}.bin'
            log.extend(gdb_cmd(gdb,f'-interpreter-exec console "dump binary memory {dump} &mem[{start}] &mem[{start+1024}]"',b'^done',8))
            observed = dump.read_bytes()
            buffer_reports.append({'sector':sector, 'exact_equal':observed==payload(sector),
                                   'sha256':hashlib.sha256(observed).hexdigest()})
        exact = all(r['exact_equal'] for r in buffer_reports)
        log.extend(gdb_cmd(gdb,'-exec-continue',b'^running',8))
        time.sleep(.8)
        subprocess.run(['import','-display',display,'-window',window,str(out/'screen.png')],
                       env=env,check=True,timeout=12)
        (out/'gdb-mi.log').write_bytes(log)
        report.update({'emulator_sha256':binary_hash,'display':display,'elapsed_s':elapsed,
                       'xvfb_invocation':['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],
                       'emulator_invocation':[str(BINARY),str(out/'n3.hdm')],
                       'host_exact_data_equal':exact,'buffers':buffer_reports,'result':result})
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        if result['state']!='PASS' or not exact:raise SystemExit(1)
    except Exception as exc:
        (out/'failure.json').write_text(json.dumps({'state':'FAIL','error':str(exc)},indent=2)+'\n')
        raise
    finally:
        (out/'gdb-mi.log').write_bytes(log)
        if gdb and gdb.poll() is None:
            try:gdb.stdin.write(b'-gdb-exit\n');gdb.stdin.flush();gdb.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired):gdb.kill();gdb.wait()
        if xv.poll() is None:
            xv.terminate()
            try:xv.wait(timeout=5)
            except subprocess.TimeoutExpired:xv.kill();xv.wait()

if __name__=='__main__':main()
