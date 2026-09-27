#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Deterministically build the standalone 1232 KiB N1 IPL floppy."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'tests/guest/i286-time-n1/src'
IMAGE_SIZE = 77 * 2 * 8 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(output: Path) -> dict:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='n1-build-') as temp:
        stage = Path(temp) / 'stage2.bin'
        ipl = Path(temp) / 'ipl.bin'
        subprocess.run(['nasm', '-f', 'bin', str(SOURCE/'stage2.asm'), '-o', str(stage)], check=True)
        payload = stage.read_bytes()
        if not (8 <= len(payload) <= 32768 and payload[:6] == b'ST2V\x01\x00'
                and int.from_bytes(payload[6:8], 'little') == len(payload)):
            raise ValueError('stage2 header/size invalid')
        sectors = (len(payload) + 1023) // 1024
        subprocess.run(['nasm', '-f', 'bin', f'-DSTAGE2_SIZE={len(payload)}',
                        f'-DSTAGE2_SECTORS={sectors}', str(SOURCE/'ipl.asm'), '-o', str(ipl)], check=True)
        boot = ipl.read_bytes()
        if len(boot) != 1024 or boot[510:512] != b'\x55\xaa' or boot[1022:1024] != b'\x55\xaa':
            raise ValueError('IPL signatures/size invalid')
        data = boot + payload.ljust(sectors*1024, b'\0')
        data += bytes(IMAGE_SIZE-len(data))
        if len(data) != IMAGE_SIZE:
            raise ValueError('image overflow')
        output.write_bytes(data)
        return {'image': str(output), 'image_bytes': len(data), 'image_sha256': sha(data),
                'ipl_sha256': sha(boot), 'stage2_sha256': sha(payload),
                'stage2_bytes': len(payload), 'stage2_sectors': sectors,
                'nasm_version': subprocess.check_output(['nasm', '-v'], text=True).strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check-reference', action='store_true')
    args = parser.parse_args()
    report = build(args.output)
    if args.check_reference:
        reference = json.loads((ROOT/'tests/guest/i286-time-n1/reference.json').read_text())
        for key in ('image_sha256','ipl_sha256','stage2_sha256','stage2_bytes','stage2_sectors','nasm_version'):
            if report[key] != reference[key]:
                raise ValueError(f'reference mismatch: {key}: {report[key]} != {reference[key]}')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
