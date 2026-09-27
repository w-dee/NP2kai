#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N3 direct FDC/DMA image and semantic result validator."""
import argparse
import json
from pathlib import Path
import struct
from n3_contract import IMAGE_SIZE, DATA_OFFSET, SECTORS, BUFFER_OFFSETS, FIELDS, payload, crc


def verify_image(data):
    if len(data) != IMAGE_SIZE:
        raise ValueError('image length')
    if any(data[o:o+2] != b'\x55\xaa' for o in (510,1022)):
        raise ValueError('IPL signature')
    if data[1024:1030] != b'ST2V\x01\0':
        raise ValueError('stage2 header')
    size = int.from_bytes(data[1030:1032], 'little')
    if not 8 <= size <= 5120:
        raise ValueError('stage2 overlaps known-data sectors')
    if any(data[1024+size:DATA_OFFSET]) or any(data[8192:]):
        raise ValueError('image padding')
    for sector in SECTORS:
        if data[(sector-1)*1024:sector*1024] != payload(sector):
            raise ValueError('known-sector payload mismatch')
    return {'state': 'PASS', 'stage2_bytes': size, 'data_sectors': list(SECTORS)}


def verify_record(r, index):
    sector, address = SECTORS[index], BUFFER_OFFSETS[index]
    def require(condition, reason):
        if not condition:
            raise ValueError(f'case {index+1}: {reason}')
    require((r['c'],r['h'],r['r'],r['n'],r['length'],r['command'],r['command_bytes'])
            == (0,0,sector,3,1024,0x46,9), 'requested CHS/command/length')
    require(r['phase'] == 4 and r['handler_phase'] == 3, 'causal phases')
    require((r['requested_address'],r['dma_page'],r['dma_initial_address'],r['dma_initial_count'])
            == (address,4,address,1023), 'DMA initial programming')
    require((r['dma_final_address'],r['dma_final_count'],r['handler_dma_address'],r['handler_dma_count'])
            == (address+1024,0xffff,address+1024,0xffff), 'DMA final address/count')
    if r['irq_during_tc_poll'] & 8:
        require((r['early_dma_address'], r['early_dma_count']) == (address+1024, 0xffff),
                'IRQ observed before coherent DMA completion')
    require(not (r['dma_status_before'] & 4) and (r['dma_tc_status'] & 4)
            and not (r['dma_status_after_read'] & 4), 'TC assertion/read-clear')
    require(not (r['pic_irr_before'] & 8) and (r['pic_irr_pending'] & 8), 'IRQ publication')
    require((r['irq_before'],r['irq_after']) == (index,index+1), 'IRQ acceptance count')
    require(r['slave_isr'] & 8 and r['master_isr'] & 128
            and not(r['slave_after_eoi'] & 8) and not(r['master_after_eoi'] & 128), 'PIC ISR/EOI')
    require(r['drive_status'] & 32 and r['fdc_initial_status'] & 0xc0 == 0x80
            and r['fdc_result_status'] & 0xf0 == 0xd0 and r['fdc_idle_status'] == 0x80,
            'FDC ready/completion/idle')
    require(r['result_bytes'] == [0,0,0,0,0,1,3], 'FDC result bytes (legacy TC CHRN)')
    require(r['expected_crc'] == r['observed_crc'] == crc(payload(sector)), 'payload CRC')
    require(r['first_mismatch'] == 0xffff and r['poison_survival'] == 0, 'exact comparison/poison')
    require((r['canary_before'],r['canary_after']) == (0x5c,0xc5), 'buffer canaries')


def verify_result(data):
    if len(data) != 256:
        raise ValueError('result length')
    u16 = lambda o: struct.unpack_from('<H',data,o)[0]
    if data[:4] != b'N3FD' or u16(4) != 1 or u16(6) != 256:
        raise ValueError('result magic/version/size')
    if u16(8) != 2 or u16(18) != 96:
        raise ValueError('case count/record size')
    if struct.unpack_from('<I',data,248)[0] != crc(data[:248]):
        raise ValueError('result CRC32')
    if data[252] not in (2,3):
        raise ValueError('result not terminal')
    if u16(10) != 2 or u16(12)+u16(14) != 2:
        raise ValueError('aggregate incomplete')
    records = []
    for index in range(2):
        row = data[32+96*index:128+96*index]
        r = {name: struct.unpack_from('<'+fmt,row,offset)[0] for name,(offset,fmt) in FIELDS.items()}
        r['result_bytes'] = list(row[32:39])
        r['name'] = ('DIRECT_READ_S7','FOLLOWUP_READ_S8')[index]
        if r['id'] != index+1 or r['authority'] != 2 or r['status'] not in (1,2):
            raise ValueError('record identity/authority/incomplete status')
        if r['status'] == 1:
            verify_record(r,index)
        records.append(r)
    failed = [r['id'] for r in records if r['status'] == 2]
    if (u16(12),u16(14),u16(16)) != (2-len(failed),len(failed),failed[0] if failed else 0):
        raise ValueError('aggregate counters/first failure')
    if (data[252] == 2) != (not failed):
        raise ValueError('terminal PASS with failed cases')
    return {'state': 'FAIL' if failed else 'PASS', 'records': records,
            'failed': failed, 'crc32': f'{crc(data[:248]):08x}'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path',type=Path)
    parser.add_argument('--kind',choices=('image','result'),required=True)
    args = parser.parse_args()
    report = (verify_image if args.kind == 'image' else verify_result)(args.path.read_bytes())
    print(json.dumps(report,indent=2))
    if report['state'] != 'PASS':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
