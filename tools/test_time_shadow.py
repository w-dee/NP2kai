#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the actual accounting/clock sources, exercise deterministic inputs."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="np2-shadow-") as directory:
        binary = Path(directory) / "shadow-test"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-O2", "-g",
                        "-Wall", "-Wextra", "-Werror", "-fsanitize=undefined",
                        "-fno-sanitize-recover=all", "-I", str(ROOT),
                        str(ROOT / "timeshadow_account.c"),
                        str(ROOT / "timeshadow_posix.c"),
                        str(ROOT / "tests/time_domains/test_timeshadow.c"),
                        "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        runtime = Path(directory) / "runtime-test"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-O2", "-g",
                        "-Wall", "-Wextra", "-Werror", "-fsanitize=undefined",
                        "-fno-sanitize-recover=all", "-DNP2_TIME_SHADOW",
                        "-I", str(ROOT / "tests/time_domains/stubs"),
                        "-I", str(ROOT),
                        str(ROOT / "tests/time_domains/test_timeshadow_runtime.c"),
                        str(ROOT / "timeshadow_account.c"),
                        str(ROOT / "timeshadow_posix.c"),
                        "-o", str(runtime)], check=True)
        subprocess.run([str(runtime)], check=True)

    # Production hooks are standalone void statements, never conditions,
    # arguments, assignments, or return values feeding guest computations.
    expected = {"pccore.c": ["reset", "service", "service"],
                "nevent.c": ["commit", "rate_before", "rate_after"],
                "statsave.c": ["reset"]}
    for path, calls in expected.items():
        lines = (ROOT / path).read_text().splitlines()
        actual = []
        for line in lines:
            if "time_shadow_" in line:
                match = re.fullmatch(r"\s*time_shadow_(\w+)\(.*\);", line)
                assert match, (path, line)
                actual.append(match.group(1))
        assert actual == calls, (path, actual)
    # Account and platform adapter have no project guest-state dependencies.
    for path in ["timeshadow_account.c", "timeshadow_posix.c"]:
        includes = re.findall(r"#include [<\"]([^>\"]+)", (ROOT / path).read_text())
        assert set(includes) <= {"timeshadow_account.h", "limits.h", "string.h", "time.h"}
    tracked = subprocess.check_output(["git", "ls-files", "*.c", "*.h", "*.cpp"],
                                      cwd=ROOT, text=True).splitlines()
    for path in tracked:
        if path.startswith(("timeshadow", "tests/")) or path in expected:
            continue
        assert "np2_time_shadow" not in (ROOT / path).read_text(errors="replace"), path
        assert "time_shadow_" not in (ROOT / path).read_text(errors="replace"), path
    print("One-way diagnostic hook/source dependency checks: PASS")


if __name__ == "__main__":
    main()
