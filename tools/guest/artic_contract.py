# SPDX-License-Identifier: MIT
"""Independent fixture schedule and result format, not a product protocol."""
import struct

RESULT_ADDRESS = 0x29000
RESULT_SIZE = 544
RECORD_SIZE = 24
# case, monotonically supplied ns (except rejection probe), valid, word port
SAMPLES = [
    (2, 0, 1, 0x5c), (5, 3255, 1, 0x5c), (5, 3256, 1, 0x5c),
    (3, 5_000_000, 1, 0x5c), (4, 25_000_000, 1, 0x5c),
    (1, 1_000_000_000, 1, 0x5c), (13, 1_000_000_000, 1, 0x5e),
    (8, 1_000_000_000, 1, 0x5c), (9, 1_020_000_000, 1, 0x5c),
    (10, 1_025_000_000, 1, 0x5c),
    (14, 54_613_333_333, 1, 0x5c), (14, 54_613_333_333, 1, 0x5e),
    (6, 54_613_333_334, 1, 0x5c), (6, 54_613_333_334, 1, 0x5e),
    (7, 200_000_000_000, 1, 0x5c), (7, 200_000_000_000, 1, 0x5e),
    (16, 200_000_000_000, 0, 0x5c), (16, 0, 1, 0x5c),
    (17, 200_000_000_000, 1, 0x5c), (15, 200_000_000_001, 1, 0x5e),
]


def expected_samples():
    accepted = 0
    result = []
    for seq, (case, ns, valid, port) in enumerate(SAMPLES, 1):
        if valid and ns >= accepted:
            accepted = ns
        # Independent absolute-time reference, with arbitrary-width Python int.
        ticks, rem = divmod(accepted * 307200, 1_000_000_000)
        phase = ticks & 0xffffff
        result.append(dict(sequence=seq, case=case, ns=ns, valid=valid, port=port,
                           phase=phase, remainder=rem//12800,
                           expected=(phase >> (8 if port == 0x5e else 0)) & 65535))
    return result


def verify_result(data, mode):
    if len(data) != RESULT_SIZE or data[:4] != b'ARTC':
        raise ValueError('result size or magic')
    words = struct.unpack('<272H', data)
    if words[2:6] != (1, RESULT_SIZE, mode, len(SAMPLES)):
        raise ValueError('version/length/mode/count')
    if words[6] != 1 or words[269] != 0xa55a or words[271] != 2:
        raise ValueError('target class/guard/terminal state')
    if sum(words[:270]) & 65535 != words[270]:
        raise ValueError('result checksum')
    records = []
    for i, sample in enumerate(expected_samples()):
        rec = words[16+i*12:28+i*12]
        case, seq, port, raw, expect, progress, verdict = rec[:7]
        if (case,seq,port,expect,progress) != (sample['case'],i+1,sample['port'],sample['expected'],8192):
            raise ValueError(f'record identity/expected/progress {i+1}')
        if mode == 2 and (raw != expect or verdict != 1):
            raise ValueError(f'fake phase mismatch {i+1}: {raw} != {expect}')
        if mode == 1 and verdict != 2:
            raise ValueError('legacy record must be observation only')
        if any(rec[7:]):
            raise ValueError('reserved record words modified')
        records.append(dict(sample, raw=raw, cpu_progress=progress, verdict=verdict))
    if words[8] != 0:
        raise ValueError('guest failure count')
    return dict(state='PASS' if mode == 2 else 'LEGACY_OBSERVATIONS_COMPLETE',
                target_class='SYNTHETIC_EMULATOR_ARTIC_MODEL',
                bios_capability_byte=words[7], records=records,
                non_claims=['physical VM/VX identity','cross-port atomicity','live realtime','audio'])
