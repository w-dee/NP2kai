#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent N1 result-contract and negative validation checks."""
import binascii
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_i286_time_n1 import verify_result, verify_image


def word(data,offset,value):
    struct.pack_into('<H',data,offset,value)


def seal(data):
    struct.pack_into('<I',data,248,binascii.crc32(data[:248]) & 0xffffffff)
    return bytes(data)


def good_result():
    data=bytearray(256)
    data[:4]=b'N1TM'
    word(data,4,1);word(data,6,256);word(data,8,6)
    word(data,10,6);word(data,12,6);word(data,18,24)
    for index in range(6):
        base=32+index*24
        data[base]=index+1
        data[base+1]=1 if index>=4 else 2
        data[base+2]=1
        if index>=2:
            data[base+3]=index+1
            word(data,base+8,index-1)
            data[base+21]=1
        if index>=1:
            data[base+23]=0xff if index==1 else 0xfe
    word(data,36,8190);word(data,38,8180);word(data,40,8000)
    data[56+20]=1
    data[80+20]=1
    data[104+20]=0
    word(data,104+16,0x4411);word(data,104+10,0x4422)
    data[128+20]=1
    word(data,128+16,0x5522)
    data[152+20]=1
    word(data,152+18,0x17f8)
    data[252]=2
    return seal(data)


class N1ContractTest(unittest.TestCase):
    def test_good_result(self):
        self.assertEqual(verify_result(good_result())['state'],'PASS')

    def test_corrupt_crc_rejected(self):
        data=bytearray(good_result());data[40]^=1
        with self.assertRaisesRegex(ValueError,'CRC32'):verify_result(data)

    def test_magic_and_version_rejected(self):
        for offset in (0,4):
            data=bytearray(good_result());data[offset]^=1;data=seal(data)
            with self.assertRaisesRegex(ValueError,'magic/version'):verify_result(data)

    def test_wrong_sequence_marker_rejected_even_with_valid_crc(self):
        data=bytearray(good_result());word(data,128+16,0x5511);data=seal(data)
        with self.assertRaisesRegex(ValueError,'STI marker'):verify_result(data)

    def test_hlt_preexisting_irq_rejected_even_with_valid_crc(self):
        data=bytearray(good_result());data[104+20]=1;data=seal(data)
        with self.assertRaisesRegex(ValueError,'already pending before HLT'):verify_result(data)

    def test_truncated_result_rejected(self):
        with self.assertRaisesRegex(ValueError,'length'):verify_result(good_result()[:-1])

    def test_nonterminal_state_rejected(self):
        data=bytearray(good_result());data[252]=1
        with self.assertRaisesRegex(ValueError,'not terminal'):verify_result(data)

    def test_image_short_rejected(self):
        with self.assertRaisesRegex(ValueError,'image length'):verify_image(b'')

if __name__=='__main__':unittest.main()
