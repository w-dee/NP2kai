#!/usr/bin/env python3
"""Executable machine-time/continuous native FM reference profile.

The input fixtures contain ordered semantic operations with absolute integer-ns
acceptance/application times. Native FM code, not a copied FM model, renders PCM.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
import random
import shlex
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tests/host/audio_waveform_policy'
PROFILE='MACHINE_TIME_CONTINUOUS_WAVEFORM_PROFILE'
LEGACY='LEGACY_NATIVE_W0_PROFILE'
D=1_000_000_000
Q=[('original',0,1),('one',1,0),('max17',17,0),('max137',137,0),
   ('max240',240,0),('max511',511,0),('event_boundary',0,0),('large',0,0)]

class Grid(ctypes.Structure):
    _fields_=[('origin_ns',ctypes.c_uint64),('first_sample',ctypes.c_uint64),('rate',ctypes.c_uint32)]

def digest(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def ceil_div(a,b):return (a+b-1)//b

def build(out,sanitize,backend):
    cfg=out/'cmake-profile';cfg.mkdir(exist_ok=True)
    with (cfg/'configure.log').open('w') as log:
        subprocess.run(['cmake','-S',str(ROOT),'-B',str(cfg),'-DBUILD_I286='+('ON' if backend=='i286' else 'OFF'),
                        '-DBUILD_WX=OFF','-DBUILD_SDL=ON','-DUSE_SDL=2',
                        '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],check=True,stdout=log,stderr=subprocess.STDOUT)
    rows=json.loads((cfg/'compile_commands.json').read_text())
    row=next(r for r in rows if r['file']==str(ROOT/'sound/opngenc.c') and ('sdlnp2kai_sdl2.dir' if backend=='i286' else 'sdlnp21kai_sdl2.dir') in r['command'])
    base=[x for x in shlex.split(row['command']) if not x.startswith('-DNP2KAI_GIT_')]
    objects=[];commands=[]
    for source in [SRC/'fm_reference.c',ROOT/'sound/opngenc.c',ROOT/'sound/opngeng.c']:
        object_path=out/(source.stem+'.o');args=base[:]
        args[args.index('-c')+1]=str(source);args[args.index('-o')+1]=str(object_path)
        args+=['-UNDEBUG','-ffunction-sections','-fdata-sections']
        if sanitize:args+=['-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all']
        subprocess.run(args,cwd=ROOT,check=True);objects.append(str(object_path));commands.append(args)
    exe=out/'fm_reference'
    args=['cc','-Wl,--gc-sections',*objects,'-lm',*(['-fsanitize=address,undefined'] if sanitize else []),'-o',str(exe)]
    subprocess.run(args,check=True);commands.append(args)
    lib=out/'libaudio_waveform_grid.so'
    args=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(SRC/'grid.c'),'-o',str(lib)]
    subprocess.run(args,check=True);commands.append(args)
    gridtest=out/'test_grid'
    args=['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
          '-fno-sanitize-recover=all',str(SRC/'grid.c'),str(SRC/'test_grid.c'),'-o',str(gridtest)]
    subprocess.run(args,check=True);commands.append(args)
    subprocess.run([str(gridtest)],check=True)
    (out/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    dll=ctypes.CDLL(str(lib));dll.audio_waveform_frontier.argtypes=[ctypes.POINTER(Grid),ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint64)]
    dll.audio_waveform_frontier.restype=ctypes.c_int
    return exe,dll

@dataclass(frozen=True)
class Event:
    epoch:int
    accept_ns:int
    apply_ns:int
    seq:int
    kind:int
    a:int=0
    b:int=0
    c:int=0

class History:
    def __init__(self,rate,origin_ns=1_000_000_000,first_sample=0,capacity=1000):
        self.grid=Grid(origin_ns,first_sample,rate)
        self.events=[];self.capacity=capacity;self.finalized=0;self.watermark_ns=origin_ns
        self.expected_epoch=1
    def frontier(self,dll,at):
        answer=ctypes.c_uint64()
        if dll.audio_waveform_frontier(ctypes.byref(self.grid),at,ctypes.byref(answer)):
            raise ValueError('grid invalid or overflow')
        return answer.value
    def append(self,event):
        if len(self.events)>=self.capacity:raise ValueError('history capacity')
        if event.seq!=len(self.events) or event.epoch!=self.expected_epoch or event.accept_ns>event.apply_ns:
            raise ValueError('history sequence/epoch/causality')
        if event.accept_ns<self.watermark_ns:raise ValueError('event behind finalized watermark')
        if self.events and (event.apply_ns,event.seq)<(self.events[-1].apply_ns,self.events[-1].seq):
            raise ValueError('application order')
        self.events.append(event)
        if event.kind==4:self.expected_epoch+=1
    def finalize(self,count,watermark):
        if count<self.finalized or count>len(self.events) or watermark<self.watermark_ns:
            raise ValueError('finalization rollback')
        if any(e.accept_ns<watermark for e in self.events[count:]):
            raise ValueError('premature watermark beyond uncommitted event')
        self.finalized=count;self.watermark_ns=watermark
    def renderable(self,dll,start,end):
        if end<start or self.frontier(dll,self.watermark_ns)<end:
            raise ValueError('future-event watermark')
        if any(self.frontier(dll,e.apply_ns)<end for e in self.events[self.finalized:]):
            raise ValueError('unfinalized semantic prefix')
        return [e for e in self.events[:self.finalized]
                if start<=self.frontier(dll,e.apply_ns)<end]

# Earliest integer ns that maps to the chosen sample frontier under ceil.
def at_frontier(frame,rate,origin=1_000_000_000):
    if not frame:return origin
    return origin+((frame-1)*D//rate)+1

def fixture(name,rate):
    """Return ordered (frame,kind,a,b,c), cut markers included."""
    a=[]
    def put(f,k,x=0,y=0,z=0):a.append((f,k,x,y,z))
    def voice(f,ch,alg=7,fb=7):put(f,5,ch,alg,fb)
    def key(f,ch,val):put(f,1,ch,val)
    def reg(f,base,address,value):put(f,0,base,address,value)
    if name.startswith('alg'):
        alg,fb=map(int,name.split('_')[1:]);voice(0,0,alg,fb);key(0,0,0xf0)
        put(239,8);key(350,0,0);put(450,8);key(2000,0,0xf0)
        reg(2200,0,0xa4,0x24);reg(2200,0,0xa0,0x39);key(3000,0,0)
        key(7000,0,0xf0);put(7300,8);end=9000
    elif name in ('active_large','active_split'):
        voice(0,2,7,7);key(0,2,0xf2)
        if name=='active_split':
            for f in range(137,3000,137):put(f,8)
        end=3000
    elif name in ('single_csm','repeated_csm','csm_key','same_frontier_csm'):
        voice(0,2,4,6);key(0,2,0xf2);put(300,2)
        if name=='repeated_csm':put(700,2)
        if name=='csm_key':key(300,2,2);key(300,2,0xf2)
        if name=='same_frontier_csm':put(300,2)
        end=2700
    elif name=='frequency':
        voice(0,0,7,7);key(0,0,0xf0)
        reg(137,0,0xa4,0x25);reg(137,0,0xa0,0x33)
        reg(800,0,0xa0,0x51);key(1500,0,0);end=3000
    elif name=='multi_stereo':
        for ch in range(6):voice(0,ch,ch%8,(ch+1)%8);put(0,6,ch,[0x40,0x80,0xc0][ch%3]);key(20*ch,ch,0xf0)
        for ch in range(6):key(950+19*ch,ch,0)
        for ch in range(6):key(4300+23*ch,ch,0xf0)
        end=6200
    elif name=='csm_extop':
        voice(0,2,4,6);key(0,2,0xf2);put(100,3,0xc0)
        for address,value in [(0xac,0x25),(0xa8,0x33),(0xad,0x20),(0xa9,0x71)]:reg(137,0,address,value)
        put(201,7);put(201,1,2,2);put(201,1,2,0xf2)
        put(201,2);put(300,3,0);reg(300,0,0xac,0x21);reg(300,0,0xa8,0x47)
        key(450,2,0);put(530,8);put(1500,2);end=2700
    elif name=='quiet_large':
        voice(0,2);key(0,2,0xf2);key(300,2,2);put(10000,2);end=11000
    elif name=='quiet_split':
        voice(0,2);key(0,2,0xf2);key(300,2,2)
        for f in range(301,10000,137):put(f,8)
        put(10000,2);end=11000
    elif name=='reset_tail':
        voice(0,0);key(0,0,0xf0);put(1000,8);put(1237,4)
        voice(1237,2,6,3);key(1237,2,0xf2);key(1700,2,2);put(1850,2);end=4000
    elif name=='owned_sequence':
        pos=0
        for i in range(24):
            voice(pos,2,i%8,i%8);key(pos,2,0xf2);pos+=211+i%5*37;put(pos,8)
            if i%4==0:put(pos,2)
            key(pos,2,2);pos+=503 if i%3 else 1600
        end=pos+250
    elif name.startswith('seed'):
        rng=random.Random(int(name[4:]));voice(0,2);key(0,2,0xf2);pos=0
        for i in range(80):
            pos+=rng.randint(3,371);ch=rng.randrange(6)
            typ=rng.randrange(8)
            if typ==0:voice(pos,ch,rng.randrange(8),rng.randrange(8))
            elif typ==1:key(pos,ch,0xf0)
            elif typ==2:key(pos,ch,0)
            elif typ==3:reg(pos,ch//3*3,0xa4+ch%3,rng.randrange(0x20,0x30))
            elif typ==4:reg(pos,ch//3*3,0xa0+ch%3,rng.randrange(256))
            elif typ==5:put(pos,2)
            elif typ==6:put(pos,3,rng.choice([0,0x40,0x80,0xc0]))
            else:put(pos,6,ch,rng.choice([0x40,0x80,0xc0]))
            if i%7==0:put(pos,8)
        end=pos+1400
    else:raise ValueError(name)
    put(end,9)
    return sorted(a,key=lambda action:action[0])

def history_from_actions(actions,rate,dll):
    hist=History(rate);records=[]
    epoch=1
    for seq,(frame,kind,a,b,c) in enumerate(actions):
        ns=at_frontier(frame,rate)
        e=Event(epoch,ns,ns,seq,kind,a,b,c)
        hist.append(e)
        actual=hist.frontier(dll,e.apply_ns)
        assert actual==frame,(rate,frame,actual)
        records.append((e,actual))
        if kind==4:epoch+=1
    hist.finalize(len(hist.events),at_frontier(actions[-1][0],rate))
    return hist,records


def service_projection(records,rate,dll,batch):
    """Owner service batches publish only a safe future-event lower bound."""
    h=History(rate,capacity=len(records)+1)
    for e,f in records:h.append(e)
    projection=[];start=0
    for count in range(batch,len(records)+batch,batch):
        count=min(count,len(records))
        next_time=records[count][0].apply_ns if count<len(records) else records[-1][0].apply_ns
        end=h.frontier(dll,next_time)
        h.finalize(count,next_time)
        projection += [(e.seq,e.kind,e.a,e.b,e.c,h.frontier(dll,e.apply_ns))
                       for e in h.renderable(dll,start,end)]
        start=end
    return projection

def credit_cuts(end,capacity,initial_blocks,return_after,consumer_pace):
    """Bounded controlled credit model. Host ticks delay admission, not time."""
    if capacity<=0 or return_after<=0 or consumer_pace<=0:raise ValueError('resource capacity')
    tick=0;free=initial_blocks;due=[];pos=0;cuts=[];waits=0
    if not free:due.append(return_after)
    while pos<end:
        matured=[t for t in due if t<=tick];free+=len(matured);due=[t for t in due if t>tick]
        if free==0:
            waits+=1
            if not due or waits>1_000_000:raise ValueError('credit exhausted')
            tick=min(due);continue
        n=min(capacity,end-pos);pos+=n;free-=1;cuts.append(pos)
        due.append(tick+return_after+consumer_pace);tick+=consumer_pace
    return cuts,waits,tick

def transport_plan(records,cuts):
    rows=[(f,e.kind,e.a,e.b,e.c) for e,f in records]
    last=max(f for f,k,a,b,c in rows if k==9)
    rows += [(f,8,0,0,0) for f in cuts if f<last]
    # An inserted credit cut at the same frontier follows original semantics.
    return sorted(rows,key=lambda row:row[0])

def run(exe,out,tag,rate,profile,q,cuts,vr,cpu,plan):
    pcm=out/(tag+'.s32le');state=out/(tag+'.state')
    subprocess.run([str(exe),str(rate),str(profile),str(q),str(cuts),str(vr),str(cpu),str(plan),str(pcm),str(state)],check=True)
    fingerprint,frames,actions=state.read_text().split()
    data=pcm.read_bytes()
    assert len(data)==int(frames)*8
    return dict(tag=tag,rate=rate,profile=PROFILE if profile else LEGACY,
                partition=q,cuts=cuts,vr=vr,cpu=cpu,frames=int(frames),pcm_bytes=len(data),
                pcm_sha256=digest(data),renderer_fingerprint=fingerprint,
                actions=int(actions),pcm_path=str(pcm))

def first_diff(a,b):
    aa=Path(a['pcm_path']).read_bytes();bb=Path(b['pcm_path']).read_bytes()
    assert len(aa)==len(bb)
    dif=[i//8 for i in range(0,len(aa),8) if aa[i:i+8]!=bb[i:i+8]]
    return dict(first_frame=dif[0] if dif else None,changed_frames=len(dif),
                percentage=100*len(dif)/(len(aa)//8) if aa else 0,
                final_state_equal=a['renderer_fingerprint']==b['renderer_fingerprint'])

def negative_controls(dll):
    h=History(44100,capacity=2)
    t=at_frontier(3,44100)
    for i in range(2):h.append(Event(1,t,t,i,0,0,0xa0,i))
    try:h.append(Event(1,t,t,2,0))
    except ValueError:pass
    else:raise AssertionError('capacity accepted')
    h.finalize(1,t)
    for start,end in [(0,4)]:
        try:h.renderable(dll,start,end)
        except ValueError:pass
        else:raise AssertionError('premature watermark accepted')
    assert h.renderable(dll,0,3)==[]
    h.finalize(2,at_frontier(4,44100))
    assert len(h.renderable(dll,0,4))==2
    h2=History(44100);h2.append(Event(1,t,t,0,0))
    try:h2.finalize(0,at_frontier(4,44100))
    except ValueError:pass
    else:raise AssertionError('unfinalized event hidden by watermark')
    # Frontier E is legal for a later same-time sequence after [S,E) closes.
    h3=History(44100);h3.finalize(0,t);assert h3.renderable(dll,0,3)==[]
    h3.append(Event(1,t,t,0,0));assert h3.renderable(dll,0,3)==[]
    try:h3.append(Event(1,t-1,t-1,1,0))
    except ValueError:pass
    else:raise AssertionError('retroactive event accepted')
    try:credit_cuts(10,0,1,1,1)
    except ValueError:pass
    else:raise AssertionError('zero capacity accepted')
    return ['capacity','future_watermark','unfinalized_prefix','later_same_frontier','retroactive_event','zero_transport_capacity']


def order_controls(exe,out,rate,dll):
    """Corrupt same-frontier semantic order; never treat PCM aliasing as identity."""
    base_prefix=[(0,5,2,7,7),(0,1,2,0xf2,0)]
    cases={
      'csm_key': ([(300,2,0,0,0),(300,1,2,0,0)],
                  [(300,1,2,0,0),(300,2,0,0,0)]),
      'frequency_high_low': ([(300,0,0,0xa6,0x25),(300,0,0,0xa2,0x33)],
                             [(300,0,0,0xa2,0x33),(300,0,0,0xa6,0x25)]),
      'extop_special_frequency': ([(137,3,0xc0,0,0),(137,0,0,0xac,0x25),(137,0,0,0xa8,0x33)],
                                  [(137,0,0,0xac,0x25),(137,0,0,0xa8,0x33),(137,3,0xc0,0,0)]),
      'two_csm_drop_one': ([(300,2,0,0,0),(300,2,0,0,0)],[(300,2,0,0,0)])
    }
    results=[]
    for name,(normal,altered) in cases.items():
        pair=[]
        for label,ops in [('ordered',normal),('mutated',altered)]:
            actions=base_prefix+ops+[(1300,9,0,0,0)]
            h,records=history_from_actions(actions,rate,dll)
            path=out/(f'order-{name}-{rate}-{label}.plan')
            path.write_text(''.join(f'{f} {e.kind} {e.a} {e.b} {e.c}\n' for e,f in records))
            runrec=run(exe,out,f'order-{name}-{rate}-{label}',rate,1,137,0,0,0,path)
            pair.append((runrec,digest(canonical([e.__dict__ for e,f in records]))))
        diff=first_diff(pair[0][0],pair[1][0]);assert pair[0][1]!=pair[1][1]
        if name!='two_csm_drop_one':assert diff['first_frame'] is not None,(name,rate)
        results.append(dict(name=name,rate=rate,history_equal=False,**diff))
    return results


def malformed_plan_controls(exe,out,rate,dll):
    actions=fixture('csm_extop',rate);_,records=history_from_actions(actions,rate,dll)
    rows=[f'{f} {e.kind} {e.a} {e.b} {e.c}' for e,f in records]
    marker=next(i for i,row in enumerate(rows) if row.split()[1]=='7')
    variants={
      'missing_csm_on':rows[:marker+2]+rows[marker+3:],
      'reversed_csm_pair':rows[:marker+1]+[rows[marker+2],rows[marker+1]]+rows[marker+3:],
      'trailing_after_end':rows+['2700 2 0 0 0'],
      'backwards_frontier':rows[:marker]+['1 7 0 0 0']+rows[marker+1:],
      'frame_capacity':rows[:-1]+['200001 9 0 0 0'],
    }
    checked=[]
    for name,variant in variants.items():
        path=out/(f'malformed-{name}.plan');path.write_text('\n'.join(variant)+'\n')
        run=subprocess.run([str(exe),str(rate),'1','0','1','0','0',str(path),
           str(out/(f'malformed-{name}.pcm')),str(out/(f'malformed-{name}.state'))],
           capture_output=True,text=True)
        assert run.returncode==2 and 'AUDIO WAVEFORM INVALID:' in run.stderr,(name,run.returncode,run.stderr)
        assert (out/(f'malformed-{name}.pcm')).stat().st_size==0
        assert (out/(f'malformed-{name}.state')).stat().st_size==0
        checked.append(dict(control=name,rejected=True,producer_bytes_published=0,reason=run.stderr.strip()))
    return checked

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--sanitizer',action='store_true');ap.add_argument('--quick',action='store_true')
    ap.add_argument('--backend',choices=['i286','ia32'],default='i286')
    args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    exe,dll=build(out,args.sanitizer,args.backend)
    negatives=negative_controls(dll)
    names=['quiet_large','quiet_split','active_large','active_split','single_csm',
           'repeated_csm','csm_key','frequency','same_frontier_csm',
           'multi_stereo','csm_extop','reset_tail','owned_sequence']
    if args.quick:names+=['alg_0_0','alg_7_7','seed1234']
    else:names += [f'alg_{alg}_{fb}' for alg in range(8) for fb in [0,1,4,7]]
    if not args.quick:names += [f'seed{seed}' for seed in [1,19,1234,0x2608,0x9801]]
    summary=[];comparisons=[];transport=[];service=[];ordering=[];cpu_variants=[]
    negatives+=malformed_plan_controls(exe,out,44100,dll)
    for rate in [44100,48000]:
        ordering+=order_controls(exe,out,rate,dll)
        for name in names:
            actions=fixture(name,rate);hist,records=history_from_actions(actions,rate,dll)
            semantic=[(e.epoch,e.apply_ns,e.seq,e.kind,e.a,e.b,e.c,f) for e,f in records if e.kind!=8]
            full_projection=[(e.seq,e.kind,e.a,e.b,e.c,f) for e,f in records if f<actions[-1][0]]
            for batch in [1,7,len(records)]:
                observed=service_projection(records,rate,dll,batch)
                assert observed==full_projection,(name,rate,batch,'owner service')
                service.append(dict(fixture=name,rate=rate,batch=batch,projection_sha256=digest(canonical(observed))))
            plan=out/(f'{name}-{rate}.plan')
            plan.write_text(''.join(f'{f} {e.kind} {e.a} {e.b} {e.c}\n' for e,f in records))
            reference=None;legacy=None
            for label,q,cuts in Q:
                tag=f'{name}-{rate}-{label}'
                v=run(exe,out,tag,rate,1,q,cuts,0,0,plan)
                v.update(fixture=name,epoch=1,machine_event_sha256=digest(canonical([e.__dict__ for e,f in records])),
                    application_frontier_sha256=digest(canonical([f for e,f in records])),
                    semantic_sequence_sha256=digest(canonical(semantic)),
                    generation_partition=label)
                if reference is None:reference=v
                comparison=first_diff(reference,v);assert comparison['first_frame'] is None and comparison['final_state_equal'],(name,rate,label,comparison)
                comparisons.append(dict(fixture=name,rate=rate,partition=label,**comparison))
                if label=='original':legacy=run(exe,out,tag+'-legacy',rate,0,q,cuts,0,0,plan)
                summary.append(v)
            comparison=first_diff(legacy,reference)
            comparisons.append(dict(fixture=name,rate=rate,partition='legacy-original-to-continuous-original',**comparison))
            # Same authorized plan copied into worker storage, with CPU coordinate variation.
            worker_plan=out/(f'{name}-{rate}.worker.plan');shutil.copyfile(plan,worker_plan)
            delayed=run(exe,out,f'{name}-{rate}-delayed',rate,1,137,0,0,12345,worker_plan)
            assert first_diff(reference,delayed)['first_frame'] is None
            assert reference['renderer_fingerprint']==delayed['renderer_fingerprint']
            if name in ('quiet_large','multi_stereo','csm_extop','reset_tail'):
                for cpu_case in [1,4,20,12345]:
                    cpu_run=run(exe,out,f'{name}-{rate}-cpu{cpu_case}',rate,1,0,1,0,cpu_case,plan)
                    eq=first_diff(reference,cpu_run)
                    assert eq['first_frame'] is None and eq['final_state_equal']
                    cpu_variants.append(dict(fixture=name,rate=rate,cpu_multiple=cpu_case,
                                             pcm_sha256=cpu_run['pcm_sha256'],state=cpu_run['renderer_fingerprint'],equal=True))
            if name=='reset_tail':
                assert [e.epoch for e,f in records if e.kind==4]==[1]
                reset_index=next(i for i,(e,f) in enumerate(records) if e.kind==4)
                assert records[reset_index+1][0].epoch==2
                assert records[reset_index+1][1]==records[reset_index][1]
            if name in ('quiet_large','multi_stereo','csm_extop','reset_tail'):
                for capacity,blocks,returned,pace in [(16,0,3,1),(137,1,7,5),(240,2,11,3),(1024,4,2,9)]:
                    cuts,waits,ticks=credit_cuts(actions[-1][0],capacity,blocks,returned,pace)
                    rows=transport_plan(records,cuts)
                    variant=out/(f'{name}-{rate}-credit-{capacity}.plan')
                    variant.write_text(''.join(f'{f} {k} {a} {b} {c}\n' for f,k,a,b,c in rows))
                    v=run(exe,out,f'{name}-{rate}-credit-{capacity}',rate,1,0,1,0,pace,variant)
                    eq=first_diff(reference,v)
                    assert eq['first_frame'] is None and eq['final_state_equal']
                    transport.append(dict(fixture=name,rate=rate,capacity=capacity,initial_blocks=blocks,
                                          return_after=returned,consumer_pace=pace,wait_ticks=waits,
                                          total_host_ticks=ticks,calls_from_credit=len(cuts),
                                          pcm_sha256=v['pcm_sha256'],state=v['renderer_fingerprint'],equal=True))
    (out/'report.json').write_text(json.dumps(dict(status='PASS_BOUNDED_FM_REFERENCE',profile=PROFILE,
        cpu_backend=args.backend,baseline=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        rates=[44100,48000],fixtures=names,partitions=[x[0] for x in Q],
        positive=summary,comparisons=comparisons,transport_credit=transport,owner_service=service,cpu_variants=cpu_variants,ordering_controls=ordering,negative=negatives),indent=2)+'\n')
    print('PASS FM',len(names),'fixtures x 2 rates x',len(Q),'partitions; exact PCM/state, delayed equality')
if __name__=='__main__':main()
