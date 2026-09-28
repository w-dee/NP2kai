#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Private Tier1 real-body/fake-time qualification, both CPU compile profiles."""
import argparse,hashlib,json,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(a,**kw):return subprocess.run(list(map(str,a)),cwd=ROOT,check=True,**kw)
def extract(text,name):
 import re
 m=re.search(r'(?:static\s+)?(?:void|REG8|REG16|BOOL)\s+(?:(?:IOOUTCALL|IOINPCALL|DMACCALL)\s+)?'+name+r'\([^;]*?\)\s*\{',text)
 assert m,name
 pos=m.end();depth=1
 while depth:
  if text[pos]=='{':depth+=1
  if text[pos]=='}':depth-=1
  pos+=1
 return text[m.start():pos]+'\n'
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--build-only',action='store_true');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 (out/('build-report.json' if a.build_only else 'binding-report.json')).unlink(missing_ok=True)
 manifests={}
 selections={'io/pic.c':None,'io/serial.c':['keyboard_callback','keyboard_o41','keyboard_o43','keyboard_i41','keyboard_i43','keyboard_reset','keyboard_resetsignal','keyboard_ctrl','keyboard_send','keyboard_changeclock'], 'io/fdc.c':['fdc_intwait','fdc_interrupt','fdc_dmafunc','fdc_intdelay','get_hdus','FDC_Recalibrate','FDC_Seek'], 'io/gdc_sub.c':['gdcslavewait','gdcsub_setslavewait','calc_gdcslavewait'],'mem/dmax86.c':None}
 for f,names in selections.items():
  b=(ROOT/f).read_bytes();s=b.decode();body='\n'.join(l for l in s.splitlines() if not l.lstrip().startswith('#include'))+'\n' if names is None else '\n'.join(extract(s,n) for n in names)
  (out/(Path(f).stem+'-body.inc')).write_text(body);manifests[f]=dict(sha256=hashlib.sha256(b).hexdigest(),transform='includes removed only' if names is None else 'whole functions extracted unchanged',functions=names)
 from fractions import Fraction
 reference=[];compat=[]
 for base in [1996800,2457600]:
  for dots in [0,1,2,137,10000,4294967295]:
   k=22464 if base==1996800 else 27648
   duration=Fraction(dots*k,15625*base)+Fraction(30,base)
   ticks=duration*23462400000000;assert ticks.denominator==1
   reference.append((base,dots,int(ticks)))
   for m in [1,4,5,15,20]:
    defined=dots*k*m <= 2147483647
    old=Fraction((dots*k*m)//15625+30*m,base*m) if defined else None
    compat.append(dict(base=base,multiple=m,dots=dots,normalized_seconds=str(duration),legacy_defined=defined,legacy_seconds=str(old) if defined else None,delta_seconds=str(duration-old) if defined else None,fdc_normalized_seconds=str(Fraction(512,base)),fdc_legacy_seconds=str(Fraction(512,base*m))))
 (out/'expected-durations.inc').write_text('static const struct {unsigned base,dots;uint64_t q;} expected_durations[]={'+','.join('{%du,%du,UINT64_C(%d)}'%v for v in reference)+'};\n')
 (out/'compatibility-deltas.json').write_text(json.dumps(compat,indent=2)+'\n')
 results=[]
 for backend in ['i286','ia32']:
  cfg=out/f'build-{backend}';target='sdlnp2kai_sdl2' if backend=='i286' else 'sdlnp21kai_sdl2'
  with (out/f'configure-{backend}.log').open('w') as log:run(['cmake','-S',ROOT,'-B',cfg,'-DBUILD_I286='+('ON' if backend=='i286' else 'OFF'),'-DBUILD_WX=OFF','-DBUILD_SDL=ON','-DUSE_SDL=2','-DCMAKE_BUILD_TYPE=Debug','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON','-DNP2_TIER1_MACHINE_TIME=ON'],stdout=log,stderr=subprocess.STDOUT)
  if a.build_only:
   with (out/f'build-{backend}.log').open('w') as log:run(['cmake','--build',cfg,'--target',target,'-j4'],stdout=log,stderr=subprocess.STDOUT)
   continue
  rows=json.loads((cfg/'compile_commands.json').read_text());row=next(r for r in rows if r['file']==str(ROOT/'io/serial.c') and target+'.dir' in r['command'])
  base=[v for v in shlex.split(row['command']) if not v.startswith('-DNP2KAI_GIT_')]
  for sanitized in [False,True]:
   label=backend+('-san' if sanitized else '');objs=[]
   for source in [ROOT/'tests/time_domains/tier1/test_binding.c',ROOT/'tier1_machine.c',ROOT/'nevent.c',ROOT/'keystat.c']:
    obj=out/(label+'-'+source.stem+'.o');args=base[:];args[args.index('-c')+1]=str(source);args[args.index('-o')+1]=str(obj);args+=['-I'+str(out),'-UNDEBUG','-ffunction-sections','-fdata-sections']
    if sanitized:args+=['-O1','-fsanitize=undefined,address','-fno-sanitize-recover=all']
    run(args);objs.append(obj)
   exe=out/label;run(['cc','-Wl,--gc-sections',*objs,'-lm',*(['-fsanitize=undefined,address'] if sanitized else []),'-o',exe]);r=subprocess.check_output([str(exe)],text=True);print(r,end='');results.append(dict(build=label,result=r.strip()))
 (out/('build-report.json' if a.build_only else 'binding-report.json')).write_text(json.dumps(dict(status='PASS_TIER1_BUILDS' if a.build_only else 'PASS_TIER1_REAL_BODY_FAKE_TIME',results=results,sources=manifests),indent=2)+'\n')
if __name__=='__main__':main()
