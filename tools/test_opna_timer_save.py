#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile production OPNA Timer save APIs with a configured experimental build's flags."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--build',required=True,type=Path)
    a=p.parse_args()
    commands=json.loads((a.build/'compile_commands.json').read_text())
    target='sdlnp2kai_sdl2' if 'BUILD_I286:BOOL=ON' in (a.build/'CMakeCache.txt').read_text() else 'sdlnp21kai_sdl2'
    command=next(x for x in commands if x['file']==str(ROOT/'statsave.c') and target+'.dir' in x['command'])
    argv=shlex.split(command['command'])
    assert '-DNP2_OPNA_TIMER_MACHINE_TIME' in argv, 'experimental build required'
    with tempfile.TemporaryDirectory(prefix='opna-save-') as temp:
        tmp=Path(temp);obj=tmp/'save.o';binary=tmp/'save-test'
        argv[argv.index('-o')+1]=str(obj)
        argv[1:1]=['-ffunction-sections','-fdata-sections']
        subprocess.run(argv,cwd=command['directory'],check=True)
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-Wl,--gc-sections',str(ROOT/'tests/time_domains/test_artic_save.c'),
                        str(obj),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],cwd=tmp,check=True)
        assert sorted(f.name for f in tmp.iterdir())==['save-test','save.o']


if __name__=='__main__':main()
