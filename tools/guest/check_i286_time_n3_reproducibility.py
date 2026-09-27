#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Two independent clean N3 builds, full byte equality and pinned hashes."""
import json
from pathlib import Path
import tempfile
from build_i286_time_n3 import build, check_reference
from verify_i286_time_n3 import verify_image


def main():
    with tempfile.TemporaryDirectory(prefix='n3-a-') as a, tempfile.TemporaryDirectory(prefix='n3-b-') as b:
        paths = [Path(a)/'n3.hdm', Path(b)/'n3.hdm']
        reports = [build(path) for path in paths]
        for path, report in zip(paths,reports):
            check_reference(report)
            verify_image(path.read_bytes())
        if paths[0].read_bytes() != paths[1].read_bytes():
            raise ValueError('independent images differ')
        print(json.dumps({'state':'PASS','byte_equal':True,
                          'first_sha256':reports[0]['image_sha256'],
                          'second_sha256':reports[1]['image_sha256']},indent=2))

if __name__ == '__main__':
    main()
