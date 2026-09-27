#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify N1 with private Xvfb and stock i286, extracting guest RAM via GDB."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time
from build_i286_time_n1 import build, ROOT
from verify_i286_time_n1 import verify_result

BINARY=ROOT/'build-baseline-sdl2-i286/sdlnp2kai_sdl2'
EXPECTED_BINARY='a7e2e22ec3b2fede5885d1317d2c1cd754fd8139ac9794f0d6eeea1221af4fd6'
XDO=ROOT/'.local/automation/packages/root/usr/bin/xdotool'
LIB=ROOT/'.local/automation/packages/root/usr/lib/x86_64-linux-gnu'


def communicate_until(proc:subprocess.Popen, token:bytes, timeout:float) -> bytes:
    result=bytearray()
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        ready,_,_=select.select([proc.stdout],[],[],min(.2,max(0,deadline-time.monotonic())))
        if ready:
            chunk=os.read(proc.stdout.fileno(),65536)
            if not chunk: break
            result.extend(chunk)
            if token in result: return bytes(result)
        if proc.poll() is not None: break
    raise RuntimeError(f'GDB did not report {token!r}: {result[-2000:]!r}')


def gdb_cmd(proc, command:str, token:bytes, timeout=12) -> bytes:
    proc.stdin.write((command+'\n').encode())
    proc.stdin.flush()
    return communicate_until(proc,token,timeout)


def main() -> None:
    out=ROOT/'.local/n1-fixture/qualification'
    out.mkdir(parents=True,exist_ok=True)
    report=build(out/'n1.hdm')
    reference=json.loads((ROOT/'tests/guest/i286-time-n1/reference.json').read_text())
    if report['image_sha256'] != reference['image_sha256']:
        raise RuntimeError('N1 image differs from tracked reference')
    binary_hash=hashlib.sha256(BINARY.read_bytes()).hexdigest()
    if binary_hash!=EXPECTED_BINARY: raise RuntimeError('stock emulator binary identity mismatch')
    env=os.environ.copy()
    env['XDG_CONFIG_HOME']=str(ROOT/'.local/oracle/xdg')
    env['LD_LIBRARY_PATH']=str(LIB)+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    env['SDL_AUDIODRIVER']='dummy'
    env['OMP_NUM_THREADS']='1'
    env['OPENBLAS_NUM_THREADS']='1'
    xvlog=(out/'xvfb.log').open('wb')
    xv=subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.PIPE,stderr=xvlog)
    xvlog.close()
    gdb=None
    try:
        ready,_,_=select.select([xv.stdout],[],[],15)
        if not ready: raise RuntimeError('Xvfb start timeout')
        display=':'+xv.stdout.readline().decode().strip()
        env['DISPLAY']=display
        started=time.monotonic()
        gdb=subprocess.Popen(['gdb','-q','--interpreter=mi2','--args',str(BINARY),str(out/'n1.hdm')],
                             cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=(out/'emulator.log').open('wb'))
        log=bytearray()
        log.extend(communicate_until(gdb,b'(gdb)',15))
        log.extend(gdb_cmd(gdb,'-gdb-set pagination off',b'^done'))
        log.extend(gdb_cmd(gdb,'-gdb-set mi-async on',b'^done'))
        log.extend(gdb_cmd(gdb,'-exec-run',b'^running',20))
        window=None
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            p=subprocess.run([str(XDO),'search','--onlyvisible','--name','Neko Project'],env=env,
                             stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            if p.returncode==0 and p.stdout.strip():
                window=p.stdout.decode().splitlines()[0]
                break
            if gdb.poll() is not None: raise RuntimeError('emulator exited before display')
            time.sleep(.2)
        if not window: raise RuntimeError('emulator window absent')
        # Allow the guest to finish. Poll memory under GDB, never modify it.
        state=0
        elapsed=0
        for attempt in range(15):
            time.sleep(1)
            log.extend(gdb_cmd(gdb,'-exec-interrupt --all',b'*stopped',25))
            dump=out/'result.bin'
            command=f'-interpreter-exec console "dump binary memory {dump} &mem[0x29000] &mem[0x29100]"'
            log.extend(gdb_cmd(gdb,command,b'^done',8))
            data=dump.read_bytes()
            state=data[252] if len(data)==256 and data[:4]==b'N1TM' else 0
            if state in (2,3):
                elapsed=round(time.monotonic()-started,3)
                break
            log.extend(gdb_cmd(gdb,'-exec-continue',b'^running',8))
        if state not in (2,3): raise RuntimeError(f'guest did not publish terminal N1 result; state={state}')
        result=verify_result(data)
        # The emulator must run briefly after the guest's terminal write so
        # SDL can flush text VRAM into the Xvfb window before capture.
        log.extend(gdb_cmd(gdb,'-exec-continue',b'^running',8))
        time.sleep(.8)
        subprocess.run(['import','-display',display,'-window',window,str(out/'screen.png')],env=env,check=True,timeout=12)
        (out/'gdb-mi.log').write_bytes(log)
        report.update({'emulator_sha256':binary_hash,'display':display,'elapsed_s':elapsed,
                       'xvfb_invocation':['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],
                       'emulator_invocation':[str(BINARY),str(out/'n1.hdm')],
                       'result':result})
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        if result['state']!='PASS': raise SystemExit(1)
    finally:
        if gdb and gdb.poll() is None:
            try: gdb.stdin.write(b'-gdb-exit\n');gdb.stdin.flush();gdb.wait(timeout=5)
            except (OSError,subprocess.TimeoutExpired): gdb.kill();gdb.wait()
        if xv.poll() is None:
            xv.terminate()
            try:xv.wait(timeout=5)
            except subprocess.TimeoutExpired:xv.kill();xv.wait()

if __name__=='__main__':
    main()
