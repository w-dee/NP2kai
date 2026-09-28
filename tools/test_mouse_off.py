#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute pinned pre-N5 real source and candidate OFF on the same legacy corpus."""
import argparse,hashlib,json,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='ffba9b26ac176ba72da4e1aa2c0a508a4ab305df'
def main():
 p=argparse.ArgumentParser();p.add_argument('--build-root',type=Path,required=True);a=p.parse_args();baseout=a.build_root.resolve();out=baseout/'off';out.mkdir(exist_ok=True)
 reports=[]
 for backend in ['i286','ia32']:
  cfg=baseout/f'build-{backend}';rows=json.loads((cfg/'compile_commands.json').read_text());target='sdlnp2kai_sdl2.dir' if backend=='i286' else 'sdlnp21kai_sdl2.dir'
  row=next(r for r in rows if r['file']==str(ROOT/'io/mouseif.c') and target in r['command'])
  flags=[x for x in shlex.split(row['command']) if not x.startswith(('-DNP2KAI_GIT_','-DNP2_MOUSE_'))]
  results=[]
  for mode in ['parent','off']:
   dest=out/(backend+'-'+mode);dest.mkdir(exist_ok=True);manifest={}
   for name in ['io/mouseif.c','io/pic.c','sdl/mousemng.c','nevent.c']:
    raw=subprocess.check_output(['git','show',PARENT+':'+name],cwd=ROOT) if mode=='parent' else (ROOT/name).read_bytes()
    manifest[name]=hashlib.sha256(raw).hexdigest()
    if name in ['io/mouseif.c','io/pic.c']:
     text='\n'.join(l for l in raw.decode().splitlines() if not l.lstrip().startswith('#include'))+'\n';(dest/(Path(name).stem+'-body.inc')).write_text(text)
    else:(dest/Path(name).name).write_bytes(raw)
   objects=[]
   for source in [ROOT/'tests/time_domains/mouse/test_legacy.c',dest/'mousemng.c',dest/'nevent.c']:
    obj=dest/(source.stem+'.o');args=flags[:];args[args.index('-c')+1]=str(source);args[args.index('-o')+1]=str(obj)
    args+=['-I'+str(dest),'-O1','-UNDEBUG','-ffunction-sections','-fdata-sections','-fsanitize=address,undefined','-fno-sanitize-recover=all'];subprocess.run(args,check=True,cwd=ROOT);objects.append(str(obj))
   exe=dest/'probe';subprocess.run(['cc','-fsanitize=address,undefined','-Wl,--gc-sections',*objects,'-lm','-o',str(exe)],check=True)
   result=subprocess.check_output([str(exe)]);(dest/'trace.jsonl').write_bytes(result);results.append(result)
   (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  assert results[0]==results[1],backend+' OFF differs from pinned parent'
  reports.append(dict(backend=backend,records=len(results[0].splitlines()),sha256=hashlib.sha256(results[0]).hexdigest()))
 (out/'report.json').write_text(json.dumps(dict(status='PASS_N5_OFF_PINNED_PARENT_EXACT',parent=PARENT,cases=reports),indent=2)+'\n');print(reports)
if __name__=='__main__':main()
