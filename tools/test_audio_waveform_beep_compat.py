#!/usr/bin/env python3
"""Controlled same-control-event legacy/native versus normalized BEEP deltas."""
from pathlib import Path
import argparse,json,shlex,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_audio_waveform_beep_continuous as bee
import test_audio_waveform_policy as fm
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tests/host/audio_waveform_policy'
CASES={
 'mode0_steady':[(0,0,0),(0,1,180),(3000,9,0)],
 'mode0_word':[(0,0,0),(0,1,0x1234),(137,1,0xff00),(721,1,0x4020),(3000,9,0)],
 'mode0_burst':[(0,0,0),(0,1,0),(137,1,255),(240,1,0),(3000,9,0)],
 'mode0_transition':[(0,0,0),(0,1,180),(501,1,24),(721,1,255),(1500,1,0),(3000,9,0)],
 'mode0_same_frontier':[(0,0,0),(0,1,180),(137,1,24),(137,1,255),(3000,9,0)],
 'mode0_reset_tail':[(0,0,0),(0,1,255),(1237,4,0),(1237,0,0),(1237,1,0),(4000,9,0)],
 'mode1_steady':[(0,0,1),(0,2,5000),(0,3,1),(3000,9,0)],
 'mode1_edge_start':[(0,0,1),(0,2,5000),(137,3,1),(3000,9,0)],
 'mode1_edge_stop':[(0,0,1),(0,2,5000),(0,3,1),(721,3,0),(3000,9,0)],
 'mode1_burst':[(0,0,1),(0,2,5000),(137,3,1),(240,3,0),(3000,9,0)],
 'mode1_frequency':[(0,0,1),(0,2,5000),(0,3,1),(1000,2,1337),(3000,9,0)],
 'mode1_same_frontier':[(0,0,1),(0,2,5000),(0,3,1),(137,3,0),(137,3,1),(3000,9,0)],
 'mode1_reset_tail':[(0,0,1),(0,2,5000),(0,3,1),(1237,4,0),(1237,0,1),(1237,2,9000),(1237,3,1),(4000,9,0)],
}
def compile_legacy(out,backend,sanitize):
    rows=json.loads((out/'cmake-profile/compile_commands.json').read_text())
    row=next(r for r in rows if r['file']==str(ROOT/'sound/opngenc.c') and
      ('sdlnp2kai_sdl2.dir' if backend=='i286' else 'sdlnp21kai_sdl2.dir') in r['command'])
    base=[x for x in shlex.split(row['command']) if not x.startswith('-DNP2KAI_GIT_')]
    objects=[];commands=[]
    for source in (SRC/'beep_compat.c',ROOT/'sound/beepg.c'):
        obj=out/(source.stem+'.compat.o');args=base[:]
        args[args.index('-c')+1]=str(source);args[args.index('-o')+1]=str(obj)
        args+=['-UNDEBUG','-ffunction-sections','-fdata-sections']
        if sanitize:args+=['-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all']
        subprocess.run(args,check=True);objects.append(str(obj));commands.append(args)
    exe=out/'beep_compat';args=['cc','-Wl,--gc-sections',*objects,'-lm',*(['-fsanitize=address,undefined'] if sanitize else []),'-o',str(exe)]
    subprocess.run(args,check=True);commands.append(args)
    (out/'legacy-build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    return exe

def legacy_run(exe,out,tag,rate,q,adaptive,plan):
    pcm=out/(tag+'.s32le');state=out/(tag+'.state')
    subprocess.run([str(exe),str(rate),str(q),str(adaptive),str(plan),str(pcm),str(state)],check=True)
    data=pcm.read_bytes();return dict(path=str(pcm),pcm_sha256=bee.digest(data),pcm_bytes=len(data),
                                      sample_count=len(data)//8,state=state.read_text().strip())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--backend',choices=('i286','ia32'),default='i286');ap.add_argument('--sanitizer',action='store_true')
    a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    candidate,dll=bee.build(out,a.backend,a.sanitizer);legacy=compile_legacy(out,a.backend,a.sanitizer)
    rows=[];legacy_partition=[]
    for rate in (44100,48000):
      for name,actions in CASES.items():
        for adaptive in ((0,1) if name.startswith('mode0') and name!='mode0_word' else (0,)):
          rec=bee.plan_for(actions,rate,dll)
          plan=out/(f'{name}-{rate}-a{adaptive}.plan')
          plan.write_text(''.join(f'{f} {e.epoch} {e.seq} {e.kind} {e.a}\n' for e,f in rec))
          history_hash=bee.digest(fm.canonical([e.__dict__ for e,f in rec]))
          normalized=bee.run(candidate,out,f'{name}-{rate}-a{adaptive}-new',rate,1,0,adaptive,plan)
          old_large=None
          for label,q in (('large',0),('one',1),('max137',137),('max240',240),('event_boundary',512)):
            old=legacy_run(legacy,out,f'{name}-{rate}-a{adaptive}-old-{label}',rate,q,adaptive,plan)
            if old_large is None:old_large=old
            delta=bee.diff(normalized,old)
            old_delta=bee.diff(old_large,old)
            rows.append(dict(fixture=name,rate=rate,adaptive_offset=adaptive,old_partition=label,
                semantic_event_sha256=history_hash,frontier_sha256=bee.digest(fm.canonical([f for e,f in rec])),
                normalized_pcm_sha256=normalized['pcm_sha256'],old_pcm_sha256=old['pcm_sha256'],
                normalized_state=normalized['state'],old_state=old['state'],
                first_differing_frame=delta['first_frame'],changed_frames=delta['changed_frames'],
                old_partition_first_difference=old_delta['first_frame'],
                old_partition_changed_frames=old_delta['changed_frames']))
            if label!='large':legacy_partition.append(dict(fixture=name,rate=rate,adaptive_offset=adaptive,
                partition=label,**old_delta))
    assert any(r['changed_frames'] for r in rows if r['fixture'].startswith('mode0'))
    assert any(r['changed_frames'] for r in rows if r['fixture'].startswith('mode1'))
    report=dict(status='PASS_BOUNDED_BEEP_COMPAT_DELTA',backend=a.backend,
       old_mode0_timestamp_units='controlled sample-index proxy; actual PIT records CPU cycles',
       old_mode1_clock_units='controlled 16.16 sample-delay proxy; actual source records CPU deltas times samplebase',
       rows=rows,legacy_partition_differences=legacy_partition)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS BEEP compatibility',len(rows),'controlled comparisons, both modes/rates')
if __name__=='__main__':main()
