#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute the pinned parent PIT/PIC/NEVENT as M_ref=5 compatibility authority."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PARENT='1dbcac20adfa4aba5fe979fbf5ef371deed41686'
FILES=['io/pit.c','io/pic.c','io/pit.h','io/pic.h','nevent.c','nevent.h',
       'legacycpu.h','legacytime.h','timeshadow.h']
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    parent=out/'parent';manifest={}
    for name in FILES:
        data=subprocess.check_output(['git','show',PARENT+':'+name],cwd=ROOT)
        dest=parent/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        manifest[name]=hashlib.sha256(data).hexdigest()
    (out/'parent-manifest.json').write_text(json.dumps(dict(head=PARENT,files=manifest),indent=2)+'\n')
    math=out/'test-math'
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',
                    '-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT),
                    str(ROOT/'tests/time_domains/test_pit_math.c'),str(ROOT/'pit0_time.c'),
                    '-o',str(math)],check=True)
    subprocess.run([str(math)],check=True)
    # Only the binding can consume the source; time arithmetic cannot reach devices.
    binding=(ROOT/'pit0_machine.c').read_text()
    for forbidden in ['legacy_cpu','CPU_','multiple','artic','nevent','gdc','dmac','rs232c','beep']:
        assert forbidden not in binding, forbidden
    bios=(ROOT/'bios/bios1c.c').read_text()
    assert 'pit0_machine_service();\n#endif\n\t\t\tpic.pi[0].imr &= ~(PIC_SYSTEMTIMER);' in bios
    arithmetic=(ROOT/'pit0_time.c').read_text()
    assert 'while (' not in arithmetic and 'for (' not in arithmetic
    assert '#include <io/' not in arithmetic and '#include <cpucore' not in arithmetic
    sources=['pit0_time.c','pit0_time_fake.c','pit0_time_posix.c','pit0_machine.c','io/pit.c','io/pic.c']
    consumers=[name for name in sources if 'pit0_time_source()' in (ROOT/name).read_text()]
    assert consumers==['pit0_machine.c'], consumers
    (out/'isolation.json').write_text(json.dumps(dict(
        source_consumer=consumers,arithmetic_device_free=True,no_advancement_loop=True,
        mutation_scope='pit.ch[0].flag, pic.pi[0].irr bit0, private clock state',
        production_guest_service_snapshots='CPU, ARTIC, GDC, DMA, NEVENT and PIT channels1-4 checked by IPL runner',
        authority='ARCHITECTURAL_ASSERTION: implementation dataflow only'),indent=2)+'\n')
    results=[]
    for backend in ['i286','ia32']:
        bins={}
        for mode,source in [('parent',parent),('fake',ROOT)]:
            binary=out/(backend+'-'+mode);bins[mode]=binary
            command=['cc','-std=c99','-O2','-g','-Wall','-Wextra','-Werror',
                     '-Wno-unused-parameter','-Wno-unused-but-set-variable','-Wno-implicit-fallthrough','-Wno-unused-variable','-Wno-missing-field-initializers',
                     '-fsanitize=undefined','-fno-sanitize-recover=all',
                     '-I'+str(ROOT/'tests/time_domains/pit_stubs'),'-I'+str(source),'-I'+str(ROOT)]
            if backend=='ia32':command+=['-DCPUCORE_IA32']
            if mode=='fake':command+=['-DNP2_PIT_PIC_MACHINE_TIME',*[str(ROOT/n) for n in ['pit0_time.c','pit0_machine.c','pit0_time_fake.c']]]
            command += [str(ROOT/'tests/time_domains/test_pit_profile.c'),str(source/'nevent.c'),'-o',str(binary)]
            subprocess.run(command,check=True)
        for clock8 in [0,1]:
            expected=subprocess.check_output([str(bins['parent']),'5',str(clock8)])
            (out/f'{backend}-clock{clock8}-parent-m5.txt').write_bytes(expected)
            for mult in [1,4,20]:
                actual=subprocess.check_output([str(bins['fake']),str(mult),str(clock8)])
                if actual!=expected:
                    (out/'actual.txt').write_bytes(actual);(out/'expected.txt').write_bytes(expected)
                    e=expected.splitlines();b=actual.splitlines()
                    for i,(x,y) in enumerate(zip(e,b)):
                        if x!=y:raise AssertionError(f'{backend} clock{clock8} M{mult} line{i}: parent {x!r}, fake {y!r}')
                    raise AssertionError('length mismatch')
                results.append(dict(backend=backend,clock8=clock8,multiple=mult,observations=len(actual.splitlines()),sha256=hashlib.sha256(actual).hexdigest()))
                print(results[-1],flush=True)
    report=dict(result='PASS_PARENT_M5_DIFFERENTIAL',authority='LEGACY_COMPATIBILITY_ASSERTION',cases=results)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
