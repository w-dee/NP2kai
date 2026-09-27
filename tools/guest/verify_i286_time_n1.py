#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the N1 IPL image or an extracted 256-byte guest result block."""
from __future__ import annotations
import argparse
import binascii
import json
from pathlib import Path
import struct

IDS = ('PIT_COUNT_LATCH', 'PIC_MASK', 'PIT_IRQ_EOI', 'HLT_WAKE', 'STI_SHADOW', 'MOV_SS_SHADOW')


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from('<H', data, offset)[0]


def verify_image(data: bytes) -> dict:
    if len(data) != 1261568:
        raise ValueError('image length')
    if data[510:512] != b'\x55\xaa' or data[1022:1024] != b'\x55\xaa':
        raise ValueError('IPL signature')
    if data[1024:1030] != b'ST2V\x01\x00':
        raise ValueError('stage2 header')
    size = u16(data, 1030)
    if not 8 <= size <= 32768:
        raise ValueError('stage2 size')
    sectors = (size+1023)//1024
    if any(data[1024+size:1024+sectors*1024]) or any(data[1024+sectors*1024:]):
        raise ValueError('nonzero image padding')
    return {'stage2_bytes': size, 'stage2_sectors': sectors}


def verify_result(data: bytes) -> dict:
    if len(data) != 256:
        raise ValueError('result length')
    if data[:4] != b'N1TM' or u16(data,4) != 1 or u16(data,6) != 256:
        raise ValueError('result magic/version/size')
    if u16(data,8) != 6 or u16(data,18) != 24:
        raise ValueError('result case count/record size')
    crc = binascii.crc32(data[:248]) & 0xffffffff
    if struct.unpack_from('<I',data,248)[0] != crc:
        raise ValueError('result CRC32')
    if data[252] not in (2,3):
        raise ValueError('result not terminal')
    if u16(data,10) != 6 or u16(data,12)+u16(data,14) != 6:
        raise ValueError('result aggregate counts')
    records = []
    for index, name in enumerate(IDS):
        base = 32+24*index
        row = data[base:base+24]
        rec = {'id': index+1, 'name': name, 'class':row[1], 'status':row[2],
               'phase':row[3], 'count_a':u16(row,4), 'count_b':u16(row,6),
               'handler_count':u16(row,8), 'post_marker':u16(row,10),
               'saved_ip':u16(row,14), 'irq_marker':u16(row,16),
               'entry_sp':u16(row,18), 'irr':row[20], 'isr_entry':row[21],
               'isr_after':row[22], 'pic_mask':row[23]}
        if row[0] != index+1 or row[1] != (1 if index >= 4 else 2) or row[2] not in (1,2):
            raise ValueError(f'{name}: ID/class/status')
        if index == 0:
            rec['count_after'] = rec.pop('handler_count')
        if index == 0 and row[2] == 1:
            if not (0 < rec['count_a'] <= 0x2000 and 0 < rec['count_b'] <= rec['count_a']
                    and 0 < rec['count_after'] < rec['count_b']):
                raise ValueError(f'{name}: count/latch sequence')
        if index == 1 and row[2] == 1 and (rec['handler_count'] != 0 or not rec['irr'] & 1):
            raise ValueError(f'{name}: masked IRQ publication/acceptance')
        if index >= 1 and rec['pic_mask'] != (0xff if index == 1 else 0xfe):
            raise ValueError(f'{name}: PIC mask record')
        if index >= 2 and row[2] == 1:
            if rec['phase'] != index+1 or rec['handler_count'] != index-1:
                raise ValueError(f'{name}: phase/handler count')
            if index == 3 and rec['irr'] & 1:
                raise ValueError(f'{name}: IRQ already pending before HLT')
            if index in (2,4,5) and not (rec['irr'] & 1):
                raise ValueError(f'{name}: no pending request')
            if not rec['isr_entry'] & 1 or rec['isr_after'] & 1:
                raise ValueError(f'{name}: ISR/EOI')
            if index == 3 and (rec['irq_marker'] != 0x4411 or rec['post_marker'] != 0x4422):
                raise ValueError(f'{name}: wake markers')
            if index == 4 and rec['irq_marker'] != 0x5522:
                raise ValueError(f'{name}: STI marker')
            if index == 5 and rec['entry_sp'] != 0x17f8:
                raise ValueError(f'{name}: MOV SS stack')
        records.append(rec)
    failures = [r['name'] for r in records if r['status'] != 1]
    if u16(data,14) != len(failures) or u16(data,12) != 6-len(failures):
        raise ValueError('status/aggregate mismatch')
    if bool(failures) != (data[252] == 3):
        raise ValueError('terminal state/record mismatch')
    if u16(data,16) != (next(r['id'] for r in records if r['name']==failures[0]) if failures else 0):
        raise ValueError('first failure ID')
    return {'state': 'PASS' if not failures else 'FAIL', 'records':records,
            'failed':failures, 'crc32':f'{crc:08x}'}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('path',type=Path)
    parser.add_argument('--kind',choices=('image','result'),required=True)
    args=parser.parse_args()
    report=verify_image(args.path.read_bytes()) if args.kind=='image' else verify_result(args.path.read_bytes())
    print(json.dumps(report,indent=2))
    if report.get('state')=='FAIL':
        raise SystemExit(1)

if __name__=='__main__':
    main()
