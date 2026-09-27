#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministic, original N4 DOS-free 1.23 MB floppy builder."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from gdc_contract import MODES, PROFILES, geometry

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tests/guest/i286-time-gdc/src'
IMAGE_SIZE = 77 * 2 * 8 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(output, scan_class=24, mode=1):
    if scan_class not in PROFILES or mode not in MODES:
        raise ValueError('unsupported mode or scan class')
    sources = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in
               [SOURCE/'ipl.asm', SOURCE/'stage2.asm', Path(__file__).resolve(),
                Path(__file__).with_name('gdc_contract.py')]}
    identity = dict(schema=1, mode=mode, scan_class=scan_class, sources=sources)
    build_id = sha(json.dumps(identity, sort_keys=True).encode())[:16]
    m,s = geometry(scan_class)
    db = lambda b: 'db ' + ','.join(str(v) for v in b)
    inc = '\n'.join([f'%define RUN_MODE {mode}', f'%define SCAN_CLASS {scan_class}',
                     f'%define CLASS_SELECTOR {int(scan_class==31)}',
                     f'%define SLAVE_PITCH {80 if scan_class==31 else 40}',
                     '%define BUILD_ID '+db(bytes.fromhex(build_id)),
                     '%define MASTER_SYNC '+db(m), '%define SLAVE_SYNC '+db(s)])+'\n'
    with tempfile.TemporaryDirectory(prefix='n4-build-') as td:
        d = Path(td)
        (d/'n4.inc').write_text(inc)
        subprocess.run(['nasm','-f','bin','-I',str(d)+'/',str(SOURCE/'stage2.asm'),
                        '-o',str(d/'stage2.bin')],check=True)
        stage = (d/'stage2.bin').read_bytes()
        if len(stage) > 32768:
            raise ValueError('stage overlaps bounded load region')
        sectors = (len(stage)+1023)//1024
        subprocess.run(['nasm','-f','bin',f'-DSTAGE_SECTORS={sectors}',
                        f'-DSTAGE_BYTES={len(stage)}',str(SOURCE/'ipl.asm'),
                        '-o',str(d/'ipl.bin')],check=True)
        boot = (d/'ipl.bin').read_bytes()
    if len(boot)!=1024:
        raise ValueError('bootstrap size')
    image = (boot+stage).ljust(IMAGE_SIZE,b'\0')
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(image)
    manifest = dict(identity, build_id=build_id, mode_name=MODES[mode],
                    image_sha256=sha(image),image_size=len(image),
                    stage_size=len(stage),stage_sha256=sha(stage),boot_sha256=sha(boot),
                    guest_license='BSD-2-Clause',host_license='MIT',
                    nasm=subprocess.check_output(['nasm','-v'],text=True).strip())
    output.with_suffix(output.suffix+'.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scan-class',type=int,choices=PROFILES,default=24)
    p.add_argument('--mode',type=int,choices=MODES,default=1)
    a=p.parse_args()
    print(json.dumps(build(a.output,a.scan_class,a.mode),indent=2))

if __name__=='__main__':
    main()
