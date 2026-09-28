#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stopped-owner qualification using the complete SDL production binary.
No replacement OPNA, board86, I/O, PCM86, PIC or NEVENT implementation.
CPU acceptance is separately qualified by the N6 IPL runner.
"""
import argparse,hashlib,json,os,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--backend',choices=['i286','ia32'],default='i286')
    p.add_argument('--baseclock',type=int,choices=[1996800,2457600],default=2457600)
    p.add_argument('--multiple',type=int,default=4)
    p.add_argument('--mode',choices=['fake','legacy'],default='fake')
    p.add_argument('--negative',choices=['board','fmgen','adpcm','csm','pcm','base'])
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);binary=a.binary.resolve()
    config=out/'xdg'/('sdlnp2kai' if a.backend=='i286' else 'sdlnp21kai');config.mkdir(parents=True,exist_ok=True)
    for name in ['bios.rom','font.rom']:shutil.copyfile(ROOT/'.local/oracle/pristine'/name,config/name)
    ini='np2kai.cfg' if a.backend=='i286' else 'np21kai.cfg';section='NekoProjectIIkai' if a.backend=='i286' else 'NekoProject21kai'
    (config/ini).write_text(f'[{section}]\nclk_base = {a.baseclock}\nclk_mult = {a.multiple}\nSNDboard = 04\nopt86BRD = 7d\nUSEFMGEN = false\n')
    params=dict(negative=a.negative,backend=a.backend,baseclock=a.baseclock,multiple=a.multiple,mode=a.mode,out=str(out),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    (out/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    script=out/'capture.py';script.write_text('PARAMETERS='+repr(str(out/'parameters.json'))+'\n'+(ROOT/'tests/time_domains/opna_timer_binding.py').read_text())
    env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(out/'xdg'),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    with (out/'gdb.log').open('w') as log:
        subprocess.run(['gdb','-q','-batch','-ex','set confirm off','-ex','set pagination off','-ex','set python print-stack full','-ex','set debuginfod enabled off','-ex','source '+str(script),'--args',str(binary)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240,check=True)
    result=json.loads((out/'report.json').read_text());assert result['result']=='PASS',result
    print(json.dumps(result))
if __name__=='__main__':main()
