#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build original deterministic 1232 KiB ARTIC raw floppy."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from artic_contract import expected_samples

ROOT = Path(__file__).resolve().parents[2]


def build(output, mode=2):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='artic-ipl-') as temp:
        tmp = Path(temp)
        (tmp/'samples.inc').write_text(''.join(
            f"dw {r['case']}, {r['port']}, {r['expected']}\n" for r in expected_samples()))
        subprocess.run(['nasm', '-f', 'bin', '-I'+str(tmp)+'/', f'-DRUN_MODE={mode}',
                        str(ROOT/'tests/guest/i286-time-artic/src/ipl.asm'),
                        '-o', str(tmp/'ipl.bin')], check=True)
        boot = (tmp/'ipl.bin').read_bytes()
    assert len(boot) == 1024 and boot[510:512] == boot[1022:1024] == b'\x55\xaa'
    image = boot + bytes(77*2*8*1024 - len(boot))
    output.write_bytes(image)
    return dict(image_bytes=len(image), image_sha256=hashlib.sha256(image).hexdigest(),
                mode=mode, nasm=subprocess.check_output(['nasm', '-v'], text=True).strip())


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--mode', type=int, choices=[1,2], default=2)
    a = p.parse_args()
    print(json.dumps(build(a.output,a.mode),indent=2))
