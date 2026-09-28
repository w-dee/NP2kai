#!/usr/bin/env python3
"""Bounded real PSG and owned-asset rhythm partition diagnostic."""
import argparse,hashlib,json,shlex,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--sanitizer',action='store_true');a=ap.parse_args();o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
 cfg=o/'cmake-profile';cfg.mkdir(exist_ok=True)
 with (cfg/'configure.log').open('w') as log:
  subprocess.run(['cmake','-S',str(ROOT),'-B',str(cfg),'-DBUILD_I286=ON','-DBUILD_WX=OFF',
   '-DBUILD_SDL=ON','-DUSE_SDL=2','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],check=True,stdout=log,stderr=subprocess.STDOUT)
 rows=json.loads((cfg/'compile_commands.json').read_text());base=shlex.split(next(x for x in rows if x['file']==str(ROOT/'sound/opngenc.c') and 'sdlnp2kai_sdl2.dir' in x['command'])['command']);base=[x for x in base if not x.startswith('-DNP2KAI_GIT_')]
 sources=[ROOT/'tests/host/audio_waveform_policy/other_sources_partition.c',ROOT/'sound/psggenc.c',ROOT/'sound/psggeng.c',ROOT/'sound/rhythmc.c',ROOT/'sound/pcmmix.c']
 objs=[];commands=[]
 for src in sources:
  obj=o/(src.stem+'.o');cmd=base[:];cmd[cmd.index('-c')+1]=str(src);cmd[cmd.index('-o')+1]=str(obj);cmd+=['-UNDEBUG','-ffunction-sections','-fdata-sections']
  if a.sanitizer:
   cmd+=['-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all']
   if src.name=='psggeng.c':cmd+=['-fwrapv']  # native PSG phase counter intentionally wraps
  subprocess.run(cmd,check=True);objs.append(str(obj));commands.append(cmd)
 exe=o/'other_sources';cmd=['cc','-Wl,--gc-sections',*objs,'-lm',*(['-fsanitize=address,undefined'] if a.sanitizer else []),'-o',str(exe)];subprocess.run(cmd,check=True);commands.append(cmd)
 (o/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 result=[]
 for rate in [44100,48000]:
  for kind in [0,1]:
   reference=None
   for q in [0,1,17,137,240,511]:
    tag=f'{"psg" if kind==0 else "rhythm"}-{rate}-q{q}';pcm=o/(tag+'.s32le');state=o/(tag+'.state')
    subprocess.run([str(exe),str(rate),str(kind),str(q),str(pcm),str(state)],check=True)
    data=pcm.read_bytes();s=state.read_text()
    if reference is None:reference=(data,s)
    dif=[i//8 for i in range(0,len(data),8) if data[i:i+8]!=reference[0][i:i+8]]
    result.append(dict(source='PSG' if kind==0 else 'RHYTHM_OWNED_ASSET',rate=rate,partition=q,
     pcm_sha256=hashlib.sha256(data).hexdigest(),state=s.strip(),first_differing_frame=dif[0] if dif else None,
     changed_frames=len(dif),state_equal=s==reference[1]))
 (o/'report.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PSG/rhythm results',[(s,r,sum(x['changed_frames']>0 or not x['state_equal'] for x in result if x['source']==s and x['rate']==r)) for s in ['PSG','RHYTHM_OWNED_ASSET'] for r in [44100,48000]])
if __name__=='__main__':main()
