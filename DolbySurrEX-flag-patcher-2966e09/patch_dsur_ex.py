#!/usr/bin/env python3
"""Patch the AC-3 Dolby Surround EX flag inside Blu-ray DD+ / E-AC-3 streams.

The Dolby Media Producer Suite v2.0 (DMPS v2.0) Blu-ray DD+ Atmos files in this
repository are interleaved as:

    AC-3 core syncframe, 640 kb/s, 2560 bytes
    E-AC-3 dependent syncframe, 1024 kb/s, 4096 bytes

MediaInfo reports "Format settings: Dolby Surround EX" from the AC-3 core
extended bitstream information field `dsurexmod`.  DMPS v2.0 leaves that field
at 0 for this 7.1 Lrs/Rrs + PLIIx downmix case; later DMPS output sets it to 2.

This tool updates only that two-bit field and recomputes the two AC-3 CRC words.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SYNCWORD = 0x0B77
DSUREXMOD_NOT_INDICATED = 0
DSUREXMOD_NOT_EX = 1
DSUREXMOD_EX = 2

# AC-3 frame-size table entries are 16-bit words, indexed by frmsizecod and
# fscod: 0 = 48 kHz, 1 = 44.1 kHz, 2 = 32 kHz.
AC3_FRAME_SIZE_WORDS = (
    (64, 69, 96),
    (64, 70, 96),
    (80, 87, 120),
    (80, 88, 120),
    (96, 104, 144),
    (96, 105, 144),
    (112, 121, 168),
    (112, 122, 168),
    (128, 139, 192),
    (128, 140, 192),
    (160, 174, 240),
    (160, 175, 240),
    (192, 208, 288),
    (192, 209, 288),
    (224, 243, 336),
    (224, 244, 336),
    (256, 278, 384),
    (256, 279, 384),
    (320, 348, 480),
    (320, 349, 480),
    (384, 417, 576),
    (384, 418, 576),
    (448, 487, 672),
    (448, 488, 672),
    (512, 557, 768),
    (512, 558, 768),
    (640, 696, 960),
    (640, 697, 960),
    (768, 835, 1152),
    (768, 836, 1152),
    (896, 975, 1344),
    (896, 976, 1344),
    (1024, 1114, 1536),
    (1024, 1115, 1536),
    (1152, 1253, 1728),
    (1152, 1254, 1728),
    (1280, 1393, 1920),
    (1280, 1394, 1920),
)

CRC16_POLY = (1 << 0) | (1 << 2) | (1 << 15) | (1 << 16)


class BitReader:
    def __init__(self, data: bytes | bytearray, bitpos: int = 0) -> None:
        self.data = data
        self.bitpos = bitpos

    def read(self, nbits: int) -> int:
        value = 0
        for _ in range(nbits):
            if self.bitpos >= len(self.data) * 8:
                raise ValueError("unexpected end of frame while reading bits")
            byte = self.data[self.bitpos >> 3]
            bit = (byte >> (7 - (self.bitpos & 7))) & 1
            value = (value << 1) | bit
            self.bitpos += 1
        return value

    def tell(self) -> int:
        return self.bitpos


def set_bits(data: bytearray, bitpos: int, nbits: int, value: int) -> None:
    if value < 0 or value >= (1 << nbits):
        raise ValueError(f"value {value} does not fit in {nbits} bits")
    for index in range(nbits):
        shift = nbits - 1 - index
        bit = (value >> shift) & 1
        absolute = bitpos + index
        byte_index = absolute >> 3
        mask = 1 << (7 - (absolute & 7))
        if bit:
            data[byte_index] |= mask
        else:
            data[byte_index] &= ~mask & 0xFF


@dataclass(frozen=True)
class AC3Info:
    offset: int
    frame_size: int
    fscod: int
    frmsizecod: int
    bsid: int
    bsmod: int
    acmod: int
    lfeon: int
    dialnorm: int
    compre: int
    compr: int | None
    xbsi1e: int | None
    xbsi2e: int | None
    dmixmod: int | None
    dsurexmod: int | None
    dsurexmod_bitpos: int | None
    crc1_ok: bool
    crc2_ok: bool

    @property
    def patchable(self) -> bool:
        return (
            self.bsid == 6
            and self.acmod == 7
            and self.lfeon == 1
            and self.xbsi2e == 1
            and self.dsurexmod is not None
            and self.dsurexmod_bitpos is not None
        )


@dataclass(frozen=True)
class EAC3Info:
    offset: int
    frame_size: int
    strmtyp: int
    substreamid: int
    fscod: int
    numblkscod: int | None
    acmod: int
    lfeon: int
    bsid: int


def bswap16(value: int) -> int:
    return ((value & 0xFF) << 8) | (value >> 8)


def bswap32(value: int) -> int:
    return int.from_bytes(value.to_bytes(4, "little"), "big")


def build_crc16_ansi_table() -> tuple[int, ...]:
    table = []
    poly = 0x8005
    bits = 16
    for index in range(256):
        crc = (index << 24) & 0xFFFFFFFF
        for _ in range(8):
            mask = 0xFFFFFFFF if crc & 0x80000000 else 0
            crc = ((crc << 1) & 0xFFFFFFFF) ^ ((poly << (32 - bits)) & mask)
        table.append(bswap32(crc))
    return tuple(table)


CRC16_ANSI_TABLE = build_crc16_ansi_table()


def av_crc16_ansi(data: bytes | bytearray, crc: int = 0) -> int:
    for byte in data:
        crc = CRC16_ANSI_TABLE[(crc & 0xFF) ^ byte] ^ (crc >> 8)
    return crc & 0xFFFF


def mul_poly(a: int, b: int, poly: int = CRC16_POLY) -> int:
    result = 0
    while a:
        if a & 1:
            result ^= b
        a >>= 1
        b <<= 1
        if b & (1 << 16):
            b ^= poly
    return result


def pow_poly(a: int, n: int, poly: int = CRC16_POLY) -> int:
    result = 1
    while n:
        if n & 1:
            result = mul_poly(result, a, poly)
        a = mul_poly(a, a, poly)
        n >>= 1
    return result


def ac3_frame_size(fscod: int, frmsizecod: int) -> int | None:
    if fscod > 2 or frmsizecod >= len(AC3_FRAME_SIZE_WORDS):
        return None
    return AC3_FRAME_SIZE_WORDS[frmsizecod][fscod] * 2


def looks_like_ac3(data: bytes | bytearray, offset: int) -> tuple[int, int, int] | None:
    if offset + 8 > len(data):
        return None
    br = BitReader(data, offset * 8)
    if br.read(16) != SYNCWORD:
        return None
    br.read(16)  # crc1
    fscod = br.read(2)
    frmsizecod = br.read(6)
    bsid = br.read(5)
    frame_size = ac3_frame_size(fscod, frmsizecod)
    if frame_size is None or bsid > 10:
        return None
    return frame_size, fscod, frmsizecod


def eac3_frame_size(data: bytes | bytearray, offset: int) -> int | None:
    if offset + 8 > len(data):
        return None
    br = BitReader(data, offset * 8)
    if br.read(16) != SYNCWORD:
        return None
    br.read(2)  # strmtyp
    br.read(3)  # substreamid
    frmsiz = br.read(11)
    frame_size = (frmsiz + 1) * 2
    fscod = br.read(2)
    if fscod == 3:
        br.read(2)  # fscod2
    else:
        br.read(2)  # numblkscod
    br.read(3)  # acmod
    br.read(1)  # lfeon
    bsid = br.read(5)
    if bsid <= 10:
        return None
    return frame_size


def expected_ac3_crc(frame: bytes | bytearray) -> tuple[int, int]:
    frame_size = len(frame)
    frame_size_58 = ((frame_size >> 2) + (frame_size >> 4)) << 1
    crc_inv = pow_poly(CRC16_POLY >> 1, 8 * frame_size_58 - 16)
    crc1_raw = av_crc16_ansi(frame[4:frame_size_58])
    crc1 = mul_poly(crc_inv, bswap16(crc1_raw))
    crc2 = bswap16(av_crc16_ansi(frame[frame_size_58 : frame_size - 2]))
    return crc1, crc2


def update_ac3_crc(frame: bytearray) -> None:
    crc1, crc2 = expected_ac3_crc(frame)
    frame[2] = (crc1 >> 8) & 0xFF
    frame[3] = crc1 & 0xFF
    frame[-2] = (crc2 >> 8) & 0xFF
    frame[-1] = crc2 & 0xFF


def parse_ac3_info(data: bytes | bytearray, offset: int) -> AC3Info:
    ac3_probe = looks_like_ac3(data, offset)
    if ac3_probe is None:
        raise ValueError(f"offset {offset}: not an AC-3 syncframe")
    frame_size, fscod, frmsizecod = ac3_probe
    frame = data[offset : offset + frame_size]
    if len(frame) != frame_size:
        raise ValueError(f"offset {offset}: truncated AC-3 frame")

    br = BitReader(frame)
    br.read(16)  # syncword
    stored_crc1 = br.read(16)
    br.read(2)  # fscod
    br.read(6)  # frmsizecod
    bsid = br.read(5)
    bsmod = br.read(3)
    acmod = br.read(3)
    if (acmod & 1) and acmod != 1:
        br.read(2)  # cmixlev
    if acmod & 4:
        br.read(2)  # surmixlev
    if acmod == 2:
        br.read(2)  # dsurmod
    lfeon = br.read(1)
    dialnorm = br.read(5)
    compre = br.read(1)
    compr = br.read(8) if compre else None

    if acmod == 0:
        br.read(5)  # dialnorm2
        if br.read(1):
            br.read(8)  # compr2

    if br.read(1):
        br.read(8)  # langcod
    if br.read(1):
        br.read(5)  # mixlevel
        br.read(2)  # roomtyp

    if acmod == 0:
        if br.read(1):
            br.read(8)  # langcod2
        if br.read(1):
            br.read(5)  # mixlevel2
            br.read(2)  # roomtyp2

    br.read(1)  # copyrightb
    br.read(1)  # origbs

    xbsi1e = None
    xbsi2e = None
    dmixmod = None
    dsurexmod = None
    dsurexmod_bitpos = None

    if bsid == 6:
        xbsi1e = br.read(1)
        if xbsi1e:
            dmixmod = br.read(2)
            br.read(3)  # ltrtcmixlev
            br.read(3)  # ltrtsurmixlev
            br.read(3)  # lorocmixlev
            br.read(3)  # lorosurmixlev
        xbsi2e = br.read(1)
        if xbsi2e:
            dsurexmod_bitpos = br.tell()
            dsurexmod = br.read(2)
            br.read(2)  # dheadphonmod
            br.read(1)  # adconvtyp
            br.read(8)  # xbsi2
            br.read(1)  # encinfo
    else:
        if br.read(1):
            br.read(14)  # timecod1
        if br.read(1):
            br.read(14)  # timecod2

    if br.read(1):
        addbsil = br.read(6)
        for _ in range(addbsil + 1):
            br.read(8)

    expected_crc1, expected_crc2 = expected_ac3_crc(frame)
    stored_crc2 = int.from_bytes(frame[-2:], "big")

    return AC3Info(
        offset=offset,
        frame_size=frame_size,
        fscod=fscod,
        frmsizecod=frmsizecod,
        bsid=bsid,
        bsmod=bsmod,
        acmod=acmod,
        lfeon=lfeon,
        dialnorm=dialnorm,
        compre=compre,
        compr=compr,
        xbsi1e=xbsi1e,
        xbsi2e=xbsi2e,
        dmixmod=dmixmod,
        dsurexmod=dsurexmod,
        dsurexmod_bitpos=dsurexmod_bitpos,
        crc1_ok=stored_crc1 == expected_crc1,
        crc2_ok=stored_crc2 == expected_crc2,
    )


def parse_eac3_info(data: bytes | bytearray, offset: int) -> EAC3Info:
    frame_size = eac3_frame_size(data, offset)
    if frame_size is None:
        raise ValueError(f"offset {offset}: not an E-AC-3 syncframe")
    br = BitReader(data, offset * 8)
    br.read(16)  # syncword
    strmtyp = br.read(2)
    substreamid = br.read(3)
    br.read(11)  # frmsiz
    fscod = br.read(2)
    numblkscod = None if fscod == 3 else br.read(2)
    if fscod == 3:
        br.read(2)  # fscod2
    acmod = br.read(3)
    lfeon = br.read(1)
    bsid = br.read(5)
    return EAC3Info(
        offset=offset,
        frame_size=frame_size,
        strmtyp=strmtyp,
        substreamid=substreamid,
        fscod=fscod,
        numblkscod=numblkscod,
        acmod=acmod,
        lfeon=lfeon,
        bsid=bsid,
    )


@dataclass(frozen=True)
class ScanResult:
    ac3: list[AC3Info]
    eac3: list[EAC3Info]


def scan_frames(data: bytes | bytearray) -> ScanResult:
    ac3_frames: list[AC3Info] = []
    eac3_frames: list[EAC3Info] = []
    offset = 0
    while offset < len(data):
        if offset + 2 > len(data) or int.from_bytes(data[offset : offset + 2], "big") != SYNCWORD:
            raise ValueError(f"offset {offset}: syncword 0x0b77 not found")
        if (ac3_probe := looks_like_ac3(data, offset)) is not None:
            info = parse_ac3_info(data, offset)
            ac3_frames.append(info)
            offset += ac3_probe[0]
            continue
        if (frame_size := eac3_frame_size(data, offset)) is not None:
            eac3_frames.append(parse_eac3_info(data, offset))
            offset += frame_size
            continue
        raise ValueError(f"offset {offset}: unsupported AC-3/E-AC-3 syncframe")
    return ScanResult(ac3=ac3_frames, eac3=eac3_frames)


def patch_dsurexmod(data: bytearray, target: int = DSUREXMOD_EX, strict: bool = True) -> int:
    if target not in (DSUREXMOD_NOT_INDICATED, DSUREXMOD_NOT_EX, DSUREXMOD_EX):
        raise ValueError("target dsurexmod must be 0, 1, or 2")

    patched = 0
    scan = scan_frames(data)
    for info in scan.ac3:
        if not info.patchable:
            if strict:
                raise ValueError(
                    f"offset {info.offset}: AC-3 frame is not the expected bsid=6, "
                    "5.1+LFE, xbsi2e-present core frame"
                )
            continue
        if not info.crc1_ok or not info.crc2_ok:
            raise ValueError(f"offset {info.offset}: input AC-3 CRC mismatch")
        if info.dsurexmod == target:
            continue

        frame = bytearray(data[info.offset : info.offset + info.frame_size])
        assert info.dsurexmod_bitpos is not None
        set_bits(frame, info.dsurexmod_bitpos, 2, target)
        update_ac3_crc(frame)
        data[info.offset : info.offset + info.frame_size] = frame
        patched += 1
    return patched


def count_values(values: Iterable[int | None]) -> dict[int | None, int]:
    counts: dict[int | None, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def print_scan(path: Path, scan: ScanResult) -> None:
    dsurex_counts = count_values(info.dsurexmod for info in scan.ac3)
    bad_crc = sum(not (info.crc1_ok and info.crc2_ok) for info in scan.ac3)
    print(f"{path}:")
    print(f"  AC-3 core frames: {len(scan.ac3)}")
    print(f"  E-AC-3 dependent frames: {len(scan.eac3)}")
    print(f"  dsurexmod counts: {dsurex_counts}")
    print(f"  AC-3 CRC mismatches: {bad_crc}")
    if scan.ac3:
        first = scan.ac3[0]
        print(
            "  first AC-3: "
            f"size={first.frame_size}, bsid={first.bsid}, acmod={first.acmod}, "
            f"lfeon={first.lfeon}, dmixmod={first.dmixmod}, dsurexmod={first.dsurexmod}"
        )
    if scan.eac3:
        first_eac3 = scan.eac3[0]
        print(
            "  first E-AC-3: "
            f"size={first_eac3.frame_size}, strmtyp={first_eac3.strmtyp}, "
            f"substreamid={first_eac3.substreamid}, bsid={first_eac3.bsid}, "
            f"acmod={first_eac3.acmod}, lfeon={first_eac3.lfeon}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch AC-3 dsurexmod to Dolby Surround EX in Blu-ray DD+ streams."
    )
    parser.add_argument("input", type=Path, help="Input .eb3/.ec3/.eac3/.ac3 file")
    parser.add_argument("output", type=Path, nargs="?", help="Output file")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only scan and report frame structure; do not write an output file",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=DSUREXMOD_EX,
        choices=(0, 1, 2),
        help="Target dsurexmod value: 0=not indicated, 1=not EX, 2=EX (default)",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Skip non-matching AC-3 frames instead of rejecting the file",
    )
    args = parser.parse_args()

    data = bytearray(args.input.read_bytes())
    before = scan_frames(data)
    print_scan(args.input, before)

    if args.check:
        return 0
    if args.output is None:
        parser.error("output path is required unless --check is used")

    patched = patch_dsurexmod(data, target=args.target, strict=not args.no_strict)
    after = scan_frames(data)
    bad_crc = sum(not (info.crc1_ok and info.crc2_ok) for info in after.ac3)
    if bad_crc:
        raise SystemExit(f"internal error: patched output has {bad_crc} AC-3 CRC mismatches")

    args.output.write_bytes(data)
    print(f"patched AC-3 frames: {patched}")
    print(f"wrote: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
