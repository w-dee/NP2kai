#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""N3 semantic corruption tests; CRC is repaired except in the CRC test."""
import struct
import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from n3_contract import FIELDS, SECTORS, BUFFER_OFFSETS, payload, crc, nonoverlap
from verify_i286_time_n3 import verify_result, verify_image
from build_i286_time_n3 import build


def seal(data):
    struct.pack_into('<I', data, 248, crc(data[:248]))
    return bytes(data)


def set_field(data, index, name, value):
    offset, fmt = FIELDS[name]
    struct.pack_into('<'+fmt, data, 32+96*index+offset, value)


def valid_result():
    data = bytearray(256)
    struct.pack_into('<4s8H', data, 0, b'N3FD',1,256,2,2,2,0,0,96)
    for i in range(2):
        address = BUFFER_OFFSETS[i]
        values = {
            'id':i+1, 'authority':2, 'status':1, 'phase':4,
            'c':0, 'h':0, 'r':SECTORS[i], 'n':3, 'length':1024,
            'dma_initial_address':address, 'dma_initial_count':1023,
            'dma_final_address':address+1024, 'dma_final_count':65535,
            'dma_tc_status':4, 'pic_irr_pending':8, 'irq_before':i, 'irq_after':i+1,
            'slave_isr':8, 'master_isr':128, 'fdc_initial_status':128,
            'fdc_result_status':209, 'fdc_idle_status':128, 'command':0x46,
            'handler_phase':3, 'expected_crc':crc(payload(SECTORS[i])),
            'observed_crc':crc(payload(SECTORS[i])), 'first_mismatch':65535,
            'requested_address':address, 'handler_dma_address':address+1024,
            'handler_dma_count':65535, 'drive_status':0x38, 'command_bytes':9,
            'dma_page':4, 'canary_before':0x5c, 'canary_after':0xc5,
        }
        for name,value in values.items():
            set_field(data,i,name,value)
        data[64+96*i:71+96*i] = bytes((0,0,0,0,0,1,3))
    data[252] = 2
    return seal(data)


class ResultTest(unittest.TestCase):
    def test_good(self):
        self.assertEqual(verify_result(valid_result())['state'], 'PASS')

    def test_bad_magic_version(self):
        for offset in (0,4):
            with self.subTest(offset=offset):
                data = bytearray(valid_result()); data[offset] ^= 1
                with self.assertRaisesRegex(ValueError,'magic/version'):
                    verify_result(seal(data))

    def test_bad_crc(self):
        data = bytearray(valid_result()); data[248] ^= 1
        with self.assertRaisesRegex(ValueError,'CRC32'): verify_result(data)

    def test_truncated(self):
        with self.assertRaisesRegex(ValueError,'length'): verify_result(valid_result()[:-1])

    def test_semantic_corruptions(self):
        mutations = (
            ('c',1,'CHS'), ('r',8,'CHS'), ('length',1023,'length'),
            ('expected_crc',0,'payload CRC'), ('observed_crc',0,'payload CRC'),
            ('first_mismatch',1023,'exact comparison'), ('poison_survival',1,'poison'),
            ('dma_final_count',0,'DMA final'), ('dma_final_address',0x4ff,'DMA final'),
            ('dma_tc_status',0,'TC'), ('dma_status_after_read',4,'TC'),
            ('pic_irr_pending',0,'IRQ publication'), ('irq_after',0,'IRQ acceptance'),
            ('slave_after_eoi',8,'ISR/EOI'), ('handler_dma_count',1,'DMA final'),
            ('handler_phase',2,'causal'), ('status',0,'incomplete'),
            ('canary_after',0,'canaries'), ('fdc_idle_status',209,'FDC'),
        )
        for name,value,message in mutations:
            with self.subTest(name=name):
                data = bytearray(valid_result()); set_field(data,0,name,value)
                with self.assertRaisesRegex(ValueError,message): verify_result(seal(data))

    def test_early_irq_incomplete_dma(self):
        data = bytearray(valid_result())
        set_field(data,0,'irq_during_tc_poll',8)
        set_field(data,0,'early_dma_count',5)
        with self.assertRaisesRegex(ValueError,'before coherent'): verify_result(seal(data))

    def test_wrong_fdc_results(self):
        data = bytearray(valid_result()); data[64] = 0x40
        with self.assertRaisesRegex(ValueError,'FDC result'): verify_result(seal(data))

    def test_bad_aggregate(self):
        data = bytearray(valid_result()); struct.pack_into('<H',data,12,1)
        with self.assertRaisesRegex(ValueError,'aggregate'): verify_result(seal(data))

    def test_pass_with_incomplete(self):
        data = bytearray(valid_result()); struct.pack_into('<H',data,10,1)
        with self.assertRaisesRegex(ValueError,'incomplete'): verify_result(seal(data))

    def test_terminal_and_failed_case(self):
        data = bytearray(valid_result())
        set_field(data,0,'status',2)
        struct.pack_into('<3H',data,12,1,1,1)
        with self.assertRaisesRegex(ValueError,'terminal PASS'): verify_result(seal(data))
        data[252] = 3
        self.assertEqual(verify_result(seal(data))['state'],'FAIL')

    def test_layout_overlap(self):
        with self.assertRaisesRegex(ValueError,'overlapping'):
            nonoverlap([('loader',0,2048),('data',1024,1024)])

    def test_generated_image_and_corrupt_sector(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'n3.hdm'; build(p)
            image = bytearray(p.read_bytes())
            self.assertEqual(verify_image(image)['state'],'PASS')
            image[6144] ^= 1
            with self.assertRaisesRegex(ValueError,'payload'): verify_image(image)
            struct.pack_into('<H',image,1030,5121)
            with self.assertRaisesRegex(ValueError,'overlaps'): verify_image(image)

if __name__ == '__main__': unittest.main()
