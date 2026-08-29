from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2"
EXPECTED_OUTPUT_SHA256 = "fd49c7b9b19bba5f7ec0b862a9811a7b822b2efe200bc82a033fb9b7f54c1588"

# The two sites are a synchronized pair. P2 alone is known to crash. Both
# assertions must match before either byte sequence is changed.
PATCHES = (
    (0x17C0D7, bytes.fromhex("B8 13 00 00 00"), bytes.fromhex("B8 15 00 00 00")),
    (0x17C9E8, bytes.fromhex("B8 13 00 00 00"), bytes.fromhex("B8 15 00 00 00")),
)


def sha256(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def update_pe_checksum(data: bytearray) -> None:
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    checksum_offset = pe_offset + 4 + 20 + 64
    total = 0
    for offset in range(0, len(data), 2):
        if checksum_offset <= offset < checksum_offset + 4:
            word = 0
        elif offset + 1 < len(data):
            word = data[offset] | (data[offset + 1] << 8)
        else:
            word = data[offset]
        total += word
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    total = (total + len(data)) & 0xFFFFFFFF
    struct.pack_into("<I", data, checksum_offset, total)


def build_patched_bytes(source: bytes) -> bytes:
    actual = sha256(source)
    if actual != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"unsupported source DLL SHA-256: {actual}")
    output = bytearray(source)
    for offset, expected, replacement in PATCHES:
        actual_bytes = bytes(output[offset : offset + len(expected)])
        if actual_bytes != expected:
            raise ValueError(
                f"byte assertion failed at 0x{offset:X}: "
                f"expected {expected.hex(' ')}, got {actual_bytes.hex(' ')}"
            )
    for offset, expected, replacement in PATCHES:
        output[offset : offset + len(expected)] = replacement
    update_pe_checksum(output)
    output_hash = sha256(output)
    if output_hash != EXPECTED_OUTPUT_SHA256:
        raise RuntimeError(
            f"internal reproducibility failure: expected {EXPECTED_OUTPUT_SHA256}, got {output_hash}"
        )
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the validated paired P2+P3 DEE DD+ JOC flat-7.1 patch."
    )
    parser.add_argument(
        "source",
        type=Path,
        nargs="?",
        default=Path("dll_original/dee_audio_filter_ddp_atmos.dll"),
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=Path("dll_patched/dee_audio_filter_ddp_atmos_cfg21_P2P3.dll"),
    )
    parser.add_argument("--check", action="store_true", help="Validate source and existing output without writing")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output after all checks")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    patched = build_patched_bytes(source.read_bytes())
    if args.check:
        if not output.is_file():
            raise FileNotFoundError(output)
        actual = sha256(output.read_bytes())
        if actual != EXPECTED_OUTPUT_SHA256:
            raise ValueError(f"existing output hash mismatch: {actual}")
        print(f"source: {EXPECTED_SOURCE_SHA256}")
        print(f"output: {actual}")
        return 0
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patched)
    print(f"wrote: {output}")
    print(f"sha256: {EXPECTED_OUTPUT_SHA256}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"patch build error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
