from pathlib import Path
import hashlib, struct, sys

EXPECTED_SHA256 = "3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2"

# P1: AtmosProcessor output-format references: "5.1" -> existing "7.1"
P1 = [
    (0x1798EC, bytes.fromhex("48 8D 15 E5 FF 4C 00"), bytes.fromhex("48 8D 15 B9 2C 4D 00")),
    (0x17ACDA, bytes.fromhex("48 8D 15 F7 EB 4C 00"), bytes.fromhex("48 8D 15 CB 18 4D 00")),
]

# P2: querymem/open-side Blu-ray conditional value: 19 -> 21
P2 = [
    (0x17C9E8, bytes.fromhex("B8 13 00 00 00"), bytes.fromhex("B8 15 00 00 00")),
]

# P3: matching set_params-side Blu-ray conditional value: 19 -> 21
P3 = [
    (0x17C0D7, bytes.fromhex("B8 13 00 00 00"), bytes.fromhex("B8 15 00 00 00")),
]

def pe_checksum(data: bytearray):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    checksum_off = pe + 4 + 20 + 64
    total = 0
    for i in range(0, len(data), 2):
        if checksum_off <= i < checksum_off + 4:
            word = 0
        elif i + 1 < len(data):
            word = data[i] | (data[i + 1] << 8)
        else:
            word = data[i]
        total += word
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    total = (total + len(data)) & 0xFFFFFFFF
    struct.pack_into("<I", data, checksum_off, total)

def patch(src: bytes, specs):
    out = bytearray(src)
    for off, old, new in specs:
        got = bytes(out[off:off+len(old)])
        if got != old:
            raise RuntimeError(
                f"Byte assertion failed at 0x{off:X}: "
                f"got {got.hex(' ')}, expected {old.hex(' ')}"
            )
        out[off:off+len(new)] = new
    pe_checksum(out)
    return bytes(out)

def main():
    if len(sys.argv) != 2:
        print("Usage: python make_dee_cfg21_patches_v2.py dee_audio_filter_ddp_atmos.dll")
        raise SystemExit(2)

    src_path = Path(sys.argv[1])
    src = src_path.read_bytes()
    sha = hashlib.sha256(src).hexdigest()
    if sha != EXPECTED_SHA256:
        raise RuntimeError(f"Unsupported source DLL SHA-256: {sha}")

    variants = {
        "dee_audio_filter_ddp_atmos_cfg21_P2P3.dll": P2 + P3,
        "dee_audio_filter_ddp_atmos_cfg21_P1P2P3.dll": P1 + P2 + P3,
        "dee_audio_filter_ddp_atmos_cfg21_P3only.dll": P3,
    }

    for name, specs in variants.items():
        data = patch(src, specs)
        dst = src_path.with_name(name)
        dst.write_bytes(data)
        print(f"{name}: {hashlib.sha256(data).hexdigest()}")

if __name__ == "__main__":
    main()
