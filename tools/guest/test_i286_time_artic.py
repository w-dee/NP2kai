#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import struct
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from artic_contract import RESULT_SIZE, expected_samples, verify_result
from build_i286_time_artic import build


def synthetic(mode=2):
    """Validator input only; never substitute this for collected guest RAM."""
    w=[0]*272
    w[:8]=[0x5241,0x4354,1,RESULT_SIZE,mode,20,1,0x80]
    for i,r in enumerate(expected_samples()):
        j=16+i*12
        w[j:j+7]=[r['case'],i+1,r['port'],r['expected'],r['expected'],8192,1 if mode==2 else 2]
    w[269]=0xa55a;w[270]=sum(w[:270])&65535;w[271]=2
    return w


class Validator(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(verify_result(struct.pack('<272H',*synthetic()),2)['state'],'PASS')
    def test_legacy_not_hardware_pass(self):
        w=synthetic(1);w[19]=123;w[270]=sum(w[:270])&65535
        self.assertEqual(verify_result(struct.pack('<272H',*w),1)['state'],'LEGACY_OBSERVATIONS_COMPLETE')
    def test_corrupt_byte(self):
        raw=bytearray(struct.pack('<272H',*synthetic()));raw[40]^=1
        with self.assertRaises(ValueError):verify_result(bytes(raw),2)
    def test_semantic_mismatch_even_with_checksum(self):
        for index in (4,6,16,17,18,19,20,21,22,23,269,271):
            w=synthetic();w[index]^=1;w[270]=sum(w[:270])&65535
            with self.subTest(index=index),self.assertRaises(ValueError):verify_result(struct.pack('<272H',*w),2)
    def test_truncated(self):
        with self.assertRaises(ValueError):verify_result(bytes(32),2)
    def test_reproducible_images(self):
        with tempfile.TemporaryDirectory() as d:
            a=build(Path(d)/'a.hdm');b=build(Path(d)/'b.hdm')
            self.assertEqual(a,b)


if __name__=='__main__':unittest.main()
