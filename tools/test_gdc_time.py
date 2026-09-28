#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Actual production GDC arithmetic against the committed N4 reference."""
import argparse
import ctypes as C
import json
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/guest'))
from gdc_contract import clocks, geometry, reference_phase, reference_points, require
U64=C.c_uint64;U32=C.c_uint32
class Profile(C.Structure):
    _fields_=[(n,U32) for n in ('hclock','vclock','raster','horizontal','display','vertical')]
class Sample(C.Structure):
    _fields_=[('ns',U64),('valid',C.c_int)]
class State(C.Structure):
    _fields_=[(n,U64) for n in ('anchor_ns','ticks','services','rejected','max_gap_ns','transitions','collapsed','max_late_ticks')]+[(n,U32) for n in ('fraction','base','remaining')]+[('anchored',C.c_int),('vsync',C.c_int),('profile',Profile)]
class Edges(C.Structure):
    _fields_=[('vertical',U64),('display',U64),('first_vertical',C.c_int)]


def run(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    libpath=out/'gdc_time.so'
    command=['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined',
             '-fno-sanitize-recover=all','-fPIC','-shared',str(ROOT/'gdc_time.c'),'-o',str(libpath)]
    subprocess.run(command,check=True)
    lib=C.CDLL(str(libpath))
    lib.gdc_profile_make.argtypes=[C.POINTER(Profile),C.POINTER(C.c_uint8),C.c_uint,U32]
    lib.gdc_time_reset.argtypes=[C.POINTER(State),U32,C.POINTER(Profile)]
    lib.gdc_time_sample.argtypes=[C.POINTER(State),Sample,C.POINTER(U64)]
    lib.gdc_time_skip.argtypes=[C.POINTER(State),U64];lib.gdc_time_skip.restype=Edges
    lib.gdc_time_status.argtypes=[C.POINTER(State)];lib.gdc_time_status.restype=C.c_uint
    lib.gdc_time_deadline.argtypes=[C.POINTER(State),C.POINTER(U64)]
    checks=0
    def eq(a,b,label):
        nonlocal checks
        require(a==b,f'{label}: {a!r} != {b!r}');checks+=1
    def observe(s,ns,valid=1):
        ticks=U64()
        ok=lib.gdc_time_sample(C.byref(s),Sample(ns,valid),C.byref(ticks))
        if ok:lib.gdc_time_skip(C.byref(s),ticks.value)
        return ok
    rng=random.Random(0x4e344744)
    rows=[]
    for klass in (15,24,31):
      for base in (1996800,2457600):
       for alternate in (False,True):
        sync=(C.c_uint8*8)(*geometry(klass,alternate)[0]);p=Profile()
        eq(lib.gdc_profile_make(C.byref(p),sync,klass,base),1,'profile admission')
        ref=clocks(klass,base,5,alternate)
        eq([getattr(p,n) for n,_ in p._fields_],list(ref.values()),'parent M5 clocks')
        total=p.display+p.vertical
        def fresh():
            s=State();lib.gdc_time_reset(C.byref(s),base,C.byref(p));observe(s,0);return s
        points=[0,1,p.display-1,p.display,p.display+1,total-1,total,total+1,total*10**12]
        points += [rng.randrange(total*20) for _ in range(1000)]
        points += [v['reference_tick'] for v in reference_points(klass,base)] if not alternate else []
        for q in points:
            s=fresh();e=lib.gdc_time_skip(C.byref(s),q);expected=reference_phase(klass,base,q,alternate)
            eq((s.vsync,s.remaining),(expected['vsync'],expected['remaining']),'exact phase')
            eq(lib.gdc_time_status(C.byref(s)),32*expected['vsync']+64*expected['hblank'],'status bits')
            eq(e.vertical,q//total+int(q%total>=p.display),'V transitions')
            eq(e.display,q//total,'display transitions')
        # Exact accepted ns grid: irregular partitions, equal/invalid/backward.
        s=fresh();now=0
        for _ in range(1000):
            now+=rng.randrange(1000000)
            observe(s,now)
            q,frac=divmod(now*(5*base),1000000000)
            expected=reference_phase(klass,base,q,alternate)
            eq((s.vsync,s.remaining),(expected['vsync'],expected['remaining']),'partitioned phase')
            eq(s.fraction,frac//12800,'reduced rational remainder')
        stable=(s.anchor_ns,s.ticks,s.fraction,s.remaining,s.vsync)
        observe(s,now);observe(s,now-1);observe(s,now+100,0)
        eq((s.anchor_ns,s.ticks,s.fraction,s.remaining,s.vsync),stable,'rejected/equal state')
        eq(s.rejected,2,'rejection diagnostics')
        deadline=U64();eq(lib.gdc_time_deadline(C.byref(s),C.byref(deadline)),1,'deadline valid')
        before=State.from_buffer_copy(s);observe(before,deadline.value-1)
        eq(before.vsync,s.vsync,'deadline minus1ns')
        observe(before,deadline.value);eq(before.vsync,1-s.vsync,'deadline equality')
        huge=fresh();observe(huge,2**64-1)
        q=((2**64-1)*5*base)//1000000000
        expected=reference_phase(klass,base,q,alternate)
        eq((huge.vsync,huge.remaining),(expected['vsync'],expected['remaining']),'UINT64_MAX')
        eq(lib.gdc_time_deadline(C.byref(huge),C.byref(deadline)),0,'deadline overflow')
        rows.append(dict(scan_class=klass,base=base,alternate=alternate,state='PASS'))
    # Service complexity: same compiled analytical function, no semantic budget.
    p=Profile();sync=(C.c_uint8*8)(*geometry(24)[0]);lib.gdc_profile_make(C.byref(p),sync,24,2457600)
    perf=[]
    for frames in (1,5,10**12):
        s=State();lib.gdc_time_reset(C.byref(s),2457600,C.byref(p))
        started=time.process_time_ns()
        for _ in range(20000):lib.gdc_time_skip(C.byref(s),frames*(p.display+p.vertical))
        perf.append(dict(frames=frames,ns_per_ctypes_call=(time.process_time_ns()-started)/20000))
    result=dict(state='PASS_GDC_ARITHMETIC',checks=checks,profiles=rows,performance=perf,
                performance_scope='Python FFI plus actual C skip; no numeric product budget',compiler=command)
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(state=result['state'],checks=checks,performance=perf)))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='.local/gdc-machine-pilot/math');a=p.parse_args();run(a.output)
