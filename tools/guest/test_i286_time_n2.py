#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N2 result-contract acceptance and corruption rejection checks."""
import binascii
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_i286_time_n2 import verify_result, verify_image


def word(data,offset,value):struct.pack_into('<H',data,offset,value)


def seal(data):
    struct.pack_into('<I',data,248,binascii.crc32(data[:248])&0xffffffff)
    return bytes(data)


def good_result():
    data=bytearray(256)
    data[:4]=b'N2RP'
    for offset,value in ((4,1),(6,256),(8,3),(10,3),(12,3),(18,32)):
        word(data,offset,value)
    rows=(
        (2,(0x1000,0,1,1,0,1,2)),
        (1,(0x8000,12317,20707,20707,210,210,0x0294,1,0x100,0x100)),
        (1,(0,0x8100,0x8100,49152,49152,0xffff,0x5c,0xc5,1)),
    )
    for index,(authority,fields) in enumerate(rows):
        base=32+32*index
        data[base:base+3]=bytes((index+1,authority,1))
        for field,value in enumerate(fields):word(data,base+4+2*field,value)
    data[252]=2
    return seal(data)


class N2ContractTest(unittest.TestCase):
    def test_good_result(self):self.assertEqual(verify_result(good_result())['state'],'PASS')

    def test_bad_magic_and_version(self):
        for offset in (0,4):
            data=bytearray(good_result());data[offset]^=1
            with self.assertRaisesRegex(ValueError,'magic/version'):verify_result(seal(data))

    def test_bad_crc(self):
        data=bytearray(good_result());data[40]^=1
        with self.assertRaisesRegex(ValueError,'CRC32'):verify_result(data)

    def test_truncated_result(self):
        with self.assertRaisesRegex(ValueError,'length'):verify_result(good_result()[:-1])

    def test_impossible_count_progression(self):
        data=bytearray(good_result());word(data,64+6,0x8000)
        with self.assertRaisesRegex(ValueError,'impossible count'):verify_result(seal(data))

    def test_final_data_mismatch(self):
        data=bytearray(good_result());word(data,96+12,49153)
        with self.assertRaisesRegex(ValueError,'final data/state'):verify_result(seal(data))

    def test_wrong_pattern_even_when_both_sums_agree(self):
        data=bytearray(good_result());word(data,96+10,0);word(data,96+12,0)
        with self.assertRaisesRegex(ValueError,'final data/state'):verify_result(seal(data))

    def test_wrong_restart_ip(self):
        data=bytearray(good_result());word(data,64+12,211)
        with self.assertRaisesRegex(ValueError,'IP/flags'):verify_result(seal(data))

    def test_inconsistent_aggregate(self):
        data=bytearray(good_result());word(data,12,2)
        with self.assertRaisesRegex(ValueError,'aggregate'):verify_result(seal(data))

    def test_terminal_with_incomplete_record(self):
        data=bytearray(good_result());data[96+2]=0
        with self.assertRaisesRegex(ValueError,'identity/class/status'):verify_result(seal(data))

    def test_nonterminal_state(self):
        data=bytearray(good_result());data[252]=1
        with self.assertRaisesRegex(ValueError,'not terminal'):verify_result(data)

    def test_invalid_image_length(self):
        with self.assertRaisesRegex(ValueError,'image length'):verify_image(b'')

if __name__=='__main__':unittest.main()
