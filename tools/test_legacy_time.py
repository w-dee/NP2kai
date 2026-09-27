#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile focused arithmetic and actual NEVENT parent/current differential tests."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / 'tests/time_domains'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', default='084f9919fbc4f659b94c3ecffdcf25380691ead7')
    parser.add_argument('--cc', default='cc')
    args = parser.parse_args()
    source = subprocess.check_output(['git', 'show', f'{args.baseline}:nevent.c'], cwd=ROOT)
    names = sorted(set(re.findall(rb'\bnevent_\w+(?=\()', source)))
    rename = [f'-D{n.decode()}=old_{n.decode()}' for n in names] + ['-Dg_nevent=old_g_nevent']
    with tempfile.TemporaryDirectory(prefix='legacy-time-') as directory:
        temp = Path(directory)
        (temp/'parent.c').write_bytes(source)
        flags = [args.cc, '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-Wno-unused-variable', '-I'+str(TEST/'stubs'), '-I'+str(ROOT)]
        def run(extra):
            subprocess.run(flags+extra, check=True, cwd=ROOT)
        run([str(TEST/'test_legacytime.c'), '-o', str(temp/'helpers')])
        subprocess.run([str(temp/'helpers')], check=True)
        run(rename+['-c', str(temp/'parent.c'), '-o', str(temp/'parent.o')])
        run(['-c', str(ROOT/'nevent.c'), '-o', str(temp/'current.o')])
        run([str(TEST/'test_nevent.c'), str(temp/'parent.o'), str(temp/'current.o'),
             '-o', str(temp/'nevent')])
        subprocess.run([str(temp/'nevent')], check=True)


if __name__ == '__main__':
    main()
