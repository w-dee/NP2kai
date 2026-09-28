#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""New bounded propositions, reusing N3's unchanged result verifier and image."""
import argparse,hashlib,json,os,select,shutil,subprocess
from pathlib import Path
from build_i286_time_n3 import build,check_reference
from verify_i286_time_n3 import verify_result
from n3_contract import payload
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--backend',choices=['i286','ia32'],required=True);p.add_argument('--case',choices=['n3','dma-hlt'],required=True);p.add_argument('--off',action='store_true');p.add_argument('--multiple',type=int,default=4);p.add_argument('--baseclock',type=int,default=2457600);a=p.parse_args()
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);binary=a.binary.resolve();image=out/'fixture.hdm'
 for name in ['result.bin','observations.json','report.json']:(out/name).unlink(missing_ok=True)
 if a.case=='n3':check_reference(build(image));hlt=0
 else:
  boot=out/'ipl.bin';subprocess.run(['nasm','-f','bin',str(ROOT/'tests/guest/tier1-timing/src/dma-hlt.asm'),'-o',str(boot)],check=True);data=boot.read_bytes();assert len(data)==1024;hlt=data.index(b'\xf4',512);image.write_bytes(data+bytes(77*2*8*1024-1024))
 cfg=out/'xdg'/('sdlnp2kai' if a.backend=='i286' else 'sdlnp21kai');cfg.mkdir(parents=True,exist_ok=True)
 for name in ['bios.rom','font.rom']:shutil.copyfile(ROOT/'.local/oracle/pristine'/name,cfg/name)
 (cfg/('np2kai.cfg' if a.backend=='i286' else 'np21kai.cfg')).write_text(f'[{"NekoProjectIIkai" if a.backend=="i286" else "NekoProject21kai"}]\nclk_base = {a.baseclock}\nclk_mult = {a.multiple}\npc_model = VX\nExMemory = 1\n')
 script=r'''
import gdb,json
from pathlib import Path
out=Path(OUTPUT);core='i286core.s' if BACKEND=='i286' else 'i386core.s'
errors=[];observations=[];halt_started=False;done=False;calls=0
HZ=23462400000000
def num(s):return int(gdb.parse_and_eval(s))
def word(off):return num('*(unsigned short*)&mem['+str(0x29000+off)+']')
def snapshot(names):return {n:bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval(n).address,gdb.parse_and_eval(n).type.sizeof)).hex() for n in names}
def setvar(name,v):gdb.execute('set variable '+name+' = '+str(v),to_string=True)
def arm(size=4):
 setvar(core+'.remainclock',-1) # Same yield request as real dmac_check readiness.
 setvar('dmac.working',4);setvar('dmac.dmach[2].mode',4);setvar('dmac.dmach[2].adrs.d',0x42000);setvar('dmac.dmach[2].leng.w',size-1)
 setvar('dmac.stat',num('dmac.stat')&~4)
 gdb.selected_inferior().write_memory(gdb.parse_and_eval('&mem[0x42000]'),bytes(size))
 setvar('dmac.dmach[2].proc.inproc','dma_dummyin');setvar('dmac.dmach[2].proc.outproc','dma_dummyout');setvar('dmac.dmach[2].proc.extproc','dma_dummyproc')
def halted():return bool(num('i386core.s.cpu_stat.hlt')) if BACKEND=='ia32' else num('i286core.s.r.w.ip')==HLT
class Armed(gdb.FinishBreakpoint):
 def stop(self):
  try:
   setvar('tier1_fake_now',num('tier1_machine.fdc_due'))
   observations.append(dict(fdc_deadline=num('tier1_machine.fdc_due')))
  except Exception as e:errors.append(str(e));return True
  return False
class Fdc(gdb.Breakpoint):
 def stop(self):Armed(gdb.newest_frame(),internal=True);return False
class HeldFinish(gdb.FinishBreakpoint):
 def __init__(self,before):super().__init__(gdb.newest_frame(),internal=True);self.before=before
 def stop(self):
  try:
   assert self.before==snapshot([core,'dmac']),'held owner service advanced CPU/DMA'
   observations.append(dict(cpu_owner_held_service=True,dma_unchanged=True))
  except Exception as e:errors.append(str(e));return True
  return False
class Service(gdb.Breakpoint):
 def stop(self):
  global halt_started
  try:
   if word(0)!=0x3144 or word(12)!=3 or halt_started or not halted():return False
   arm();halt_started=True
   before=snapshot([core,'dmac']);setvar('tier1_fake_now',HZ);HeldFinish(before)
  except Exception as e:errors.append(str(e));return True
  return False
class DMAFinish(gdb.FinishBreakpoint):
 def __init__(self,before):super().__init__(gdb.newest_frame(),internal=True);self.before=before
 def stop(self):
  global done
  try:
   assert num('dmac.dmach[2].adrs.d')==self.before+1,'not one byte/opportunity'
   if not num('dmac.working'):
    assert num('dmac.dmach[2].leng.w')==65535 and num('dmac.stat')&4
    done=True;observations.append(dict(guest_hlt=True,dma_bytes=4,opportunities=calls,backend=BACKEND));return True
  except Exception as e:errors.append(str(e));return True
  return False
class DMA(gdb.Breakpoint):
 def stop(self):
  global calls
  if halt_started and num('dmac.working')&4:
   calls+=1;DMAFinish(num('dmac.dmach[2].adrs.d'))
  return False
class Step(gdb.Breakpoint):
 def stop(self):
  try:
   if word(0)!=0x3144:return False
   if word(12)==1:arm(64)
   elif word(12)==2:
    assert word(16)==128 and word(18)>0 and num('dmac.dmach[2].adrs.d')==0x42040 and num('dmac.dmach[2].leng.w')==65535, (word(16),num('dmac.dmach[2].adrs.d'),num('dmac.dmach[2].leng.w'))
    observations.append(dict(guest_work=True,dma_bytes=64,partial_memory_observations=word(18),fake_time_frozen=True))
    Service('*tier1_service',internal=True);DMA('*dmax86',internal=True)
  except Exception as e:errors.append(str(e));return True
  return False
class N3Done(gdb.Breakpoint):
 def stop(self):return num('*(unsigned int*)&mem[0x29000]')==0x4446334e and num('mem[0x290fc]') in (2,3)
gdb.execute('start',to_string=True)
if not OFF:Fdc('*fdc_interrupt',internal=True) # Also bootstrap disk IRQs before the HLT fixture.
if CASE=='n3':
 N3Done('mem[0x290fc]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
else:
 Step('*(unsigned short*)&mem[0x2900c]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)

gdb.execute('continue')
assert not errors,errors
if CASE!='n3':assert done and calls==4 and halt_started,'HLT DMA opportunities not qualified'
for name,start,size in [('result.bin',0x29000,256),('buffer-s7.bin',0x40100,1024),('buffer-s8.bin',0x40900,1024)]:
 (out/name).write_bytes(bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval('&mem['+str(start)+']'),size)))
(out/'observations.json').write_text(json.dumps(observations,indent=2)+'\n')
gdb.execute('kill',to_string=True)
'''
 pre='OUTPUT='+repr(str(out))+'\nBACKEND='+repr(a.backend)+'\nCASE='+repr(a.case)+'\nOFF='+repr(a.off)+'\nHLT='+str(hlt)+'\n'
 (out/'capture.py').write_text(pre+script)
 env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(out/'xdg'),SDL_AUDIODRIVER='dummy',OMP_NUM_THREADS='1',LP_NUM_THREADS='1')
 with (out/'xvfb.log').open('wb') as log:xv=subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.PIPE,stderr=log)
 try:
  ready,_,_=select.select([xv.stdout],[],[],15);assert ready;env['DISPLAY']=':'+xv.stdout.readline().decode().strip()
  with (out/'gdb.log').open('w') as log:subprocess.run(['gdb','-q','-batch','-ex','set pagination off','-ex','set confirm off','-ex','source '+str(out/'capture.py'),'--args',str(binary),str(image)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True)
  assert (out/'observations.json').exists(),'guest assertions incomplete; see gdb.log'
  if a.case=='n3':
   result=verify_result((out/'result.bin').read_bytes());assert result['state']=='PASS',result
   for sector in [7,8]:assert (out/f'buffer-s{sector}.bin').read_bytes()==payload(sector)
  else:result=json.loads((out/'observations.json').read_text())
  report=dict(status='PASS_TIER1_'+a.case.upper().replace('-','_'),backend=a.backend,multiple=a.multiple,baseclock=a.baseclock,off=a.off,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),result=result,authority='OWNER_APPROVED_PROFILE_WITH_UNCHANGED_N3_DATA_ASSERTIONS' if a.case=='n3' else 'BACKEND_RELATIONAL_COMPATIBILITY',physical=False)
  (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='result'}))
 finally:
  xv.terminate()
  try:xv.wait(timeout=5)
  except subprocess.TimeoutExpired:xv.kill();xv.wait()
if __name__=='__main__':main()
