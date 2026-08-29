#!/usr/bin/env python3
"""Generate experimental DEE v5.2.1 DD+ Atmos flat-7.1 DLL variants.

Targets exactly the user-supplied dee_audio_filter_ddp_atmos.dll build.
No patch is applied unless SHA-256 and original bytes match.
"""
from pathlib import Path
import argparse, hashlib, struct, sys

EXPECTED_SHA256 = '3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2'

PATCHES = {
    'P1': [
        # AtmosProcessor output-format construction sites:
        # LEA RDX, "5.1" -> LEA RDX, existing "7.1"
        (0x1798EC, bytes.fromhex('48 8D 15 E5 FF 4C 00'), bytes.fromhex('48 8D 15 B9 2C 4D 00')),
        (0x17ACDA, bytes.fromhex('48 8D 15 F7 EB 4C 00'), bytes.fromhex('48 8D 15 CB 18 4D 00')),
    ],
    'P2': [
        # Blu-ray branch candidate channel/input configuration:
        # 19 (0x13, modern 5.X+2 candidate) -> 21 (0x15, flat 7.1 candidate)
        (0x17C9E8, bytes.fromhex('B8 13 00 00 00'), bytes.fromhex('B8 15 00 00 00')),
    ],
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def update_pe_checksum(data: bytearray) -> tuple[int, int]:
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    opt = pe + 4 + 20
    chk_off = opt + 64
    total = 0
    for i in range(0, len(data), 2):
        if chk_off <= i < chk_off + 4:
            word = 0
        elif i + 1 < len(data):
            word = data[i] | (data[i + 1] << 8)
        else:
            word = data[i]
        total += word
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    total = (total + len(data)) & 0xFFFFFFFF
    struct.pack_into('<I', data, chk_off, total)
    return chk_off, total

def apply(src: bytes, names: tuple[str, ...]) -> bytearray:
    data = bytearray(src)
    for name in names:
        for off, old, new in PATCHES[name]:
            got = bytes(data[off:off + len(old)])
            if got != old:
                raise RuntimeError(
                    f'{name} @ 0x{off:X}: expected {old.hex(" ")}, got {got.hex(" ")}'
                )
            data[off:off + len(new)] = new
    update_pe_checksum(data)
    return data

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('dll', type=Path, help='Original dee_audio_filter_ddp_atmos.dll')
    ap.add_argument('-o', '--out-dir', type=Path, default=None)
    args = ap.parse_args()

    src_path = args.dll.resolve()
    out_dir = (args.out_dir or src_path.parent).resolve()
    src = src_path.read_bytes()
    actual = sha256(src)
    if actual != EXPECTED_SHA256:
        print('Refusing to patch: binary SHA-256 does not match the analyzed build.', file=sys.stderr)
        print(f'Expected: {EXPECTED_SHA256}', file=sys.stderr)
        print(f'Actual:   {actual}', file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    variants = [
        (('P1',), 'dee_audio_filter_ddp_atmos_flat71_P1.dll'),
        (('P2',), 'dee_audio_filter_ddp_atmos_flat71_P2.dll'),
        (('P1','P2'), 'dee_audio_filter_ddp_atmos_flat71_P1P2.dll'),
    ]
    for names, filename in variants:
        data = apply(src, names)
        out = out_dir / filename
        out.write_bytes(data)
        print(f'{filename}: {sha256(data)}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
