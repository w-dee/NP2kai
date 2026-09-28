#!/usr/bin/env python3
"""N6-C real semantic history + independent W0 exact waveform plan binding."""
import argparse, copy, hashlib, json, os, shutil, subprocess
from pathlib import Path
from test_n6_w0 import compile_test, load, save, change_groups, hash_file, pcm_first_diff
from test_opna_csm_history import run as run_n6_c
ROOT = Path(__file__).resolve().parents[1]
CASES = {
 'p0_baseline':1, 'p1_single':2, 'p2_repeated':3, 'p3_batched':3,
 'p4_key':4, 'p5_frequency':5, 'p6_same_frontier':13,
 'p7_rewrite':3, 'p8_stop_restart':3, 'p9_reset':6,
 'p10_quiet':9, 'p10_quiet_large':8, 'p11_active':10,
}

def canonical(obj): return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def digest(data): return hashlib.sha256(data).hexdigest()
def check(ok, where, detail):
    if not ok: raise ValueError(f'{where}: {detail}')

def capture(binary, out, backend, case):
    work=out/backend/case;work.mkdir(parents=True,exist_ok=True)
    cfg=work/'xdg'/('sdlnp2kai' if backend=='i286' else 'sdlnp21kai')
    cfg.mkdir(parents=True,exist_ok=True)
    for name in ('bios.rom','font.rom'):
        shutil.copyfile(ROOT/'.local/oracle/pristine'/name,cfg/name)
    section='NekoProjectIIkai' if backend=='i286' else 'NekoProject21kai'
    ini='np2kai.cfg' if backend=='i286' else 'np21kai.cfg'
    (cfg/ini).write_text(f'[{section}]\nclk_base = 2457600\nclk_mult = 4\nSNDboard = 04\nopt86BRD = 7d\nUSEFMGEN = false\n')
    (work/'parameters.json').write_text(json.dumps(dict(case=case,backend=backend,out=str(work))))
    (work/'capture.py').write_text('PARAMETERS='+repr(str(work/'parameters.json'))+'\n'+(ROOT/'tests/time_domains/n6_w_semantic_binding.py').read_text())
    env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(work/'xdg'),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    with (work/'gdb.log').open('w') as log:
        subprocess.run(['gdb','-q','-batch','-ex','set confirm off','-ex','set pagination off',
            '-ex','set python print-stack full','-ex','set debuginfod enabled off',
            '-ex','source '+str(work/'capture.py'),'--args',str(binary)],env=env,
            stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    data=json.loads((work/'semantic.json').read_text())
    check(data['result']=='PASS','capture','GDB fixture did not pass')
    return data

def bind(case, sem, rows, reference):
    """Fail before W0 replay. Semantic CSM records authorize exact W0 CSM slots."""
    check(sem['case']==case and sem['board']==4 and sem['baseclock']==2457600,
          'fixture','identity/profile')
    check(all(v==0 for v in sem['machine_owner_synthesis_calls'].values()),
          'semantic','synthesis in machine-time owner')
    segments=sem['segments']
    check(len(segments)==(2 if case=='p9_reset' else 1),'semantic','epoch count')
    all_records=[]
    for e,segment in enumerate(segments,2):
        records=segment['records'];previous_deadline=0
        check(segment['epoch']==e,'semantic','wrong epoch')
        check(segment['finalized_count']==len(records) and segment['next_sequence']==len(records),
              'semantic','required prefix not finalized')
        for seq,r in enumerate(records):
            check(r['epoch']==e and r['sequence']==seq,'semantic',f'epoch/sequence at {seq}')
            check(r['kind']==1 and (r['off'],r['on'])==(0,1),'semantic',f'CSM pair at {seq}')
            check(r['ordinal']==seq+1,'semantic',f'Timer A ordinal at {seq}')
            check(r['deadline_ns']>previous_deadline and r['service_ns']>=r['deadline_ns'],
                  'semantic',f'deadline/service at {seq}')
            previous_deadline=r['deadline_ns']
            all_records.append(r)
    expected=sem['expected']
    check(len(expected)==len(all_records),'semantic','missing or extra expected CSM')
    for i,(r,x) in enumerate(zip(all_records,expected)):
        check((r['epoch'],r['sequence'],r['deadline_ns'])==
              (x['epoch'],x['sequence'],x['deadline_ns']),
              'semantic',f'logical deadline/order at {i}')
    if case in ('p4_key','p5_frequency'):
        registers=[x['register'] for x in sem['operations']]
        check(registers==([0x28] if case=='p4_key' else [0xa6,0xa2]),
              'semantic','same-time guest-operation order')
        check(all(x['preceding_csm']==1 and x['finalized']==1 and
                  x['machine_ns']==all_records[0]['deadline_ns'] for x in sem['operations']),
              'semantic','guest operation before settled CSM')
        hits=sem['guest_hits']
        expected_hits=[(0x28,'opngen_keyon')] if case=='p4_key' else [
            (0xa6,'opngen_setreg'),(0xa2,'opngen_setreg')]
        check([(x['register'],x['operation']) for x in hits]==expected_hits and
              all(x['preceding_csm']==1 and x['servicing']==0 for x in hits),
              'semantic','guest native operation order at finalized CSM frontier')
    if case=='p3_batched':
        check(len(all_records)==10 and len({x['service_ns'] for x in all_records})==1 and
              len({x['deadline_ns'] for x in all_records})==10,
              'semantic','multi-expiry service collapsed')
    if case=='p6_same_frontier':
        check(len(all_records)==2 and all_records[0]['service_ns']==all_records[1]['service_ns'],
              'semantic','same-service CSM records')
    if case=='p8_stop_restart':
        check(len(all_records)==10 and all_records[1]['deadline_ns']>10*all_records[0]['deadline_ns'],
              'semantic','phantom CSM in stopped interval')
    if case=='p7_rewrite':
        check([x['register'] for x in sem['operations']]==[0x24,0x25],
              'semantic','timer period rewrite missing')
    # The W0 source is the independent, frozen producer plan. Exact row
    # comparison also protects non-CSM writes, generation calls and frontiers.
    check(len(rows)==len(reference),'plan','entry count')
    for i,(r,x) in enumerate(zip(rows,reference)):
        check(r==x,'plan',f'entry {i}, kind {x["kind"]}, frontier {x["frame"]}')
    slots=[(i,r) for i,r in enumerate(rows) if r['kind']==10]
    check(len(slots)==len(all_records),'binding','CSM slot count')
    mapping=[]
    for index,((plan_index,slot),semantic) in enumerate(zip(slots,all_records)):
        epoch=semantic['epoch']-1
        check(slot['epoch']==epoch,'binding',f'cross-epoch CSM {index}')
        next_index=slots[index+1][0] if index+1<len(slots) else len(rows)
        off=[(j,r) for j,r in enumerate(rows[plan_index+1:next_index],plan_index+1)
             if r['kind']==11 and r['parent']==slot['seq']]
        on=[(j,r) for j,r in enumerate(rows[plan_index+1:next_index],plan_index+1)
            if r['kind']==12 and r['parent']==slot['seq']]
        check(len(off)==len(on)==1 and plan_index<off[0][0]<on[0][0] and
              off[0][1]['sub']==semantic['off'] and on[0][1]['sub']==semantic['on'],
              'binding',f'CSM off/on structure {index}')
        mapping.append(dict(machine_epoch=semantic['epoch'],semantic_sequence=semantic['sequence'],
            deadline_ns=semantic['deadline_ns'],service_ns=semantic['service_ns'],
            plan_epoch=slot['epoch'],plan_entry=plan_index,off_entry=off[0][0],on_entry=on[0][0],
            sample_frontier=slot['frame']))
    if case=='p6_same_frontier':
        check(mapping[0]['sample_frontier']==mapping[1]['sample_frontier'],
              'binding','CSM frontier not shared')
    if case in ('p4_key','p5_frequency'):
        start=mapping[0]['on_entry']
        if case=='p4_key':
            later=[r for r in rows[start+1:] if r['kind']==4]
            check(bool(later) and later[0]['frame']==mapping[0]['sample_frontier'],
                  'binding','guest key sequence/frontier')
        else:
            later=[r for r in rows[start+1:] if r['kind']==2 and r['reg'] in (0xa6,0xa2)]
            check(len(later)>=2 and [x['reg'] for x in later[:2]]==[0xa6,0xa2] and
                  all(x['frame']==mapping[0]['sample_frontier'] for x in later[:2]),
                  'binding','frequency acceptance sequence/frontier')
    return mapping

def materialize(case, sem, rows, reference):
    """Fill the source plan's CSM slots from N6-C semantic records."""
    mapping=bind(case,sem,rows,reference)
    bound=copy.deepcopy(rows)
    records=[r for segment in sem['segments'] for r in segment['records']]
    for slot,semantic in zip(mapping,records):
        pair=bound[slot['plan_entry']]
        off=bound[slot['off_entry']]
        on=bound[slot['on_entry']]
        # The controlled source provides frontier, call partition and parent
        # slots. N6-C provides whether the CSM pair exists and its sub-order.
        for entry in (pair,off,on):
            entry['kind']=0;entry['sub']=0;entry['value']=0
        check(semantic['kind']==1 and (semantic['off'],semantic['on'])==(0,1),
              'binding','unrecognized semantic CSM pair')
        pair['kind']=10
        off.update(kind=11,sub=semantic['off'],value=2)
        on.update(kind=12,sub=semantic['on'],value=0xf2)
    check(bound==reference,'binding','materialized plan differs from controlled source')
    return mapping,bound

def replay(binary, mode, plan, pcm):
    with (Path(str(pcm)+'.log')).open('w') as log:
        subprocess.run([binary,'replay',mode,str(plan),str(pcm)],stdout=log,
                       stderr=subprocess.STDOUT,check=True)

def mutations(case, sem, rows, ref):
    """Each corruption must fail binding before worker publication."""
    controls=[]
    def run(name,change):
        s=copy.deepcopy(sem);r=copy.deepcopy(rows);change(s,r)
        measured=None
        if name.startswith('semantic_') and name.endswith('x'):
            original_deadlines=[x['deadline_ns'] for x in sem['segments'][0]['records']]
            mutated_deadlines=[x['deadline_ns'] for x in s['segments'][0]['records']]
            measured=(mutated_deadlines[-1]-mutated_deadlines[0])/(original_deadlines[-1]-original_deadlines[0])
            target=1.5 if name=='semantic_1_5x' else 1.7
            assert abs(measured-target)<0.0001,(name,measured)
        try:bind(case,s,r,ref)
        except ValueError as e:
            controls.append(dict(control=name,detected=True,first_mismatch=str(e),measured_time_scale=measured));return
        raise AssertionError(f'undetected {name}')
    if case in ('p2_repeated','p3_batched'):
        def remove_semantic(s,r):
            segment=s['segments'][0];segment['records'].pop();s['expected'].pop()
            segment['finalized_count']-=1;segment['next_sequence']-=1
        def append_semantic(s,r):
            segment=s['segments'][0];new=copy.deepcopy(segment['records'][-1])
            new['sequence']+=1;new['ordinal']+=1
            new['deadline_ns']+=17904;new['service_ns']=new['deadline_ns']
            segment['records'].append(new);segment['finalized_count']+=1
            segment['next_sequence']+=1
            s['expected'].append(dict(epoch=new['epoch'],sequence=new['sequence'],deadline_ns=new['deadline_ns']))
        if case=='p2_repeated':
            run('plan_refers_missing_semantic',remove_semantic)
            run('semantic_without_plan',append_semantic)
    if case=='p3_batched':
        run('missing_csm',remove_semantic)
        run('extra_csm',append_semantic)
        run('csm_order_swap',lambda s,r:s['segments'][0]['records'].__setitem__(slice(0,2),list(reversed(s['segments'][0]['records'][:2]))))
        run('wrong_semantic_sequence',lambda s,r:s['segments'][0]['records'][2].__setitem__('sequence',99))
        run('same_timestamp_wrong_sequence',lambda s,r:(s['segments'][0]['records'][0].__setitem__('service_ns',s['segments'][0]['records'][1]['service_ns']),s['segments'][0]['records'][1].__setitem__('sequence',0)))
        run('semantic_1_5x',lambda s,r:[x.update(deadline_ns=x['deadline_ns']*3//2,service_ns=x['service_ns']*3//2) for x in s['segments'][0]['records']])
        run('semantic_1_7x',lambda s,r:[x.update(deadline_ns=x['deadline_ns']*17//10,service_ns=x['service_ns']*17//10) for x in s['segments'][0]['records']])
        run('premature_finalization',lambda s,r:s['segments'][0].__setitem__('finalized_count',0))
        run('render_before_prefix',lambda s,r:s['segments'][0].__setitem__('finalized_count',len(s['segments'][0]['records'])-1))
        run('retrospective_semantic_event',lambda s,r:s['segments'][0]['records'][3].__setitem__('deadline_ns',1))
        run('plan_missing_semantic',lambda s,r:r.__setitem__(slice(None),change_groups(r,'remove',{10})))
        run('plan_generation_reorder',lambda s,r:r.__setitem__(slice(None),change_groups(r,'swap',{15})))
        run('plan_wrong_frame_count',lambda s,r:next(x for x in r if x['kind']==15).__setitem__('actual',301))
    if case=='p4_key':
        run('csm_guest_key_reversed',lambda s,r:r.__setitem__(slice(None),change_groups(r,'swap',{10,4})))
        run('frontier_plus_one',lambda s,r:next(x for x in r if x['kind']==10).__setitem__('frame',301))
        run('frontier_minus_one',lambda s,r:next(x for x in r if x['kind']==10).__setitem__('frame',299))
    if case=='p5_frequency':
        run('frequency_write_reversed',lambda s,r:s['operations'].__setitem__(slice(None),list(reversed(s['operations']))))
    if case=='p6_same_frontier':
        run('csm_pair_off_on_inversion',lambda s,r:(s['segments'][0]['records'][0].__setitem__('off',1),s['segments'][0]['records'][0].__setitem__('on',0)))
    if case=='p9_reset':
        run('wrong_epoch',lambda s,r:s['segments'][1]['records'][0].__setitem__('epoch',99))
        run('stale_old_epoch',lambda s,r:s['segments'][1]['records'][0].__setitem__('epoch',2))
    return controls

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--sanitizer',action='store_true');ap.add_argument('--backend',choices=['i286','ia32','both'],default='both')
    ap.add_argument('--i286-binary',type=Path,default=ROOT/'.local/n6-c/build-i286-fake/sdlnp2kai_sdl2')
    ap.add_argument('--ia32-binary',type=Path,default=ROOT/'.local/n6-c/build-ia32-fake/sdlnp21kai_sdl2')
    a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    w0=compile_test(out,a.sanitizer);plans={};records={}
    for cid in sorted(set(CASES.values())|{8,11}):
        work=out/'w0'/str(cid);work.mkdir(parents=True,exist_ok=True)
        plan=work/'source.bin';pcm=work/'source.s32le'
        with (work/'record.log').open('w') as log:
            subprocess.run([w0,'record',str(cid),str(plan),str(pcm)],stdout=log,check=True)
        plans[cid]=(plan,pcm);records[cid]=load(plan)[1]
    positives=[];negative=[]
    backends=['i286','ia32'] if a.backend=='both' else [a.backend]
    for backend in backends:
        product=(a.i286_binary if backend=='i286' else a.ia32_binary).resolve()
        for case,cid in CASES.items():
            sem=capture(product,out,backend,case)
            plan,source=plans[cid];rows=records[cid]
            mapping,bound_rows=materialize(case,sem,rows,records[cid])
            work=out/backend/case
            bound=work/'bound.bin';save(bound,load(plan)[0],bound_rows)
            check(bound.read_bytes()==plan.read_bytes(),'binding','W0 source plan byte equality')
            (work/'binding.json').write_text(json.dumps(mapping,indent=2)+'\n')
            semantic_records=[r for seg in sem['segments'] for r in seg['records']]
            semantic_hash=digest(canonical(semantic_records))
            bundle=dict(fixture_id=case,semantic_records=semantic_records,
                        semantic_history_sha256=semantic_hash,mapping=mapping,
                        w0_plan_sha256=hash_file(bound))
            (work/'bound-manifest.json').write_text(json.dumps(bundle,indent=2)+'\n')
            consumed_semantic={}
            for mode in ('immediate','delayed'):
                worker_bundle=copy.deepcopy(bundle)
                check(worker_bundle['semantic_history_sha256']==digest(canonical(worker_bundle['semantic_records']))
                      and worker_bundle['w0_plan_sha256']==hash_file(bound),
                      'publication',f'{backend} {case} {mode}')
                consumed_semantic[mode]=digest(canonical(worker_bundle['semantic_records']))
                pcm=work/(mode+'.s32le');replay(w0,mode,bound,pcm)
                check(pcm.read_bytes()==source.read_bytes(),'PCM',f'{backend} {case} {mode}')
                check(Path(str(pcm)+'.state').read_bytes()==Path(str(source)+'.state').read_bytes(),
                      'state',f'{backend} {case} {mode}')
                check(Path(str(pcm)+'.history').read_bytes()==bound.read_bytes(),
                      'consumed plan',f'{backend} {case} {mode}')
            check((work/'immediate.s32le').read_bytes()==(work/'delayed.s32le').read_bytes(),
                  'PCM','serial/delayed')
            check(consumed_semantic['immediate']==consumed_semantic['delayed']==semantic_hash,
                  'semantic','serial/delayed consumed history')
            row=dict(fixture_id=case,backend=backend,semantic_history_sha256=semantic_hash,
                serial_semantic_history_sha256=consumed_semantic['immediate'],
                delayed_semantic_history_sha256=consumed_semantic['delayed'],
                bound_plan_sha256=digest(canonical(mapping)+bound.read_bytes()),
                events=len(rows),csm=len(mapping),generation_calls=sum(r['kind']==15 for r in rows),
                epochs=len(sem['segments']),frames=source.stat().st_size//8,pcm_bytes=source.stat().st_size,
                pcm_sha256=hash_file(source),state_fingerprint=f"{int.from_bytes(Path(str(source)+'.state').read_bytes(),'little'):016x}",
                serial='PASS',delayed='PASS',mapping=mapping)
            positives.append(row)
            if backend==backends[0]:negative += [dict(fixture_id=case,**r) for r in mutations(case,sem,rows,records[cid])]
    # The quiet-tail partition pair is an exact changed-call-sequence control.
    sem_quiet=json.loads((out/backends[0]/'p10_quiet_large'/'semantic.json').read_text())
    sem_split=json.loads((out/backends[0]/'p10_quiet'/'semantic.json').read_text())
    for name,case,sem,altered,reference in (
        ('generation_call_split','p10_quiet_large',sem_quiet,records[9],records[8]),
        ('generation_call_merge','p10_quiet',sem_split,records[8],records[9])):
        try:bind(case,sem,altered,reference)
        except ValueError as e:negative.append(dict(fixture_id=case,control=name,detected=True,first_mismatch=str(e)))
        else:raise AssertionError(f'undetected {name}')
    # W0 establishes this bounded counterexample and bounded equivalence.
    q8,q9=plans[8][1],plans[9][1];check(pcm_first_diff(q8,q9) is not None,'partition','quiet tail must differ')
    a10,a11=plans[10][1],plans[11][1];check(a10.read_bytes()==a11.read_bytes(),'partition','active PCM equivalence')
    check(Path(str(a10)+'.state').read_bytes()==Path(str(a11)+'.state').read_bytes(),
          'partition','active state equivalence')
    # Explicitly bind the qualified alternative to the same N6-C semantic source.
    sem= json.loads((out/backends[0]/'p11_active'/'semantic.json').read_text())
    alt=copy.deepcopy(records[11]);original=records[10]
    def semantic_tokens(rows):
        return [(r['kind'],r['epoch'],r['reg'],r['value'],r['sub']) for r in rows if r['kind'] not in (15,16,17)]
    check(semantic_tokens(alt)==semantic_tokens(original),'partition','active semantic mismatch')
    # Explicit bounded exception: the same semantic-slot binding is checked;
    # only W0's already-qualified alternate generation partition is admitted.
    bind('p11_active',sem,alt,alt)
    altout=out/'active_alternative.s32le';replay(w0,'delayed',plans[11][0],altout)
    check(altout.read_bytes()==a10.read_bytes(),'partition','active alternate replay PCM')
    check(Path(str(altout)+'.state').read_bytes()==Path(str(a10)+'.state').read_bytes(),
          'partition','active alternate replay state')
    # N6-C admission is exercised on the real product binary; no worker plan
    # is published on rejection, so no partial PCM artifact can be created.
    for backend in backends:
        reject=run_n6_c((a.i286_binary if backend=='i286' else a.ia32_binary).resolve(),
                        out/'admission'/backend,backend,2457600,'capacity_plus_one')
        check(reject['rejection']==7 and reject['machine_owner_synthesis_calls']==
              {'sound_sync':0,'opngen_csm':0,'opngen_getpcm':0},'admission',backend)
        check(not list((out/'admission'/backend).rglob('*.s32le')),'admission','partial PCM')
    report=dict(status='PASS_N6_W_MACHINE_HISTORY_EXACT_WAVEFORM_REPLAY_INTEGRATION',
        metadata=dict(w0_binary_sha256=hash_file(w0),sanitizer=a.sanitizer,backends=backends,
                      host_csm_capacity=256,pcm_format='44100 Hz signed 32-bit little-endian stereo'),
        positives=positives,negative=negative,
        quiet_partition_first_diff_frame=pcm_first_diff(q8,q9),active_partition_equivalent=True,
        admission_rejection_no_pcm=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(positives),'integrated exact cases,',len(negative),'binding negatives')
if __name__=='__main__':main()
