#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Actual guest execution qualification; debugger controls only fake time."""
import argparse,hashlib,json,os,subprocess,shutil,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--backend',choices=['i286','ia32'],required=True);p.add_argument('--baseclock',type=int,choices=[1996800,2457600],default=2457600);p.add_argument('--multiple',type=int,default=4)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);binary=a.binary.resolve()
    subprocess.run(['nasm','-f','bin',str(ROOT/'tests/guest/opna-timer-n6/src/ipl.asm'),'-o',str(out/'ipl.bin')],check=True)
    boot=(out/'ipl.bin').read_bytes();assert len(boot)==1024 and boot[510:512]==boot[1022:1024]==b'\x55\xaa'
    image=out/'n6.hdm';image.write_bytes(boot+bytes(77*2*8*1024-1024))
    config=out/'xdg'/('sdlnp2kai' if a.backend=='i286' else 'sdlnp21kai');config.mkdir(parents=True,exist_ok=True)
    for name in ['bios.rom','font.rom']:shutil.copyfile(ROOT/'.local/oracle/pristine'/name,config/name)
    ini='np2kai.cfg' if a.backend=='i286' else 'np21kai.cfg';section='NekoProjectIIkai' if a.backend=='i286' else 'NekoProject21kai'
    (config/ini).write_text(f'[{section}]\nclk_base = {a.baseclock}\nclk_mult = {a.multiple}\npc_model = VX\nExMemory = 1\nSNDboard = 04\nopt86BRD = 7d\nUSEFMGEN = false\n')
    params=dict(out=str(out),backend=a.backend,baseclock=a.baseclock,multiple=a.multiple,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),image_sha256=hashlib.sha256(image.read_bytes()).hexdigest())
    (out/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    (out/'capture.py').write_text('PARAMETERS='+repr(str(out/'parameters.json'))+'\n'+(ROOT/'tests/guest/opna-timer-n6/capture.py').read_text())
    env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(out/'xdg'),SDL_AUDIODRIVER='dummy',SDL_VIDEODRIVER='dummy',OMP_NUM_THREADS='1')
    with (out/'gdb.log').open('w') as log:
        subprocess.run(['gdb','-q','-batch','-ex','set confirm off','-ex','set pagination off','-ex','set python print-stack full','-ex','set debuginfod enabled off','-ex','source '+str(out/'capture.py'),'--args',str(binary),str(image)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90,check=True)
    data=(out/'result.bin').read_bytes();w=lambda off:struct.unpack_from('<H',data,off)[0]
    assert data[16]==data[20]==0 and w(18)==8192
    assert data[22]==1 and data[24]&16 and w(26)==w(28)==0
    assert w(30)==2 and data[32]&16 and data[34]&16==0 and w(46)==0x2222 and w(48)==2 and w(126)==2
    log=json.loads((out/'service.json').read_text());assert log['hlt_serviced'] and log['cpu_frozen_service'] and log['frozen_cpu_progress']
    params.update(result='PASS_N6_CPU_OBSERVATION',claims='real guest frozen-time loop; masked publication; IF=0 delayed acceptance; ISR/EOI; HLT then next IRQ; no audio/physical timing claim')
    (out/'report.json').write_text(json.dumps(params,indent=2)+'\n');print(json.dumps(params))
if __name__=='__main__':main()
