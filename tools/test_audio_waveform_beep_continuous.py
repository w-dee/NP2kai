#!/usr/bin/env python3
"""Owner-approved continuous BEEP and FM+BEEP common-grid qualification."""
from pathlib import Path
import argparse,ctypes,hashlib,json,shlex,shutil,struct,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_audio_waveform_policy as fm
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tests/host/audio_waveform_policy'
Q=[('large',0,0),('one',1,0),('max17',17,0),('max137',137,0),('max240',240,0),('max511',511,0),('event',0,1)]
def digest(x):return hashlib.sha256(x).hexdigest()
def build(out,backend,sanitize):
    cfg=out/'cmake-profile';cfg.mkdir(exist_ok=True)
    with (cfg/'configure.log').open('w') as log:
        subprocess.run(['cmake','-S',str(ROOT),'-B',str(cfg),'-DBUILD_I286='+('ON' if backend=='i286' else 'OFF'),
                        '-DBUILD_WX=OFF','-DBUILD_SDL=ON','-DUSE_SDL=2','-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],
                        check=True,stdout=log,stderr=subprocess.STDOUT)
    rows=json.loads((cfg/'compile_commands.json').read_text())
    row=next(r for r in rows if r['file']==str(ROOT/'sound/opngenc.c') and
             ('sdlnp2kai_sdl2.dir' if backend=='i286' else 'sdlnp21kai_sdl2.dir') in r['command'])
    base=[x for x in shlex.split(row['command']) if not x.startswith('-DNP2KAI_GIT_')]
    objs=[];commands=[]
    for source in [SRC/'beep_reference.c',ROOT/'sound/beepg.c']:
        obj=out/(source.stem+'.o');args=base[:];args[args.index('-c')+1]=str(source);args[args.index('-o')+1]=str(obj)
        args+=['-UNDEBUG','-ffunction-sections','-fdata-sections']
        if sanitize:args+=['-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all']
        subprocess.run(args,check=True);objs.append(str(obj));commands.append(args)
    exe=out/'beep_reference';args=['cc','-Wl,--gc-sections',*objs,'-lm',*(['-fsanitize=address,undefined'] if sanitize else []),'-o',str(exe)]
    subprocess.run(args,check=True);commands.append(args)
    lib=out/'libgrid.so';args=['cc','-std=c11','-O2','-shared','-fPIC',str(SRC/'grid.c'),'-o',str(lib)]
    subprocess.run(args,check=True);commands.append(args)
    (out/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    dll=ctypes.CDLL(str(lib));dll.audio_waveform_frontier.argtypes=[ctypes.POINTER(fm.Grid),ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint64)]
    dll.audio_waveform_frontier.restype=ctypes.c_int
    return exe,dll

def actions(name,adaptive):
    # Ordered independent BEEP history. Reset fixture has nonzero old tail at F=1237.
    start=[(0,0,0),(0,1,180),(137,1,24),(137,1,255),(501,1,0),(721,1,200)]
    if name=='mode0':return start+[(1900,1,70),(3000,9,0)]
    if name=='mode0_word':return [(0,0,0),(0,1,0x1234),(137,1,0xff00),(721,1,0x4020),(3000,9,0)]
    if name=='mode0_reset':return start+[(1237,4,0),(1237,0,0),(1237,1,255),(1800,1,0),(4000,9,0)]
    rate=[(0,0,1),(0,2,5000),(0,3,1),(137,3,0),(137,3,1),(601,2,1337),(721,3,0),(1500,3,1)]
    if name=='mode1':return rate+[(3000,9,0)]
    if name=='mode1_reset':return [x for x in rate if x[0]<1237]+[(1237,4,0),(1237,0,1),(1237,2,9000),(1237,3,1),(1800,3,0),(4000,9,0)]
    if name=='fm_silent':return [(0,0,1),(0,2,5000),(0,3,1),(11000,9,0)]
    if name=='mixed':return [(0,0,0),(0,1,255),(137,0,1),(137,2,5000),(137,3,1),
                             (721,3,0),(1000,0,0),(1000,1,180),(1237,4,0),
                             (1237,0,0),(1237,1,255),(1700,1,0),(4000,9,0)]
    raise ValueError(name)

def plan_for(actions,rate,dll):
    h=fm.History(rate,capacity=1000);record=[];epoch=1
    for seq,(frame,kind,value) in enumerate(actions):
        ns=fm.at_frontier(frame,rate);event=fm.Event(epoch,ns,ns,seq,kind,value)
        h.append(event);f=h.frontier(dll,ns);assert f==frame
        record.append((event,f))
        if kind==4:epoch+=1
    h.finalize(len(record),fm.at_frontier(actions[-1][0],rate))
    assert h.renderable(dll,0,actions[-1][0])
    return record

def run(exe,out,tag,rate,q,cuts,adaptive,plan):
    pcm=out/(tag+'.s32le');state=out/(tag+'.state')
    subprocess.run([str(exe),str(rate),str(q),str(cuts),str(adaptive),str(plan),str(pcm),str(state)],check=True)
    b=pcm.read_bytes();return {'pcm_sha256':digest(b),'pcm_bytes':len(b),'sample_count':len(b)//8,
                                'state':state.read_text().strip(),'path':str(pcm)}

def qualified_state(a):
    fields=a['state'].split()
    # Field 13 is diagnostic plan-record count; credit-only cuts may change it.
    return fields[:12]+fields[13:]

def diff(a,b):
    aa=Path(a['path']).read_bytes();bb=Path(b['path']).read_bytes();assert len(aa)==len(bb)
    changed=[i//8 for i in range(0,len(aa),8) if aa[i:i+8]!=bb[i:i+8]]
    return {'first_frame':changed[0] if changed else None,'changed_frames':len(changed),'state_equal':qualified_state(a)==qualified_state(b)}

def mix(a,b):
    av=struct.iter_unpack('<ii',Path(a['path']).read_bytes());bv=struct.iter_unpack('<ii',Path(b['path']).read_bytes())
    mixed=bytearray()
    for (al,ar),(bl,br) in zip(av,bv):mixed.extend(struct.pack('<ii',al+bl,ar+br))
    return digest(mixed),len(mixed)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--backend',choices=['i286','ia32'],default='i286');ap.add_argument('--sanitizer',action='store_true')
    a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    exe,dll=build(out,a.backend,a.sanitizer);rows=[];mixed=[];negative=[];credits=[];delays=[];services=[];ordering=[]
    for rate in (44100,48000):
        for name in ('mode0','mode0_word','mode0_reset','mode1','mode1_reset','mixed','fm_silent'):
            for adaptive in ((0,1) if name.startswith('mode0') and name!='mode0_word' else (0,)):
                ops=actions(name,adaptive);rec=plan_for(ops,rate,dll)
                plan=out/(f'{name}-{adaptive}-{rate}.plan')
                plan.write_text(''.join(f'{f} {e.epoch} {e.seq} {e.kind} {e.a}\n' for e,f in rec))
                expected_projection=[(e.seq,e.kind,e.a,f) for e,f in rec if f<ops[-1][0]]
                for batch in (1,7,len(rec)):
                    observed=fm.service_projection(rec,rate,dll,batch)
                    assert [(seq,kind,x,frontier) for seq,kind,x,y,z,frontier in observed]==expected_projection
                    services.append(dict(fixture=name,rate=rate,adaptive_offset=adaptive,batch=batch,projection_sha256=digest(fm.canonical(observed)),equal=True))
                reference=None
                for label,q,cuts in Q:
                    tag=f'{name}-{adaptive}-{rate}-{label}'
                    value=run(exe,out,tag,rate,q,cuts,adaptive,plan)
                    if reference is None:reference=value
                    equality=diff(reference,value)
                    assert equality=={'first_frame':None,'changed_frames':0,'state_equal':True},(tag,equality)
                    rows.append(dict(fixture=name,rate=rate,adaptive_offset=adaptive,partition=label,
                        epoch_count=1+sum(k==4 for f,k,v in ops),
                        machine_event_sha256=digest(fm.canonical([e.__dict__ for e,f in rec])),
                        application_frontier_sha256=digest(fm.canonical([f for e,f in rec])),
                        semantic_sequence_sha256=digest(fm.canonical([(e.epoch,e.seq,e.kind,e.a) for e,f in rec])),
                        **value,**equality))
                worker=out/(plan.name+'.worker');shutil.copyfile(plan,worker)
                delayed=run(exe,out,f'{name}-{adaptive}-{rate}-delayed',rate,137,0,adaptive,worker)
                assert diff(reference,delayed)=={'first_frame':None,'changed_frames':0,'state_equal':True}
                delays.append(dict(fixture=name,rate=rate,adaptive_offset=adaptive,pcm_sha256=delayed['pcm_sha256'],state=qualified_state(delayed),equal=True))
                if name in ('mode0_reset','mode1_reset','mixed'):
                    # Explicit credit and owner-service cuts never change the committed plan.
                    for capacity,blocks,returned,pace in ((16,0,3,1),(137,1,7,5),(240,2,11,3),(1024,4,2,9)):
                        cuts,waits,ticks=fm.credit_cuts(ops[-1][0],capacity,blocks,returned,pace)
                        extra=[];nextseq=0
                        for e,f in rec:extra.append((f,e.kind,e.a,e.epoch))
                        for f in cuts:
                            if f<ops[-1][0]:extra.append((f,8,0,1+sum(k==4 and at<=f for at,k,v in ops)))
                        extra.sort(key=lambda x:x[0]);epoch=1;lines=[]
                        for f,k,v,ep in extra:
                            if k==4:ep=epoch;epoch+=1
                            elif k==8:ep=epoch
                            else:ep=epoch
                            lines.append(f'{f} {ep} {nextseq} {k} {v}\n');nextseq+=1
                        # Same-frontier cuts are transport-only; keep semantic order by placing after operations.
                        credit=out/(f'{name}-{adaptive}-{rate}-credit-{capacity}.plan');credit.write_text(''.join(lines))
                        v=run(exe,out,f'{name}-{adaptive}-{rate}-credit-{capacity}',rate,0,1,adaptive,credit)
                        assert diff(reference,v)=={'first_frame':None,'changed_frames':0,'state_equal':True}
                        credits.append(dict(fixture=name,rate=rate,adaptive_offset=adaptive,capacity=capacity,initial_blocks=blocks,return_after=returned,consumer_pace=pace,wait_ticks=waits,total_host_ticks=ticks,pcm_sha256=v['pcm_sha256'],state=qualified_state(v),equal=True))
                if name=='mixed':
                    # FM reset_tail and BEEP mixed histories both close at global 1237 and end at 4000.
                    fmout=out/(f'fm-{rate}');fmout.mkdir(exist_ok=True)
                    fmexe,_=fm.build(fmout,a.sanitizer,a.backend)
                    _,frecord=fm.history_from_actions(fm.fixture('reset_tail',rate),rate,dll)
                    fplan=fmout/'reset-tail.plan';fplan.write_text(''.join(f'{f} {e.kind} {e.a} {e.b} {e.c}\n' for e,f in frecord))
                    fv=fm.run(fmexe,fmout,'reset-tail',rate,1,0,0,0,0,fplan)
                    fvalue={'path':fv['pcm_path'],'state':fv['renderer_fingerprint']}
                    assert fvalue['path'] and fv['frames']==reference['sample_count']
                    old_fm=Path(fv['pcm_path']).read_bytes()[1236*8:1237*8]
                    old_beep=Path(reference['path']).read_bytes()[1236*8:1237*8]
                    assert old_fm!=bytes(8) and old_beep!=bytes(8),(rate,old_fm,old_beep)
                    mh,mb=mix(fvalue,reference)
                    assert mix(reference,fvalue)==(mh,mb)
                    assert mix(fvalue,delayed)==(mh,mb)
                    fworker=fmout/'reset-tail.worker.plan';shutil.copyfile(fplan,fworker)
                    fd=fm.run(fmexe,fmout,'reset-tail-delayed',rate,1,137,0,0,12345,fworker)
                    assert mix({'path':fd['pcm_path']},delayed)==(mh,mb)
                    credit_cuts,_,_=fm.credit_cuts(4000,137,1,7,5)
                    credit_rows=fm.transport_plan(frecord,credit_cuts)
                    fcplan=fmout/'reset-tail.credit.plan'
                    fcplan.write_text(''.join(f'{f} {k} {x} {y} {z}\n' for f,k,x,y,z in credit_rows))
                    fc=fm.run(fmexe,fmout,'reset-tail-credit-plan',rate,1,0,1,0,5,fcplan)
                    bc={'path':str(out/(f'mixed-0-{rate}-credit-137.s32le'))}
                    assert mix({'path':fc['pcm_path']},bc)==(mh,mb)
                    for flabel,bq in (('one',1),('large',0),('credit',137)):
                        fr=fm.run(fmexe,fmout,'reset-tail-'+flabel,rate,1,bq,0,0,0,fplan)
                        br=run(exe,out,f'mixed-{rate}-{flabel}-source',rate,bq,0,0,plan)
                        h,n=mix({'path':fr['pcm_path']},br)
                        assert (h,n)==(mh,mb) and mix(br,{'path':fr['pcm_path']})==(mh,mb)
                    mixed.append(dict(rate=rate,reset_frontier=1237,mix_frames=reference['sample_count'],
                                      mix_bytes=mb,mix_sha256=mh,fm_sha256=fv['pcm_sha256'],
                                      beep_sha256=reference['pcm_sha256'],source_placement_equal=True,
                                      old_tail_nonzero=True))
                if name=='fm_silent':
                    fmout=out/(f'fm-silent-{rate}');fmout.mkdir(exist_ok=True)
                    fmexe,_=fm.build(fmout,a.sanitizer,a.backend)
                    fplan=fmout/'silent.plan';fplan.write_text('11000 9 0 0 0\n')
                    fv=fm.run(fmexe,fmout,'silent',rate,1,0,0,0,0,fplan)
                    assert fv['frames']==reference['sample_count']
                    assert Path(fv['pcm_path']).read_bytes()==bytes(fv['pcm_bytes'])
                    mh,mb=mix({'path':fv['pcm_path']},reference)
                    assert (mh,mb)==(reference['pcm_sha256'],reference['pcm_bytes'])
                    mixed.append(dict(rate=rate,case='FM_silent_BEEP_active',mix_frames=reference['sample_count'],
                                      mix_bytes=mb,mix_sha256=mh,source_placement_equal=True))
        for order_name,base,one,two in (
            ('mode0_data',[(0,0,0),(0,1,180)],(137,1,24),(137,1,255)),
            ('mode1_edges',[(0,0,1),(0,2,5000),(0,3,1)],(137,3,0),(137,3,1))):
            variants=[]
            for label,pair in (('ordered',(one,two)),('reversed',(two,one))):
                ops=base+list(pair)+[(3000,9,0)]
                rec=plan_for(ops,rate,dll)
                op=out/(f'order-{order_name}-{rate}-{label}.plan')
                op.write_text(''.join(f'{f} {e.epoch} {e.seq} {e.kind} {e.a}\n' for e,f in rec))
                variants.append(run(exe,out,f'order-{order_name}-{rate}-{label}',rate,1,0,0,op))
            changed=diff(*variants)
            assert changed['changed_frames']>0 and not changed['state_equal']
            ordering.append(dict(rate=rate,case=order_name,**changed))
        invalid=out/(f'invalid-{rate}.plan');invalid.write_text('0 1 0 0 0\n10 1 2 9 0\n')
        p=out/(f'invalid-{rate}.pcm');s=out/(f'invalid-{rate}.state')
        proc=subprocess.run([str(exe),str(rate),'0','0','0',str(invalid),str(p),str(s)],capture_output=True,text=True)
        assert proc.returncode==2 and p.stat().st_size==0 and s.stat().st_size==0
        negative.append(dict(rate=rate,rejected=True,producer_bytes_published=0))
    report=dict(status='PASS_BOUNDED_BEEP_CONTINUOUS_AND_MIX',profile='MACHINE_TIME_CONTINUOUS_WAVEFORM_PROFILE',
        backend=a.backend,rates=[44100,48000],rows=rows,mixed=mixed,transport_credit=credits,delayed=delays,owner_service=services,ordering_controls=ordering,negative=negative)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS BEEP',len(rows),'partition cases, both modes/rates, mixed source reset and delayed equality')
if __name__=='__main__':main()
