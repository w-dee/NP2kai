#!/usr/bin/env python3
"""Qualify bounded CSM semantic history against the complete fake-time SDL device binding."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CASES=['positive','capacity_plus_one','insufficient_first','insufficient_after_finalized','huge_gap','sequence_overflow','incomplete_prefix','retroactive_sequence','incompatible_base','corrupt_phase','corrupt_timer_state']
def run(binary,out,backend,baseclock,case):
    work=out/case;work.mkdir(parents=True,exist_ok=True)
    config=work/'xdg'/('sdlnp2kai' if backend=='i286' else 'sdlnp21kai');config.mkdir(parents=True,exist_ok=True)
    for name in ['bios.rom','font.rom']:shutil.copyfile(ROOT/'.local/oracle/pristine'/name,config/name)
    ini='np2kai.cfg' if backend=='i286' else 'np21kai.cfg'
    section='NekoProjectIIkai' if backend=='i286' else 'NekoProject21kai'
    (config/ini).write_text(f'[{section}]\nclk_base = {baseclock}\nclk_mult = 4\nSNDboard = 04\nopt86BRD = 7d\nUSEFMGEN = false\n')
    params=dict(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),backend=backend,baseclock=baseclock,case=case,out=str(work))
    (work/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
    (work/'capture.py').write_text('PARAMETERS='+repr(str(work/'parameters.json'))+'\n'+(ROOT/'tests/time_domains/opna_csm_history_binding.py').read_text())
    env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(work/'xdg'),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    with (work/'gdb.log').open('w') as log:
        subprocess.run(['gdb','-q','-batch','-ex','set confirm off','-ex','set pagination off','-ex','set python print-stack full','-ex','set debuginfod enabled off','-ex','source '+str(work/'capture.py'),'--args',str(binary)],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240,check=True)
    diagnostics=(work/'gdb.log').read_text()
    assert 'ERROR: AddressSanitizer' not in diagnostics and 'runtime error:' not in diagnostics,case
    report=json.loads((work/'report.json').read_text());assert report['result']=='PASS',report
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--backend',choices=['i286','ia32'],required=True);ap.add_argument('--baseclock',type=int,choices=[1996800,2457600],default=2457600)
    args=ap.parse_args();binary=args.binary.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    results=[run(binary,out,args.backend,args.baseclock,case) for case in CASES]
    (out/'report.json').write_text(json.dumps(dict(backend=args.backend,baseclock=args.baseclock,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),results=results),indent=2)+'\n')
    print('PASS',args.backend,args.baseclock,len(results),'CSM history fixture groups')
if __name__=='__main__':main()
