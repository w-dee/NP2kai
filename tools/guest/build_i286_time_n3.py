#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build N3 using N1's unchanged licensed IPL and generated known sectors."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from build_i286_time_n1 import ROOT, sha
from n3_contract import IMAGE_SIZE, SECTORS, DATA_OFFSET, payload, crc, nonoverlap

SOURCE = ROOT / 'tests/guest/i286-time-n3/src'
IPL_SOURCE = ROOT / 'tests/guest/i286-time-n1/src/ipl.asm'
REFERENCE = SOURCE.parent / 'reference.json'


def build(output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data_sectors = [payload(s) for s in SECTORS]
    with tempfile.TemporaryDirectory(prefix='n3-build-') as tmp:
        temp = Path(tmp)
        for s, data in zip(SECTORS, data_sectors):
            (temp / f'sector{s}.bin').write_bytes(data)
        stage = temp / 'stage2.bin'
        subprocess.run(['nasm', '-f', 'bin', '-I', str(temp)+'/',
                        str(SOURCE/'stage2.asm'), '-o', str(stage)], check=True)
        stage_data = stage.read_bytes()
        if not (8 <= len(stage_data) <= 5*1024 and stage_data[:6] == b'ST2V\x01\0'
                and int.from_bytes(stage_data[6:8], 'little') == len(stage_data)):
            raise ValueError('invalid stage2 header/size or overlaps data sectors')
        sectors = (len(stage_data)+1023)//1024
        disk = [('ipl', 0, 1024), ('stage2', 1024, sectors*1024),
                ('data7', DATA_OFFSET, 1024), ('data8', DATA_OFFSET+1024, 1024)]
        memory = [('ipl', 0x1fc00, 1024), ('stage2-reserve', 0x20000, 32768),
                  ('stack', 0x28000, 4096), ('result', 0x29000, 256),
                  ('loader-status', 0x2a000, 32), ('dma7-canaries', 0x400ff, 1026),
                  ('dma8-canaries', 0x408ff, 1026)]
        nonoverlap(disk)
        nonoverlap(memory)
        boot = temp/'ipl.bin'
        subprocess.run(['nasm', '-f', 'bin', f'-DSTAGE2_SIZE={len(stage_data)}',
                        f'-DSTAGE2_SECTORS={sectors}', str(IPL_SOURCE), '-o', str(boot)], check=True)
        boot_data = boot.read_bytes()
        if len(boot_data) != 1024 or any(boot_data[o:o+2] != b'\x55\xaa' for o in (510,1022)):
            raise ValueError('bad IPL size/signatures')
        image = bytearray(IMAGE_SIZE)
        image[:1024] = boot_data
        image[1024:1024+len(stage_data)] = stage_data
        image[DATA_OFFSET:DATA_OFFSET+2048] = b''.join(data_sectors)
        output.write_bytes(image)
        return {'image': str(output), 'image_bytes': len(image), 'image_sha256': sha(image),
                'ipl_sha256': sha(boot_data), 'stage2_sha256': sha(stage_data),
                'stage2_bytes': len(stage_data), 'stage2_sectors': sectors,
                'payload_sha256': sha(b''.join(data_sectors)),
                'sector_crc32': [f'{crc(d):08x}' for d in data_sectors],
                'nasm_version': subprocess.check_output(['nasm','-v'],text=True).strip(),
                'disk_regions': disk, 'memory_regions': memory}


def check_reference(report):
    reference = json.loads(REFERENCE.read_text())
    for key, value in reference.items():
        if report.get(key) != value:
            raise ValueError(f'reference mismatch: {key}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check-reference', action='store_true')
    args = parser.parse_args()
    report = build(args.output)
    if args.check_reference:
        check_reference(report)
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
