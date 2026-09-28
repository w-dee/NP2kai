#!/usr/bin/env python3
"""Native BEEP partition diagnosis; differences are reported, not normalized."""
from pathlib import Path
import argparse,hashlib,json,shlex,subprocess
ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(data).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--sanitizer',action='store_true');a=ap.parse_args()
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 cfg=out/'cmake-profile';cfg.mkdir(exist_ok=True)
 with (cfg/'configure.log').open('w') as log:
  subprocess.run(['cmake','-S',str(ROOT),'-B',str(cfg),'-DBUILD_I286=ON',
                  '-DBUILD_WX=OFF','-DBUILD_SDL=ON','-DUSE_SDL=2','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],
                 check=True,stdout=log,stderr=subprocess.STDOUT)
 row=next(x for x in json.loads((cfg/'compile_commands.json').read_text())
          if x['file']==str(ROOT/'sound/opngenc.c') and 'sdlnp2kai_sdl2.dir' in x['command'])
 base=[x for x in shlex.split(row['command']) if not x.startswith('-DNP2KAI_GIT_')]
 commands=[];objs=[]
 for src in [ROOT/'tests/host/audio_waveform_policy/beep_partition.c',ROOT/'sound/beepg.c']:
  obj=out/(src.stem+'.o');cmd=base[:];cmd[cmd.index('-c')+1]=str(src);cmd[cmd.index('-o')+1]=str(obj)
  cmd+=['-UNDEBUG','-ffunction-sections','-fdata-sections']
  if a.sanitizer:cmd+=['-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all']
  subprocess.run(cmd,check=True);commands.append(cmd);objs.append(str(obj))
 exe=out/'beep_partition';cmd=['cc','-Wl,--gc-sections',*objs,'-lm',*(['-fsanitize=address,undefined'] if a.sanitizer else []),'-o',str(exe)]
 subprocess.run(cmd,check=True);commands.append(cmd);(out/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 rows=[]
 for rate in [44100,48000]:
  for mode in [0,1]:
   basepcm=basestate=None
   for q in [0,1,17,137]:
    tag=f'beep-r{rate}-mode{mode}-q{q}';pcm=out/(tag+'.s32le');state=out/(tag+'.state')
    subprocess.run([str(exe),str(rate),str(mode),str(q),str(pcm),str(state)],check=True)
    data=pcm.read_bytes();s=state.read_text().strip()
    if q==0:basepcm=data;basestate=s
    diff=[i//8 for i in range(0,len(data),8) if data[i:i+8]!=basepcm[i:i+8]]
    rows.append(dict(rate=rate,mode=mode,partition=q,frames=128,pcm_bytes=len(data),
      pcm_sha256=digest(data),state=s,first_differing_frame=diff[0] if diff else None,
      changed_frames=len(diff),state_equal=s==basestate))
 assert any(r['changed_frames']>0 for r in rows if r['mode']==0 and r['partition']>0)
 assert any(r['changed_frames']>0 for r in rows if r['mode']==1 and r['partition']>0)
 (out/'report.json').write_text(json.dumps(dict(profile='LEGACY_NATIVE_BEEP_DIAGNOSTIC',
  result='BOTH_MODES_PARTITION_SENSITIVE',rows=rows),indent=2)+'\n')
 print('BEEP both native modes partition-sensitive at 44100/48000; see report.json')
if __name__=='__main__':main()
