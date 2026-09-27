#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate N2's 256-byte REP result contract or 1232 KiB raw image."""
from __future__ import annotations
import argparse
import binascii
import json
from pathlib import Path
import struct
from verify_i286_time_n1 import verify_image

NAMES=('IRQ_DURING_REP','RESTART_STATE','FINAL_INTEGRITY')


def word(data:bytes,offset:int) -> int:
    return struct.unpack_from('<H',data,offset)[0]


def verify_result(data:bytes) -> dict:
    if len(data)!=256:raise ValueError('result length')
    if data[:4]!=b'N2RP' or word(data,4)!=1 or word(data,6)!=256:
        raise ValueError('result magic/version/size')
    if word(data,8)!=3 or word(data,18)!=32:raise ValueError('case count/record size')
    crc=binascii.crc32(data[:248])&0xffffffff
    if struct.unpack_from('<I',data,248)[0]!=crc:raise ValueError('result CRC32')
    if data[252] not in (2,3):raise ValueError('result not terminal')
    if word(data,10)!=3 or word(data,12)+word(data,14)!=3:
        raise ValueError('aggregate incomplete')
    records=[]
    for index,name in enumerate(NAMES):
        row=data[32+32*index:64+32*index]
        if row[0]!=index+1 or row[1]!=(2 if index==0 else 1) or row[2] not in (1,2):
            raise ValueError(f'{name}: identity/class/status')
        records.append({'id':index+1,'name':name,'class':row[1],'status':row[2],
                        'fields':[word(row,i) for i in range(4,24,2)]})
    a,b,c=[r['fields'] for r in records]
    if records[0]['status']==1:
        if not (a[0]==0x1000 and a[1]==0 and a[2]==1 and (a[3]&1)
                and not(a[4]&1) and a[5]==1 and a[6]==2):
            raise ValueError('IRQ_DURING_REP: publication/acceptance/completion markers')
    if records[1]['status']==1:
        count,remaining,si,di,saved_ip,rep_ip,flags,irq_count,start_si,start_di=b
        progress=count-remaining
        if not (count==0x8000 and 0<remaining<count and progress>0
                and si==start_si+progress and di==start_di+progress
                and start_si==start_di==0x100 and saved_ip==rep_ip!=0
                and flags&0x0200 and not(flags&0x0400) and irq_count==1):
            raise ValueError('RESTART_STATE: impossible count/pointer/IP/flags')
    if records[2]['status']==1:
        final_cx,final_si,final_di,src_sum,dst_sum,mismatch,before,after,irq_count,*_=c
        if not (final_cx==0 and final_si==final_di==0x8100 and src_sum==dst_sum==0xc000
                and mismatch==0xffff and before==0x5c and after==0xc5 and irq_count==1):
            raise ValueError('FINAL_INTEGRITY: final data/state mismatch')
    failures=[r['id'] for r in records if r['status']!=1]
    if word(data,12)!=3-len(failures) or word(data,14)!=len(failures):
        raise ValueError('aggregate/status mismatch')
    if word(data,16)!=(failures[0] if failures else 0):
        raise ValueError('first failed ID')
    if (data[252]==2)!=(not failures):raise ValueError('terminal state mismatch')
    return {'state':'PASS' if not failures else 'FAIL','records':records,
            'failed':failures,'crc32':f'{crc:08x}'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('path',type=Path)
    parser.add_argument('--kind',choices=('image','result'),required=True)
    args=parser.parse_args()
    report=verify_image(args.path.read_bytes()) if args.kind=='image' else verify_result(args.path.read_bytes())
    print(json.dumps(report,indent=2))
    if report.get('state')=='FAIL':raise SystemExit(1)

if __name__=='__main__':main()
