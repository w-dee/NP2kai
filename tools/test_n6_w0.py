#!/usr/bin/env python3
"""Build and qualify private native OPNA ordered-history recorder/replay."""
from pathlib import Path
import argparse,json,subprocess,shlex,hashlib,struct
ROOT=Path(__file__).resolve().parents[1]
CASES={1:'baseline',2:'single_csm_timer',3:'repeated_csm',4:'same_frontier_csm_key',5:'csm_frequency',6:'reset_epoch',7:'source_sync',8:'quiet_large_call',9:'quiet_split_calls',10:'active_partition',11:'active_split'}
HEADER=struct.Struct('<8s13I2Q');RECORD=struct.Struct('<9Q11I')
FIELDS=['seq','parent','time_ns','service_ns','frame','call_id','cpu','last_before','last_after','kind','epoch','origin','reg','value','sub','requested','actual','remain_before','remain_after','aux']
def hash_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def compile_test(out,sanitizer=False):
    profile=out/'cmake-profile'
    profile.mkdir(exist_ok=True)
    with (profile/'configure.log').open('w') as log:
        subprocess.run(['cmake','-S',str(ROOT),'-B',str(profile),'-DBUILD_I286=ON',
                        '-DBUILD_WX=OFF','-DBUILD_SDL=ON','-DUSE_SDL=2',
                        '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON'],check=True,stdout=log,stderr=subprocess.STDOUT)
    commands=json.loads((profile/'compile_commands.json').read_text())
    row=next(x for x in commands if x['file']==str(ROOT/'sound/opngenc.c') and 'sdlnp2kai_sdl2.dir' in x['command'])
    objs=[]
    for source in [ROOT/'tests/host/n6_w0/native_history.c',ROOT/'sound/opngenc.c',ROOT/'sound/opngeng.c']:
        argv=shlex.split(row['command']);obj=out/(source.stem+'.o')
        argv[argv.index('-c')+1]=str(source);argv[argv.index('-o')+1]=str(obj)
        argv+=['-UNDEBUG','-ffunction-sections','-fdata-sections']
        if sanitizer:argv+=['-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all']
        subprocess.run(argv,cwd=ROOT,check=True,stdout=subprocess.DEVNULL);objs.append(str(obj))
    binary=out/'native_history';subprocess.run(['cc','-Wl,--gc-sections',*objs,'-lm',*(['-fsanitize=address,undefined'] if sanitizer else []),'-o',str(binary)],check=True);return binary

def load(p):
    data=p.read_bytes();assert len(data)>=HEADER.size
    header=HEADER.unpack_from(data);assert header[0]==b'N6W0A01\0' and header[1]==1
    n=header[-1];assert len(data)==HEADER.size+n*RECORD.size
    return header,[dict(zip(FIELDS,RECORD.unpack_from(data,HEADER.size+i*RECORD.size))) for i in range(n)]
def save(p,head,rows):
    head=(*head[:-1],len(rows))
    p.write_bytes(HEADER.pack(*head)+b''.join(RECORD.pack(*(r[k] for k in FIELDS)) for r in rows))
def fail_if_equal(a,b):
    return a.read_bytes()!=b.read_bytes()

def call_spans(rows,pcm):
    raw=pcm.read_bytes();total=0;spans=[]
    for r in rows:
        if r['kind']==15:
            size=r['actual']*8;segment=raw[total*8:total*8+size]
            assert len(segment)==size
            spans.append(dict(epoch=r['epoch'],generation_call_id=r['call_id'],
                sample_frontier=r['frame'],total_start_frame=total,frames=r['actual'],
                origin=r['origin'],pcm_bytes=size,pcm_sha256=hashlib.sha256(segment).hexdigest()))
            total+=r['actual']
    assert len(raw)==total*8
    return spans

from copy import deepcopy

def groups(rows):
    result=[]; current=[]
    for row in rows:
        current.append(deepcopy(row))
        if row['kind']==17:
            result.append(current);current=[]
    assert not current
    return result

def renumber(rows):
    old_to_new={r['seq']:i for i,r in enumerate(rows)}
    for i,r in enumerate(rows):
        if r['kind']==17:
            r['parent']=i-1;r['aux']=(i-1)&0xffffffff
        elif r['parent']:
            assert r['parent'] in old_to_new
            r['parent']=old_to_new[r['parent']]
        r['seq']=i
    return rows

def change_groups(rows,action,kinds):
    parts=groups(rows)
    indexes=[]
    for i,g in enumerate(parts):
        if any(r['kind'] in kinds for r in g):indexes.append(i)
    assert indexes
    if action=='remove':del parts[indexes[0]]
    elif action=='swap':assert len(indexes)>=2;parts[indexes[0]],parts[indexes[1]]=parts[indexes[1]],parts[indexes[0]]
    return renumber([r for g in parts for r in g])

def pcm_first_diff(a,b):
    a=a.read_bytes();b=b.read_bytes()
    for i,(x,y) in enumerate(zip(a,b)):
        if x!=y:return i//8
    return min(len(a),len(b))//8 if len(a)!=len(b) else None

def first_record_diff(a,b):
    for left,right in zip(a,b):
        if left!=right:return dict(sequence=left['seq'],generation_call_id=left['call_id'],sample_frontier=left['frame'])
    if len(a)!=len(b):
        r=a[min(len(a),len(b))] if len(a)>len(b) else b[min(len(a),len(b))]
        return dict(sequence=r['seq'],generation_call_id=r['call_id'],sample_frontier=r['frame'])
    return None

def mutation_suite(binary,out,plans):
    matrix=[]
    def check(name,case,edit,expect,scale=None):
        d=out/'negative'/name;d.mkdir(parents=True,exist_ok=True)
        head,original=load(plans[case][0]);rows=deepcopy(original)
        if edit:rows=edit(rows)
        plan=d/'mutated.bin';save(plan,head,rows)
        pcm=d/'replay.s32le'
        with (d/'replay.log').open('w') as log:
            proc=subprocess.run([binary,'replay','delayed',str(plan),str(pcm)],stdout=log,stderr=subprocess.STDOUT)
        rejected=proc.returncode!=0
        if rejected:assert 'N6-W0 INVALID:' in (d/'replay.log').read_text(),name
        diff=first_record_diff(original,rows)
        first_pcm=None if rejected else pcm_first_diff(plans[case][1],pcm)
        if expect=='reject':assert rejected,(name,'expected rejection')
        elif expect=='pcm':assert not rejected and first_pcm is not None,(name,'expected PCM difference')
        elif expect=='history':assert not rejected and diff is not None,(name,'expected history difference')
        else:raise ValueError(expect)
        measured=None
        if scale is not None:
            baseline_span=original[-1]['time_ns']-original[0]['time_ns']
            mutated_span=rows[-1]['time_ns']-rows[0]['time_ns']
            assert baseline_span>0
            measured=mutated_span/baseline_span
            assert abs(measured-scale)<=2/baseline_span,(name,measured,scale)
        matrix.append(dict(control=name,case=CASES[case],detected=True,mechanism='schema/plan rejection' if rejected else 'exact PCM divergence' if first_pcm is not None else 'exact history/timing divergence',earliest=diff,pcm_frame=first_pcm,measured_time_scale=measured))
    check('drop_csm',2,lambda r:change_groups(r,'remove',{10}),'pcm')
    check('collapse_csm',3,lambda r:change_groups(r,'remove',{10}),'pcm')
    check('reverse_csm_guest_key',4,lambda r:change_groups(r,'swap',{10,4}),'pcm')
    def freq_swap(rows):
        parts=groups(rows);a=next(i for i,g in enumerate(parts) if any(x['kind']==3 and x['reg']==0xa6 for x in g));b=next(i for i,g in enumerate(parts) if any(x['kind']==3 and x['reg']==0xa2 for x in g));parts[a],parts[b]=parts[b],parts[a];return renumber([x for g in parts for x in g])
    check('reverse_frequency_writes',5,freq_swap,'pcm')
    def shift(delta):
        def edit(rows):
            r=next(x for x in rows if x['kind']==10 and x['frame']>0)
            r['frame']+=delta;return rows
        return edit
    check('frontier_plus_one',4,shift(1),'reject')
    check('frontier_minus_one',4,shift(-1),'reject')
    def epoch(rows):
        reset=[r for r in rows if r['kind']==1][1]
        reset['epoch']+=1;return rows
    check('cross_epoch',6,epoch,'reject')
    def premature(rows):
        parts=groups(rows);g=next(g for g in parts if any(x['kind']==10 for x in g));final=g.pop();at=next(i for i,x in enumerate(g) if x['kind']==10);g.insert(at+1,final);return renumber([x for g in parts for x in g])
    check('premature_finalization',4,premature,'reject')
    def retrospective(rows):
        r=next(x for x in rows if x['kind']==4);r['time_ns']=0;return rows
    check('retrospective_time',4,retrospective,'reject')
    for numer,denom in [(3,2),(17,10)]:
        def stretch(rows,n=numer,d=denom):
            for r in rows:r['time_ns']=r['time_ns']*n//d;r['service_ns']=r['service_ns']*n//d
            return rows
        check(f'time_scale_{numer}_{denom}',3,stretch,'history',numer/denom)
    for name,case in [('schema_version',1),('record_capacity',1)]:
        d=out/'negative'/name;d.mkdir(parents=True,exist_ok=True)
        data=bytearray(plans[case][0].read_bytes())
        if name=='schema_version':struct.pack_into('<I',data,8,2)
        else:struct.pack_into('<Q',data,68,50001)
        plan=d/'mutated.bin';plan.write_bytes(data)
        with (d/'replay.log').open('w') as log:
            proc=subprocess.run([binary,'replay','delayed',str(plan),str(d/'replay.s32le')],stdout=log,stderr=subprocess.STDOUT)
        assert proc.returncode!=0 and 'N6-W0 INVALID:' in (d/'replay.log').read_text(),name
        matrix.append(dict(control=name,case=CASES[case],detected=True,mechanism='schema/plan rejection',earliest=None,pcm_frame=None))
    for name,canonical,altered in [('merge_partition_calls',9,8),('split_partition_calls',8,9)]:
        first=pcm_first_diff(plans[canonical][1],plans[altered][1]);assert first is not None
        matrix.append(dict(control=name,case=CASES[canonical],detected=True,mechanism='exact PCM divergence',earliest=first_record_diff(load(plans[canonical][0])[1],load(plans[altered][0])[1]),pcm_frame=first))
    d=out/'negative'/'capture_overflow';d.mkdir(parents=True,exist_ok=True)
    plan=d/'invalid.bin';pcm=d/'invalid.s32le'
    plan.unlink(missing_ok=True);pcm.unlink(missing_ok=True)
    with (d/'record.log').open('w') as log:
        proc=subprocess.run([binary,'record','12',str(plan),str(pcm)],stdout=log,stderr=subprocess.STDOUT)
    assert proc.returncode!=0 and 'N6-W0 INVALID:' in (d/'record.log').read_text() and not plan.exists() and not pcm.exists()
    matrix.append(dict(control='capture_overflow',case='fixture_capacity',detected=True,
                       mechanism='capture invalidated before publication',earliest=None,pcm_frame=None))
    return matrix

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--sanitizer',action='store_true');a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    binary=compile_test(out,a.sanitizer);results=[];plans={}
    for cid,name in CASES.items():
        d=out/name;d.mkdir(exist_ok=True)
        plan=d/'source.bin';src=d/'source.s32le'
        subprocess.run([binary,'record',str(cid),str(plan),str(src)],check=True,stdout=(d/'record.log').open('w'))
        header,rows=load(plan);plans[cid]=(plan,src)
        for mode in ['immediate','delayed']:
            pcm=d/(mode+'.s32le')
            subprocess.run([binary,'replay',mode,str(plan),str(pcm)],check=True,stdout=(d/(mode+'.log')).open('w'))
            assert pcm.read_bytes()==src.read_bytes(),(name,mode,'PCM')
            assert Path(str(pcm)+'.history').read_bytes()==plan.read_bytes(),(name,mode,'history')
            assert (Path(str(pcm)+'.state')).read_bytes()==(Path(str(src)+'.state')).read_bytes(),(name,mode,'state')
        results.append(dict(case=name,source_history_hash=hash_file(plan),immediate_history_hash=hash_file(Path(str(d/'immediate.s32le')+'.history')),delayed_history_hash=hash_file(Path(str(d/'delayed.s32le')+'.history')),events=len(rows),generation_calls=sum(r['kind']==15 for r in rows),frames=src.stat().st_size//8,pcm_bytes=src.stat().st_size,pcm_sha256=hash_file(src),immediate_pcm_sha256=hash_file(d/'immediate.s32le'),delayed_pcm_sha256=hash_file(d/'delayed.s32le'),state_fingerprint=f"{int.from_bytes(Path(str(src)+'.state').read_bytes(),'little'):016x}",call_spans=call_spans(rows,src),result='PASS'))
    assert fail_if_equal(out/'quiet_large_call/source.s32le',out/'quiet_split_calls/source.s32le')
    def semantics(path):
        return [(r['kind'],r['epoch'],r['time_ns'],r['frame'],r['reg'],r['value'],r['sub']) for r in load(path)[1] if r['kind'] not in (15,16,17)]
    assert semantics(plans[8][0])==semantics(plans[9][0]),'partition pair must preserve semantic events'
    assert (out/'active_partition/source.s32le').read_bytes()==(out/'active_split/source.s32le').read_bytes()
    negative=mutation_suite(binary,out,plans)
    metadata=dict(repository_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),compiler=subprocess.check_output(['cc','--version'],text=True).splitlines()[0],cpu_backend='i286 compile profile',board='SOUNDID_PC_9801_86 (0x04)',opna_backend='native',sample_rate=44100,pcm_format='signed 32-bit little-endian stereo',baseclock=2457600,multiple=20,cpumode=0,initialization='opngen_initialize(44100), opngen_setvol(64), opngen_reset, opngen_setcfg(3, OPN_MONORAL), fixed four-operator channel-2 voice and key-on',active_sources=['native OPNA'],schema=1,sanitizer=a.sanitizer,source_sha256={str(path.relative_to(ROOT)):hash_file(path) for path in [ROOT/'sound/opngenc.c',ROOT/'sound/opngeng.c',ROOT/'sound/sound.c',ROOT/'sound/opntimer.c',ROOT/'tests/host/n6_w0/native_history.c']})
    (out/'report.json').write_text(json.dumps(dict(metadata=metadata,positive=results,negative=negative),indent=2)+'\n')
    print('PASS',len(results),'source/immediate/delayed exact controlled cases and',len(negative),'negative controls')
if __name__=='__main__':main()
