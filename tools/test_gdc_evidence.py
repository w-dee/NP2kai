#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Revalidate captured N4 artifacts, cross-run equality and rejection controls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/guest'))
from gdc_contract import parse_result, require
from gdc_machine_contract import verify_machine
from run_gdc_machine import source_id

def sha(data):return hashlib.sha256(data).hexdigest()
def read(directory):
    r=json.loads((directory/'report.json').read_text())
    data=(directory/'result.bin').read_bytes();raw=(directory/'machine-capture.json').read_bytes()
    require(sha(data)==r['result_sha256'] and sha(raw)==r['capture_sha256'],'artifact identity')
    require(sha((directory/'gdc.hdm').read_bytes())==r['image_sha256'],'guest image identity')
    require(r['source_id']==source_id(),'product source freshness')
    binary=ROOT/f"build_gdc_{r['backend']}_fake_{r['profile_base']}"/('sdlnp2kai_sdl2' if r['backend']=='i286' else 'sdlnp21kai_sdl2')
    require(sha(binary.read_bytes())==r['binary_sha256'],'binary identity')
    records=parse_result(data,mode=2,scan_class=r['scan_class'],build_id=r['build_id'])
    require(records==r['records'],'report differs from raw RAM')
    capture=json.loads(raw)
    verify_machine(records,capture,scan_class=r['scan_class'],profile_base=r['profile_base'],
                   baseclock=r['baseclock'],multiple=r['multiple'],schedule=r.get('schedule','canonical'))
    return r,capture

def bounded(r):
    # Other PIC inputs and CPU polling/flags are outside GDC authority.
    return [{k:v for k,v in x.items() if k not in ('irr','isr','imr','handler_isr','after_eoi','polls','saved_flags')}
            |{k:x[k]&4 for k in ('irr','isr','imr','handler_isr','after_eoi')}
            |{'saved_if':x['saved_flags']&512} for x in r['records']]

def run(out):
    rows=[];negatives=[];total=0
    for b,classes in [('i286',[15,24]),('ia32',[15,24,31])]:
      for c in classes:
       for p in [1996800,2457600]:
        directory=out/'n4-final'/f'{b}-{c}-p{p}-r1996800-m4'
        ref,cap=read(directory)
        for runtime in [1996800,2457600]:
         for m in [1,4,20]:
            r,t=read(out/'n4-final'/f'{b}-{c}-p{p}-r{runtime}-m{m}');total+=1
            require(bounded(ref)==bounded(r),'runtime CPU dependence')
        for variant in ('presentation_suppressed','fractional_and_partitioned','frozen_repeat','boundary_variants'):
            r,t=read(out/'n4-extra'/f'{b}-{c}-p{p}-{variant}');total+=1
            if variant in ('presentation_suppressed','fractional_and_partitioned'):
                require(bounded(ref)==bounded(r),'paired guest state')
                for x,y in zip(cap['trace'],t['trace']):
                    a,z=x['state'],y['state']
                    keys=('gdc_machine.time.remaining','gdc_machine.time.fraction','gdc_machine.time.vsync','gdc.clock','gdc.vsyncint')
                    require(all(a['values'][k]==z['values'][k] for k in keys),'paired phase/remainder')
                    require(a['master_sync']==z['master_sync'] and a['slave_sync']==z['slave_sync'],'paired geometry')
                    require(a['blink'][:2]==z['blink'][:2],'paired blink')
            a=t['trace'][0]['state']['values'];z=t['trace'][-1]['state']['values']
            if variant=='presentation_suppressed':require(a['gdc_machine.presentations']==z['gdc_machine.presentations'],'suppressed draw')
            rows.append(dict(backend=b,scan_class=c,base=p,variant=variant,
                             generation_delta=z['gdc_machine.generation']-a['gdc_machine.generation'],
                             presentations=z['gdc_machine.presentations']-a['gdc_machine.presentations']))
        rendered,rc=read(out/'n4-render'/f'{b}-{c}-p{p}-presentation_suppressed');total+=1
        require(bounded(ref)==bounded(rendered),'render follow-up guest equality')
        require('drawcount' in rc['presentation']['after']['values'],'missing actual draw evidence')
        require(rc['trace'][0]['state']['values']['drawcount']==rc['trace'][-1]['state']['values']['drawcount'],'host drew during suppression')
        # Mutations are copies of host observations; never guest RAM writes.
        for label in ('direct_read','phase','held_cpu','hlt','latest_present','missing_case'):
            changed=deepcopy(cap)
            if label=='direct_read':changed['reads'][0]['raw']^=0x20
            elif label=='phase':changed['trace'][0]['state']['values']['gdc_machine.time.remaining']+=1
            elif label=='held_cpu':next(s for s in changed['services'] if s['label']=='CPU-held-time-advanced')['cpu_unchanged']=False
            elif label=='hlt':changed['halted_serviced']=False
            elif label=='latest_present':changed['presentation']['after']['values']['gdc_machine.presented']-=1
            else:changed['trace'].pop()
            try:verify_machine(ref['records'],changed,scan_class=c,profile_base=p,baseclock=1996800,multiple=4)
            except ValueError:negatives.append(label)
            else:raise ValueError('negative control accepted: '+label)
        data=(directory/'result.bin').read_bytes()
        for label,change in [('crc',128),('schema',4),('stale_id',16)]:
            damaged=bytearray(data);damaged[change]^=1
            try:parse_result(bytes(damaged),mode=2,scan_class=c,build_id=ref['build_id'])
            except ValueError:negatives.append(label)
            else:raise ValueError('invalid RAM accepted: '+label)
    report=dict(state='PASS_GDC_CAPTURE_EVIDENCE',validated_runs=total,negative_controls=len(negatives),
                comparisons=rows,scope='bounded GDC state; unrelated PIC bits and CPU polling counts excluded')
    (out/'evidence-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS {total} captures, {len(negatives)} rejection controls, runtime and presentation equality')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'.local/gdc-machine-pilot')
    run(p.parse_args().output)
