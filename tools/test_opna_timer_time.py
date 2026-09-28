#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""UBSan rational arithmetic and bounded-work implementation check."""
import argparse,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 binary=out/'math'
 subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ROOT),str(ROOT/'tests/time_domains/test_opna_timer_math.c'),str(ROOT/'opna_timer_time.c'),'-o',str(binary)],check=True)
 result=subprocess.check_output([str(binary)],text=True);(out/'result.txt').write_text(result);print(result,end='')
 code=(ROOT/'opna_timer_time.c').read_text()
 assert code.count('for (i = 0; i < 2; ++i)')==2 and 'while (' not in code
 for name in ['opna_timer_time.c','opna_timer_machine.c']:
  text=(ROOT/name).read_text()
  for forbidden in ['pccore.multiple','pccore.realclock','legacy_cpu','CPU_CLOCK','sound_sync','opngen_getpcm']:
   assert forbidden not in text,(name,forbidden)
 (out/'report.json').write_text(json.dumps(dict(result='PASS',partition_cases=40000,authority='integer arithmetic and structural bounded-work; binding/CPU qualification separate'),indent=2)+'\n')
if __name__=='__main__':main()
