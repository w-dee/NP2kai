#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise actual private SDL pacing with deterministic host-clock wrappers."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="np2-sdl-pacing-") as directory:
    binary = Path(directory) / "test"
    subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=undefined", "-DNP2_GDC_MACHINE_TIME", "-I", str(ROOT),
                    str(ROOT / "sdl/cpupacing.c"),
                    str(ROOT / "tests/time_domains/test_sdl_cpupacing.c"),
                    "-Wl,--wrap=clock_gettime", "-Wl,--wrap=clock_nanosleep",
                    "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
