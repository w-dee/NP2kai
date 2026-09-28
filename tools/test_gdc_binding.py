#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Production GDC/PIC/PIT binding and extracted real blink/wait code under UBSan.

Renderer and command execution are stubs here; N4 exercises real guest I/O.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]

def function(text,name):
    a=text.index(name+'(');a=text.rfind('\n',0,a)+1;i=text.index('{',a)+1;depth=1
    while depth:
        depth+=(text[i]=='{')-(text[i]=='}');i+=1
    return text[a:i]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'.local/gdc-machine-pilot/binding');a=p.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);st=out/'stubs'
    shutil.copytree(ROOT/'tests/time_domains/pit_stubs',st,dirs_exist_ok=True)
    q=st/'compiler.h';q.write_text(q.read_text()+'\ntypedef uint32_t RGB32;\n#define MEMCALL\n#define VRAMCALL\n#define LOADINTELWORD(p) ((unsigned)((const unsigned char*)(p))[0]+256u*((const unsigned char*)(p))[1])\n')
    q=st/'pccore.h';q.write_text(q.read_text().replace('typedef struct {int unused;} NP2CFG;', 'typedef struct {unsigned wait[6];int DISPSYNC,RASTER,color16;} NP2CFG;\nextern NP2CFG np2cfg;').replace('UINT32 realclock;','UINT32 realclock,baseclock;').replace('UINT8 screendispflag;','UINT8 screendispflag,screenupdate;'))
    q=st/'cpucore.h';q.write_text(q.read_text().replace('extern unsigned test_accepted;','extern unsigned test_accepted,test_vector;').replace('((void)(v),(void)(s),++test_accepted)','(test_vector=(v),(void)(s),++test_accepted)'))
    q=st/'io/iocore.h';q.write_text(q.read_text().replace('extern struct test_gdc {int vsyncint;} gdc;','#include <io/gdc.h>\n#include <io/gdc_cmd.h>\nextern _GDC gdc;\nextern _GDCS gdcs;'))
    (st/'vram').mkdir(exist_ok=True);(st/'vram/vram.h').write_text('extern unsigned MEMWAIT_TRAM,MEMWAIT_VRAM,MEMWAIT_GRCG;\n')
    src=(ROOT/'tests/time_domains/test_pit_profile.c').read_text();prefix=src[:src.index('static unsigned elapsed,sequence;')]
    prefix=prefix.replace('struct test_gdc gdc;','_GDC gdc;\n_GDCS gdcs;\nNP2CFG np2cfg;\nunsigned test_vector;')
    gdctext=(ROOT/'io/gdc.c').read_text();a1=gdctext.index('typedef struct {');b1=gdctext.index('static const UINT8',a1)
    constants=gdctext[a1:gdctext.index('void gdc_setdegitalpal(')]
    policy=gdctext[gdctext.index('#if !defined(CPUCORE_IA32)'):gdctext.index('typedef struct {')]
    extracted=policy+constants+'\n'+function(gdctext,'gdc_updateclock')+'\n'+function((ROOT/'pccore.c').read_text(),'gdc_machine_blink')+'\n'+function((ROOT/'mem/memtram.c').read_text(),'memtram_rd8')+'\n'+function(gdctext,'gdc_ia0')+'\n'+function(gdctext,'gdc_i60')+'\n'+function(gdctext,'gdc_o6a')+'\n'+function(gdctext,'gdc_biosreset')+'\n'+function(gdctext,'gdc_reset')
    extra='''
#include <time.h>
#include <gdc_machine.h>
#include <vram/maketext.h>
TRAM_T tramflag;
unsigned MEMWAIT_TRAM,MEMWAIT_VRAM,MEMWAIT_GRCG;
extern GDC_SAMPLE gdc_fake_sample;
unsigned work_calls[2];
void gdc_work(int id){work_calls[id]++;if(id)gdc.s.cnt=0;else gdc.m.cnt=0;}
void timing_setrate(unsigned y,unsigned h){(void)y;(void)h;}
unsigned char mem[0x100000],fontrom[0x100000];
unsigned test_inp;
#define CPU_INPADRS test_inp
#define MEML_READ16(a) LOADINTELWORD(mem+(a))
int hf_codeul;
struct{unsigned low,high;}cgwindow;
struct{unsigned operate;}vramop;
struct{unsigned chip;}grcg;
#define VOPBIT_ACCESS 0
#define VOPBIT_EGC 1
#define VOPBIT_ANALOG 4
#define MEMM_VRAM(v) ((void)(v))
#define CopyMemory(d,s,n) memcpy(d,s,n)
void gdc_vectreset(GDCDATA d){(void)d;}
void gdc_setanalogpalall(const UINT16 *p){(void)p;}
static unsigned test_clock_pending(void);
void hook_fontrom(unsigned n){(void)n;}
'''
    unit=out/'binding.c';unit.write_text(prefix+extra+extracted+'\n'+(ROOT/'tests/time_domains/test_gdc_binding.c').read_text()+'\n'+(ROOT/'tests/time_domains/test_gdc_clock_pending.c').read_text())
    reports=[]
    for base in (1996800,2457600):
      for combined in (False,True):
        name=f'binding-{base}-{int(combined)}';binary=out/name
        cmd=['cc','-std=c99','-O2','-g','-Wall','-Wextra','-fsanitize=undefined','-fno-sanitize-recover=all',
             '-I'+str(st),'-I'+str(ROOT),'-DNP2_GDC_MACHINE_TIME','-DNP2_GDC_FAKE_TIME','-DSUPPORT_CRT31KHZ',
             f'-DNP2_GDC_PROFILE_BASE={base}','-DNP2_GDC_SOURCE_ID="host-binding-test"',
             str(unit),str(ROOT/'gdc_time.c'),str(ROOT/'gdc_machine.c'),str(ROOT/'gdc_time_fake.c'),str(ROOT/'nevent.c')]
        if combined:cmd+=['-DNP2_PIT_PIC_MACHINE_TIME',str(ROOT/'pit0_time.c'),str(ROOT/'pit0_machine.c'),str(ROOT/'pit0_time_fake.c')]
        cmd+=['-o',str(binary)]
        subprocess.run(cmd,check=True)
        result=subprocess.check_output([str(binary)],text=True)
        perf=subprocess.check_output([str(binary),'benchmark'],text=True)
        (out/(name+'-performance.json')).write_text(perf)
        reject=subprocess.run([str(binary),'reject-raster'],capture_output=True,text=True)
        if reject.returncode!=-6 or 'admitted profile (1)' not in reject.stderr:raise RuntimeError('RASTER admission failure')
        # Reintroducing the inherited renderer dependency must fail the new
        # ordering regression. Keep every positive canonical assertion intact.
        wrong=out/'renderer_dependency.c'
        machine=(ROOT/'gdc_machine.c').read_text()
        old='if (gdc_machine.clock_pending &&'
        assert machine.count(old)==1
        wrong.write_text(machine.replace(old,'if ((gdcs.grphdisp & GDCSCRN_EXT) &&'))
        negative=cmd.copy()
        negative[negative.index(str(ROOT/'gdc_machine.c'))]=str(wrong)
        negative[-1]=str(out/(name+'-negative'))
        subprocess.run(negative,check=True)
        rejected=subprocess.run([negative[-1]],capture_output=True,text=True)
        assert rejected.returncode==-6 and 'test_clock_pending:' in rejected.stderr and 'gdc.clock==' in rejected.stderr, rejected.stderr
        reports.append(dict(base=base,combined=combined,result=result.strip(),raster_rejected=True,
                            renderer_dependency_rejected=True,performance=json.loads(perf)))
    (out/'report.json').write_text(json.dumps(dict(state='PASS_GDC_BINDING',scope='actual GDC/PIC/PIT, extracted actual clock/blink/TRAM charge; renderer/command stubs',runs=reports),indent=2)+'\n')
    print(json.dumps(reports))

if __name__=='__main__':main()
