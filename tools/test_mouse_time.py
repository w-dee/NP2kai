#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded normalized mouse math and real mouse/PIC binding qualification."""
import argparse,json,shlex,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(args):subprocess.run(list(map(str,args)),cwd=ROOT,check=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 exe=out/'math'
 run(['cc','-std=c99','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I',ROOT,ROOT/'mouse_time.c',ROOT/'tests/time_domains/mouse/test_math.c','-o',exe]);run([exe])
 manifest={}
 for name in ['mouseif','pic']:
  source=ROOT/'io'/f'{name}.c';data=source.read_bytes();body='\n'.join(l for l in data.decode().splitlines() if not l.lstrip().startswith('#include'))+'\n'
  (out/f'{name}-body.inc').write_text(body);manifest[str(source.relative_to(ROOT))]=dict(sha256=hashlib.sha256(data).hexdigest(),transform='remove include lines only; compile actual function bodies')
 results=[]
 for backend in ['i286','ia32']:
  cfg=out/f'build-{backend}'
  with (out/f'configure-{backend}.log').open('w') as log:
   subprocess.run(['cmake','-S',str(ROOT),'-B',str(cfg),'-DBUILD_I286='+('ON' if backend=='i286' else 'OFF'),'-DBUILD_WX=OFF','-DBUILD_SDL=ON','-DUSE_SDL=2','-DCMAKE_BUILD_TYPE=Debug','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DNP2_MOUSE_MACHINE_TIME=ON','-DNP2_MOUSE_FAKE_TIME=ON'],check=True,stdout=log,stderr=subprocess.STDOUT)
  rows=json.loads((cfg/'compile_commands.json').read_text());target='sdlnp2kai_sdl2.dir' if backend=='i286' else 'sdlnp21kai_sdl2.dir'
  row=next(r for r in rows if r['file']==str(ROOT/'io/mouseif.c') and target in r['command'])
  base=[x for x in shlex.split(row['command']) if not x.startswith('-DNP2KAI_GIT_')]
  for san in [False,True]:
   label=backend+('-san' if san else '');objects=[];commands=[]
   for source in [ROOT/'tests/time_domains/mouse/test_binding.c',ROOT/'mouse_time.c',ROOT/'mouse_machine.c',ROOT/'nevent.c']:
    obj=out/(label+'-'+source.stem+'.o');args=base[:];args[args.index('-c')+1]=str(source);args[args.index('-o')+1]=str(obj)
    args+=['-I'+str(out),'-UNDEBUG','-ffunction-sections','-fdata-sections']
    if san:args+=['-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all']
    run(args);objects.append(obj);commands.append(args)
   exe=out/label;args=['cc','-Wl,--gc-sections',*objects,'-lm',*(['-fsanitize=address,undefined'] if san else []),'-o',exe];run(args)
   result=subprocess.check_output([str(exe)],text=True);print(result,end='');results.append(dict(build=label,result=result.strip()))
   (out/(label+'-commands.json')).write_text(json.dumps(commands,indent=2)+'\n')
 (out/'binding-report.json').write_text(json.dumps(dict(status='PASS_N5_BOUNDED_MATH_AND_BINDING',authority='OWNER_APPROVED_NORMALIZED_PROFILE',guest_isr=False,results=results,sources=manifest),indent=2)+'\n')
if __name__=='__main__':main()
