#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic parser unit tests; these data are NEVER emulator qualification."""
import json
from pathlib import Path
import struct
import unittest
import zlib

from gdc_contract import CASES, HEADER, RECORD, SIZE, geometry, parse_result, verify_result, reference_phase, reference_points
from run_i286_time_gdc import validate_capture

ID='0011223344556677'


def put(b,offset,value):
    struct.pack_into('<H',b,offset,value)


def crc(b):
    struct.pack_into('<I',b,4088,zlib.crc32(b[:4088]))
    return b


def synthetic(mode=1,scan_class=24):
    b=bytearray(SIZE)
    b[:4]=b'N4GD'
    for off,value in {4:1,6:SIZE,8:RECORD,10:28,12:mode,14:scan_class,24:0x201c,
                      26:28,28:scan_class,32:32768,36:2,44:28,4094:2}.items():
        put(b,off,value)
    b[16:24]=bytes.fromhex(ID)
    b[40:44]=b[4084:4088]=bytes.fromhex('3cc3a55a')
    for case,spec in CASES.items():
        o=HEADER+(case-1)*RECORD
        for off,value in {0:case,2:case,4:scan_class+(100 if case==27 else 0),8:7,
                          10:0x2000+case,14:0xffff}.items():put(b,o+off,value)
        b[o+6]=spec['category'];b[o+7]=spec['verdict']
        b[o+12:o+14]=b'\x84\x84'
        b[o+24:o+26]=b'\x04\x04'
        b[o+48:o+56],b[o+56:o+64]=geometry(scan_class,case==27)
        b[o+64:o+68]=bytes([15,15,int(scan_class==31),0])
        b[o+72:o+76]=bytes.fromhex('3cc3a55a')
        if case>=16:put(b,o+32,32768)
        if case>=20:put(b,o+26,1)
        if case>=23:put(b,o+26,2)
        if case==18:b[o+20]=4;b[o+22]=255
        if case in (20,21,23):b[o+21]=4;b[o+22]=251
        if case>=22:put(b,o+68,1)
        if case>=24:put(b,o+68,2)
        if case==23:
            for off,v in {28:0x1111,30:0x2222,38:0x1234,40:0x1234,42:0x2000,44:0x200}.items():put(b,o+off,v)
            b[o+36]=4
    return crc(b)


class Contract(unittest.TestCase):
    def check(self,b,mode=1,scan_class=24,build_id=ID):
        return verify_result(b,mode=mode,scan_class=scan_class,build_id=build_id)

    def test_synthetic_valid_all_profiles(self):
        for c in (15,24,31):
            self.assertEqual(self.check(synthetic(scan_class=c),scan_class=c)['state'],
                             'LEGACY_COMPATIBILITY_PROFILE_CAPTURED')

    def test_truncation_extension(self):
        b=synthetic()
        for length in (0,4,127,128,2368,4088,4094,4095):
            with self.subTest(length=length),self.assertRaises(ValueError):self.check(b[:length])
        with self.assertRaises(ValueError):self.check(b+b'\0')

    def test_every_single_byte_corruption(self):
        original=synthetic()
        for i in range(SIZE):
            b=original.copy();b[i]^=1
            with self.subTest(offset=i),self.assertRaises(ValueError):self.check(b)

    def test_rechecks_semantics_with_repaired_crc(self):
        # Includes guards/reserved/identity/decoded fields/sequence/geometry and
        # each positive IRQ/HLT/CPU/FIFO assertion; valid CRC is not sufficient.
        offsets=[0,4,6,8,10,12,14,16,24,26,28,30,32,36,38,40,44,46,4084,4092,4094]
        offsets += [HEADER+i for i in (0,2,4,6,7,8,10,14,16,17,18,19,23,24,25,48,56,64,66,67,70,71,72,76)]
        offsets += [HEADER+28*RECORD]
        for case,field in [(16,32),(18,20),(18,22),(18,26),(19,20),(19,26),
                           (20,26),(20,21),(20,22),(21,26),(21,20),(21,21),
                           (22,21),(22,37),(22,68),(23,26),(23,28),(23,30),
                           (23,38),(23,42),(23,44),(23,36),(24,21),(24,68),(26,24),(26,25)]:
            offsets.append(HEADER+(case-1)*RECORD+field)
        for off in offsets:
            b=synthetic()
            # Flip the actual IRQ/IF/FIFO bit, not an irrelevant other line.
            mask=1
            record=(off-HEADER)//RECORD+1;field=(off-HEADER)%RECORD
            if record>=18 and field in (20,21,22,24,25,36,37):mask=4
            if record==23 and field==44:off+=1;mask=2
            b[off]^=mask
            with self.subTest(offset=off),self.assertRaises(ValueError):self.check(crc(b))

    def test_stale_build_and_wrong_profile(self):
        for kwargs in (dict(build_id='ffeeddccbbaa9988'),dict(scan_class=15),dict(mode=2)):
            with self.assertRaises(ValueError):self.check(synthetic(),**kwargs)

    def test_future_never_passes_synthetic_valid_data(self):
        b=synthetic(mode=2)
        self.assertEqual(len(parse_result(b,mode=2,scan_class=24,build_id=ID)),28)
        with self.assertRaisesRegex(ValueError,'NOT_EXECUTABLE_UNTIL_MACHINE_TIME_GDC'):
            self.check(b,mode=2)

    def test_future_inventory_and_reference_boundaries(self):
        root=Path(__file__).resolve().parents[2]
        plan=json.loads((root/'tests/guest/i286-time-gdc/future-cases.json').read_text())
        self.assertFalse(plan['product_qualification_executed'])
        self.assertEqual([v['case'] for v in plan['cases']],list(CASES))
        for profile in plan['profiles']:
            c,base=profile['scan_class'],profile['B_ref']
            points=reference_points(c,base)
            self.assertEqual(points,profile['selected_points'])
            for p in points:
                q=p['reference_tick'];ns=p['first_ns_on_tick']
                self.assertEqual(ns*(5*base)//1000000000,q)
                self.assertEqual(p['expected'],reference_phase(c,base,q))
            self.assertEqual([p['expected']['hblank'] for p in points[1:7]],[0,0,1,0,1,0])
            self.assertEqual([p['expected']['vsync'] for p in points[7:11]],[0,1,1,0])
            self.assertEqual(points[14]['expected'],points[15]['expected'])

    def test_missing_host_evidence(self):
        result=self.check(synthetic())
        for capture in (dict(errors=['failed'],trace=[],reads=[]),dict(errors=[],trace=[],reads=[])):
            with self.assertRaises(ValueError):
                validate_capture(capture,result,backend='i286',scan_class=24,baseclock=2457600,multiple=5)

if __name__=='__main__':
    unittest.main()
