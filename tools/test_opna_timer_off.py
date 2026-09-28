#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare parent and default-OFF .text under identical configured flags."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PARENT='c05748f42ab75a80fc889fded1e6fb1f5b2cf2ea'
FILES=['pccore.c','io/pic.c','sound/opna.c','sound/opntimer.c','sound/fmboard.c','cbus/board86.c','sound/pcm86c.c','statsave.c','sdl/np2.c','i286c/i286c.c','i286c/v30patch.c','i386c/ia32/cpu.c','i386c/ia32/interface.c']

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    build=a.build.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    commands=json.loads((build/'compile_commands.json').read_text())
    target='sdlnp2kai_sdl2' if 'BUILD_I286:BOOL=ON' in (build/'CMakeCache.txt').read_text() else 'sdlnp21kai_sdl2'
    rows=[]
    for name in FILES:
        matches=[x for x in commands if x['file']==str(ROOT/name) and target+'.dir' in x['command']]
        if not matches and name.startswith(('i286c/','i386c/')):continue
        command=matches[0]
        argv=shlex.split(command['command'])
        if any(v.startswith('-DNP2_OPNA_TIMER_MACHINE_TIME') for v in argv):raise ValueError('OFF build required')
        texts=[]
        for which in ('parent','off'):
            dest=out/which/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(subprocess.check_output(['git','show',PARENT+':'+name],cwd=ROOT) if which=='parent' else (ROOT/name).read_bytes())
            obj=dest.with_suffix('.o');args=argv.copy();args[args.index('-o')+1]=str(obj);args[args.index('-c')+1]=str(dest)
            args[1:1]=['-iquote',str((ROOT/name).parent)]
            subprocess.run(args,cwd=command['directory'],check=True,stdout=subprocess.DEVNULL)
            text=dest.with_suffix('.text');subprocess.run(['objcopy','--dump-section','.text='+str(text),str(obj)],check=True)
            texts.append(text.read_bytes())
        rows.append(dict(file=name,bytes=len(texts[0]),equal=texts[0]==texts[1],
                         sha256=[hashlib.sha256(t).hexdigest() for t in texts]))
    (out/'report.json').write_text(json.dumps(dict(parent=PARENT,build=str(a.build),results=rows),indent=2)+'\n')
    if not all(r['equal'] for r in rows):raise RuntimeError('OFF codegen differs; see report')
    print('PASS: default OFF parent-identical .text for',len(rows),'material legacy objects',target)

if __name__=='__main__':main()
