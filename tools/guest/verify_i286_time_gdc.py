#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Revalidate an N4 capture against current fixture sources and explicit identity."""
import argparse
import json
from pathlib import Path
import tempfile

from build_i286_time_gdc import build, sha
from gdc_contract import PROFILES, require, verify_result
from run_i286_time_gdc import source_identity, validate_capture


def verify(output,backend,scan_class,mode=1):
    output=Path(output)
    report=json.loads((output/'report.json').read_text())
    require((report['backend'],report['scan_class'],report['mode'])==(backend,scan_class,mode),
            'requested backend/class/mode differs from report')
    with tempfile.TemporaryDirectory(prefix='n4-verify-') as td:
        current=build(Path(td)/'gdc.hdm',scan_class,mode)
    for key in ('build_id','sources','image_size','image_sha256','stage_sha256','boot_sha256'):
        require(report[key]==current[key],'stale fixture '+key)
    for name,key in [('gdc.hdm','image_sha256'),('result.bin','result_sha256'),
                     ('capture.json','capture_sha256'),('source-manifest.json','source_manifest_sha256')]:
        require(sha((output/name).read_bytes())==report[key],'artifact hash mismatch: '+name)
    require(json.loads((output/'source-manifest.json').read_text())==source_identity(),
            'stale product/runner source identity')
    result=verify_result((output/'result.bin').read_bytes(),mode=mode,scan_class=scan_class,
                         build_id=current['build_id'])
    require(result==report['result'] and report['state']==result['state'],'report/result mismatch')
    runtime=report['runtime']
    checks=validate_capture(json.loads((output/'capture.json').read_text()),result,backend=backend,
                            scan_class=scan_class,baseclock=runtime['baseclock'],multiple=runtime['multiple'])
    require(checks==report['capture_checks'],'report/capture mismatch')
    return dict(state=result['state'],backend=backend,scan_class=scan_class,records=len(result['records']))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--backend',choices=['i286','ia32'],required=True)
    p.add_argument('--scan-class',choices=PROFILES,type=int,required=True)
    p.add_argument('--mode',choices=[1,2],type=int,default=1)
    a=p.parse_args()
    print(json.dumps(verify(a.output,a.backend,a.scan_class,a.mode)))

if __name__=='__main__':
    main()
