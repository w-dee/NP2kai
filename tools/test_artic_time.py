#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Strict/UBSan tests of the production ARTIC arithmetic and I/O binding."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def isolation():
    allowed = {'io/artic.c', 'artic_time.c', 'artic_time.h',
               'artic_time_fake.c', 'artic_time_posix.c'}
    paths = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard',
                                    '*.c', '*.h', '*.cpp'], cwd=ROOT, text=True).splitlines()
    for name in set(paths):
        if name.startswith('tests/') or name in allowed:
            continue
        text = (ROOT/name).read_text(errors='replace')
        assert not re.search(r'\bartic_(?:machine_|time_|fake_)', text), name
    for name in ['artic_time.c', 'artic_time.h', 'artic_time_fake.c', 'artic_time_posix.c']:
        text = (ROOT/name).read_text()
        includes = re.findall(r'#include [<"]([^>"]+)', text)
        assert set(includes) <= {'artic_time.h', 'stdint.h', 'string.h', 'time.h'}, name
        assert not re.search(r'CPU_CLOCK|legacy_cpu|np2_time_shadow|nevent_|pic_|pccore\.', text), name
    print('PASS machine-time dataflow: ARTIC is the only guest consumer')


def main():
    with tempfile.TemporaryDirectory(prefix='np2-artic-') as temp:
        flags = [os.environ.get('CC', 'cc'), '-std=c99', '-O2', '-g', '-Wall',
                 '-Wextra', '-Werror', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                 '-I'+str(ROOT/'tests/time_domains/artic_stubs'), '-I'+str(ROOT)]
        for case, sources, defines in [
            ('math', ['test_artic_time.c'], []),
            ('live', ['test_artic_live.c'], []),
            ('binding-on', ['test_artic_binding.c'], ['-DNP2_ARTIC_MACHINE_TIME']),
            ('binding-off', ['test_artic_binding.c'], [])]:
            output = str(Path(temp)/case)
            inputs = [str(ROOT/'tests/time_domains'/s) for s in sources]
            if case != 'binding-off':
                provider = 'artic_time_posix.c' if case == 'live' else 'artic_time_fake.c'
                inputs += [str(ROOT/'artic_time.c'), str(ROOT/provider)]
            subprocess.run(flags+defines+inputs+['-o', output], check=True)
            subprocess.run([output], check=True)
    isolation()


if __name__ == '__main__':
    main()
