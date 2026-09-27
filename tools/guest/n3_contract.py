# SPDX-License-Identifier: MIT
"""Shared N3 layout and project-authored known-sector data contract."""
import binascii
import struct

IMAGE_SIZE = 77 * 2 * 8 * 1024
SECTORS = (7, 8)
BUFFER_OFFSETS = (0x100, 0x900)
DATA_OFFSET = 6 * 1024
RECORD_SIZE = 96
FIELDS = {
    'id': (0, 'B'), 'authority': (1, 'B'), 'status': (2, 'B'), 'phase': (3, 'B'),
    'c': (4, 'B'), 'h': (5, 'B'), 'r': (6, 'B'), 'n': (7, 'B'),
    'length': (8, 'H'), 'dma_initial_address': (10, 'H'), 'dma_initial_count': (12, 'H'),
    'dma_final_address': (14, 'H'), 'dma_final_count': (16, 'H'),
    'dma_tc_status': (18, 'B'), 'dma_status_after_read': (19, 'B'),
    'pic_irr_before': (20, 'B'), 'pic_irr_pending': (21, 'B'),
    'irq_before': (22, 'B'), 'irq_after': (23, 'B'),
    'slave_isr': (24, 'B'), 'master_isr': (25, 'B'),
    'slave_after_eoi': (26, 'B'), 'master_after_eoi': (27, 'B'),
    'fdc_initial_status': (28, 'B'), 'fdc_result_status': (29, 'B'),
    'fdc_idle_status': (30, 'B'), 'command': (31, 'B'),
    'handler_phase': (39, 'B'), 'expected_crc': (40, 'I'), 'observed_crc': (44, 'I'),
    'first_mismatch': (48, 'H'), 'poison_survival': (50, 'H'),
    'requested_address': (52, 'H'), 'handler_dma_address': (54, 'H'),
    'handler_dma_count': (56, 'H'), 'drive_status': (58, 'B'),
    'command_bytes': (59, 'B'), 'dma_page': (64, 'B'),
    'canary_before': (65, 'B'), 'canary_after': (66, 'B'), 'dma_status_before': (67, 'B'),
    'irq_during_tc_poll': (68, 'B'), 'early_dma_address': (70, 'H'), 'early_dma_count': (72, 'H'),
}


def payload(sector):
    if sector not in SECTORS:
        raise ValueError('unsupported N3 sector')
    data = bytearray(((i * 73) ^ ((i >> 8) * 29) ^ (sector * 17)) & 255 for i in range(1024))
    struct.pack_into('<4sBBBBHH', data, 0, b'N3FD', 1, 0, 0, sector, 1024, sector ^ 0xa55a)
    return bytes(data)


def crc(data):
    return binascii.crc32(data) & 0xffffffff


def nonoverlap(regions):
    for name, start, size in regions:
        if start < 0 or size <= 0:
            raise ValueError(f'invalid region: {name}')
    ordered = sorted(regions, key=lambda r: r[1])
    for left, right in zip(ordered, ordered[1:]):
        if left[1] + left[2] > right[1]:
            raise ValueError(f'overlapping regions: {left[0]} / {right[0]}')
