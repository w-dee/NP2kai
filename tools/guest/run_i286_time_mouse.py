#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Real guest IRQ13/EOI and CPU-held fake-time N5 qualification (Linux GDB)."""
import argparse,hashlib,json,os,select,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def qualify(binary,out,backend,multiple,base):
 out=out.resolve();out.mkdir(parents=True,exist_ok=True);binary=binary.resolve()
 (out/'result.bin').unlink(missing_ok=True)
 boot=out/'ipl.bin';subprocess.run(['nasm','-f','bin',str(ROOT/'tests/guest/i286-time-mouse/src/ipl.asm'),'-o',str(boot)],check=True)
 data=boot.read_bytes();assert len(data)==1024 and data[510:512]==data[1022:1024]==b'\x55\xaa'
 image=out/'mouse.hdm';image.write_bytes(data+bytes(77*2*8*1024-len(data)))
 cfg=out/'xdg'/('sdlnp2kai' if backend=='i286' else 'sdlnp21kai');cfg.mkdir(parents=True,exist_ok=True)
 for name in ['bios.rom','font.rom']:shutil.copyfile(ROOT/'.local/oracle/pristine'/name,cfg/name)
 (cfg/('np2kai.cfg' if backend=='i286' else 'np21kai.cfg')).write_text(f'[{"NekoProjectIIkai" if backend=="i286" else "NekoProject21kai"}]\nclk_base = {base}\nclk_mult = {multiple}\npc_model = VX\nExMemory = 1\n')
 script=r'''
import gdb,json
from pathlib import Path
out=Path(OUTPUT);backend=BACKEND
core='i286core.s' if backend=='i286' else 'i386core.s'
log=[];errors=[];held=False
P=1175000000
q=0
def num(x):return int(gdb.parse_and_eval(x))
def word(off):return num('*(unsigned short*)&mem['+str(0x29000+off)+']')
def snap(names):
 return {n:bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval(n).address,gdb.parse_and_eval(n).type.sizeof)).hex() for n in names}
def advance(t):
 global q
 q=t;gdb.execute('set variable mouse_fake_now = '+str(t),to_string=True)
 log.append(dict(step=word(12),q=t,clock=num(core+'.clock'),base=num(core+'.baseclock'),remaining=num(core+'.remainclock')))
class Finished(gdb.FinishBreakpoint):
 def __init__(self,before):super().__init__(gdb.newest_frame(),internal=True);self.before=before
 def stop(self):
  try:
   assert self.before==snap([core,'artic','gdc','dmac','g_nevent']),'mouse service mutated CPU/other devices'
   assert num('pic.pi[1].irr')&32
   log.append(dict(cpu_held_service=True,other_state_unchanged=True,publications=num('mouse_machine.publications')))
  except Exception as e:errors.append(str(e));return True
  return False
class Service(gdb.Breakpoint):
 def stop(self):
  global held
  try:
   if word(12)!=4 or held:return False
   halted=bool(num('i386core.s.cpu_stat.hlt')) if backend=='ia32' else False
   # i286 uses the HLT opcode address. Its offset is supplied from the guest
   # image listing by the host runner, independent of device implementation.
   if backend=='i286':halted=num('i286core.s.r.w.ip')==HLT_OFFSET
   if not halted:return False
   before=snap([core,'artic','gdc','dmac','g_nevent']);advance(8*P);held=True;Finished(before)
  except Exception as e:errors.append(str(e));return True
  return False
class Step(gdb.Breakpoint):
 def stop(self):
  try:
   if num('*(unsigned int*)&mem[0x29000]')!=0x4d54354e:return False
   step=word(12)
   if step in (1,):advance(0)
   elif step==2:advance(7*P)
   elif step==3:advance(7*P)
   elif step==4:Service('*mouse_machine_service',internal=True)
  except Exception as e:errors.append(str(e));return True
  return False
class Done(gdb.Breakpoint):
 def stop(self):return num('*(unsigned int*)&mem[0x29000]')==0x4d54354e and word(126)==2
gdb.execute('start',to_string=True)
Step('*(unsigned short*)&mem[0x2900c]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
Done('*(unsigned short*)&mem[0x2907e]',type=gdb.BP_WATCHPOINT,wp_class=gdb.WP_WRITE,internal=True)
gdb.execute('continue')
assert not errors,errors
assert word(126)==2 and held,'guest terminal/HLT missing'
assert word(16)==8192,'frozen-time CPU work'
assert not(word(18)&32),'IRQ with frozen fake time'
assert word(20)&32 and word(22)==0,'held masked pending publication'
assert word(24)==2 and word(36)==2,'two real guest handlers'
assert word(26)&32 and not(word(28)&32),'ISR/EOI'
assert word(34)==0x1234,'HLT continuation'
assert num('mouse_machine.publications')==8,'logical IRQ publication count'
(out/'result.bin').write_bytes(bytes(gdb.selected_inferior().read_memory(gdb.parse_and_eval('&mem[0x29000]'),128)))
(out/'service.json').write_text(json.dumps(log,indent=2)+'\n')
gdb.execute('kill',to_string=True)
'''
 # STI; HLT; CLI appears once in this original image; HLT offset is exact.
 hlt=data.index(b'\xfb\xf4\xfa')+1
 script='OUTPUT='+repr(str(out))+'\nBACKEND='+repr(backend)+'\nHLT_OFFSET='+str(hlt)+'\n'+script
 (out/'capture.py').write_text(script)
 env=os.environ.copy();env.update(XDG_CONFIG_HOME=str(out/'xdg'),SDL_AUDIODRIVER='dummy',OMP_NUM_THREADS='1',LP_NUM_THREADS='1')
 with (out/'xvfb.log').open('wb') as log:xv=subprocess.Popen(['Xvfb','-displayfd','1','-screen','0','1024x768x24','-nolisten','tcp'],stdout=subprocess.PIPE,stderr=log)
 try:
  ready,_,_=select.select([xv.stdout],[],[],15);assert ready
  env['DISPLAY']=':'+xv.stdout.readline().decode().strip()
  with (out/'gdb.log').open('w') as log:subprocess.run(['gdb','-q','-batch','-ex','set pagination off','-ex','set confirm off','-ex','source '+str(out/'capture.py'),'--args',str(binary),str(image)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90,check=True)
  assert (out/'result.bin').exists(),'GDB did not complete all assertions'
  report=dict(status='PASS_N5_REAL_GUEST_IRQ13_ACCEPTANCE_EOI_HLT',authority='OWNER_APPROVED_NORMALIZED_PROFILE_AND_DEVICE_RELATIONAL_ASSERTION',backend=backend,multiple=multiple,baseclock=base,guest_handlers=2,logical_publications=8,cpu_held_service=True,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),physical_hardware=False,live_realtime=False)
  (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
 finally:
  xv.terminate()
  try:xv.wait(timeout=5)
  except subprocess.TimeoutExpired:xv.kill();xv.wait()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--binary',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--backend',required=True,choices=['i286','ia32']);p.add_argument('--multiple',type=int,default=4);p.add_argument('--baseclock',type=int,default=2457600,choices=[2457600,1996800]);a=p.parse_args();qualify(a.binary,a.output,a.backend,a.multiple,a.baseclock)
