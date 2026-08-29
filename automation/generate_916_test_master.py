from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = REPO_ROOT / "example-flow" / "sollevante_lp_v01_DAMF_Nearfield_48k_24b_24.wav"
DEFAULT_OUTPUT = REPO_ROOT / "automation" / "work" / "test_audio" / "atmos_916_channel_id_adm.wav"

SAMPLE_RATE = 48_000
BIT_DEPTH = 24
BYTES_PER_SAMPLE = BIT_DEPTH // 8
DURATION_SECONDS = 40
TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SECONDS

ADM_NAMESPACE = "urn:ebu:metadata-schema:ebuCore_2016"
ET.register_namespace("", ADM_NAMESPACE)
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")


# Physical track order in the generated ADM BWF. Dolby Atmos beds are limited to
# 7.1.2, so the remaining 9.1.6 speaker positions are fixed objects.
TRACKS = [
    {"track": 1, "label": "L", "name": "Left", "kind": "bed", "frequency_hz": 440.00},
    {"track": 2, "label": "R", "name": "Right", "kind": "bed", "frequency_hz": 554.37},
    {"track": 3, "label": "C", "name": "Center", "kind": "bed", "frequency_hz": 659.26},
    {"track": 4, "label": "LFE", "name": "Low Frequency Effects", "kind": "bed", "frequency_hz": 55.00},
    {"track": 5, "label": "Lss", "name": "Left Side Surround", "kind": "bed", "frequency_hz": 493.88},
    {"track": 6, "label": "Rss", "name": "Right Side Surround", "kind": "bed", "frequency_hz": 622.25},
    {"track": 7, "label": "Lrs", "name": "Left Rear Surround", "kind": "bed", "frequency_hz": 523.25},
    {"track": 8, "label": "Rrs", "name": "Right Rear Surround", "kind": "bed", "frequency_hz": 698.46},
    {"track": 9, "label": "Ltm", "name": "Left Top Middle", "kind": "bed", "frequency_hz": 783.99},
    {"track": 10, "label": "Rtm", "name": "Right Top Middle", "kind": "bed", "frequency_hz": 987.77},
    {"track": 11, "label": "Lw", "name": "Left Wide", "kind": "object", "frequency_hz": 466.16,
     "position": {"X": -1.0, "Y": 0.75, "Z": 0.0}},
    {"track": 12, "label": "Rw", "name": "Right Wide", "kind": "object", "frequency_hz": 587.33,
     "position": {"X": 1.0, "Y": 0.75, "Z": 0.0}},
    {"track": 13, "label": "Ltf", "name": "Left Top Front", "kind": "object", "frequency_hz": 739.99,
     "position": {"X": -0.5, "Y": 1.0, "Z": 1.0}},
    {"track": 14, "label": "Rtf", "name": "Right Top Front", "kind": "object", "frequency_hz": 932.33,
     "position": {"X": 0.5, "Y": 1.0, "Z": 1.0}},
    {"track": 15, "label": "Ltr", "name": "Left Top Rear", "kind": "object", "frequency_hz": 880.00,
     "position": {"X": -0.5, "Y": -1.0, "Z": 1.0}},
    {"track": 16, "label": "Rtr", "name": "Right Top Rear", "kind": "object", "frequency_hz": 1108.73,
     "position": {"X": 0.5, "Y": -1.0, "Z": 1.0}},
]

# Listening order is conventional 9.1.6 rather than the file's bed-first track
# order. Each slot starts with three short identification bursts followed by a
# sustained tone. This remains easy to locate even after lossy JOC coding.
SEQUENCE = [
    "L", "R", "C", "LFE", "Lw", "Rw", "Lss", "Rss",
    "Lrs", "Rrs", "Ltf", "Rtf", "Ltm", "Rtm", "Ltr", "Rtr",
]
SEQUENCE_START_SECONDS = 2.0
SLOT_SECONDS = 2.0


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def qname(name: str) -> str:
    return f"{{{ADM_NAMESPACE}}}{name}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_riff_chunks(path: Path, wanted: set[bytes] | None = None) -> dict[bytes, bytes]:
    chunks: dict[bytes, bytes] = {}
    with path.open("rb") as handle:
        header = handle.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise ValueError(f"not a RIFF/WAVE file: {path}")
        while True:
            chunk_header = handle.read(8)
            if not chunk_header:
                break
            if len(chunk_header) != 8:
                raise ValueError(f"truncated RIFF chunk header in {path}")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            if wanted is None or chunk_id in wanted:
                chunks[chunk_id] = handle.read(chunk_size)
                if len(chunks[chunk_id]) != chunk_size:
                    raise ValueError(f"truncated {chunk_id!r} chunk in {path}")
            else:
                handle.seek(chunk_size, 1)
            if chunk_size & 1:
                handle.read(1)
    return chunks


def first_child(element: ET.Element, name: str) -> ET.Element:
    for child in element:
        if local_name(child.tag) == name:
            return child
    raise KeyError(name)


def set_single_text_child(element: ET.Element, name: str, text: str) -> None:
    matches = [child for child in element if local_name(child.tag) == name]
    if not matches:
        child = ET.SubElement(element, qname(name))
    else:
        child = matches[0]
        for duplicate in matches[1:]:
            element.remove(duplicate)
    child.text = text


def time_text(seconds: float) -> str:
    hours = int(seconds // 3600)
    seconds -= hours * 3600
    minutes = int(seconds // 60)
    seconds -= minutes * 60
    return f"{hours:02d}:{minutes:02d}:{seconds:08.5f}"


def build_axml(template_axml: bytes) -> bytes:
    root = ET.fromstring(template_axml.rstrip(b"\0"))
    extended = next(element for element in root.iter() if local_name(element.tag) == "audioFormatExtended")

    object_tracks = [track for track in TRACKS if track["kind"] == "object"]
    selected_object_count = len(object_tracks)
    allowed = {
        "audioContent": {"ACO_1001"},
        "audioObject": {"AO_1001"},
        "audioPackFormat": {"AP_00011001"}
                           | {f"AP_0003{0x1000 + index:04x}" for index in range(1, selected_object_count + 1)},
        "audioChannelFormat": {f"AC_000110{index:02x}" for index in range(1, 11)}
                              | {f"AC_0003{0x1000 + index:04x}" for index in range(1, selected_object_count + 1)},
        "audioStreamFormat": {f"AS_000110{index:02x}" for index in range(1, 11)}
                             | {f"AS_0003{0x1000 + index:04x}" for index in range(1, selected_object_count + 1)},
        "audioTrackFormat": {f"AT_000110{index:02x}_01" for index in range(1, 11)}
                            | {f"AT_0003{0x1000 + index:04x}_01" for index in range(1, selected_object_count + 1)},
        "audioTrackUID": {f"ATU_{index:08x}" for index in range(1, len(TRACKS) + 1)},
    }
    id_attribute = {
        "audioContent": "audioContentID",
        "audioObject": "audioObjectID",
        "audioPackFormat": "audioPackFormatID",
        "audioChannelFormat": "audioChannelFormatID",
        "audioStreamFormat": "audioStreamFormatID",
        "audioTrackFormat": "audioTrackFormatID",
        "audioTrackUID": "UID",
    }

    # IDs in the source use hexadecimal suffixes. State the exact six object IDs
    # explicitly so that selection cannot drift if the template is changed.
    selected_objects = {f"AO_{0x100B + index:04x}" for index in range(selected_object_count)}
    allowed["audioObject"] = {"AO_1001"} | selected_objects

    for child in list(extended):
        name = local_name(child.tag)
        if name in allowed and child.attrib.get(id_attribute[name]) not in allowed[name]:
            extended.remove(child)

    programme = next(element for element in extended if local_name(element.tag) == "audioProgramme")
    programme.attrib.update({
        "audioProgrammeName": "Atmos_9.1.6_Channel_ID",
        "start": "01:00:00.00000",
        "end": time_text(3600 + DURATION_SECONDS),
    })
    for child in list(programme):
        if local_name(child.tag) == "audioContentIDRef":
            programme.remove(child)
    ET.SubElement(programme, qname("audioContentIDRef")).text = "ACO_1001"

    content = next(element for element in extended if element.attrib.get("audioContentID") == "ACO_1001")
    content.attrib["audioContentName"] = "Atmos 9.1.6 deterministic channel identification"
    for child in list(content):
        content.remove(child)
    ET.SubElement(content, qname("audioObjectIDRef")).text = "AO_1001"
    for object_id in sorted(selected_objects):
        ET.SubElement(content, qname("audioObjectIDRef")).text = object_id
    dialogue = ET.SubElement(content, qname("dialogue"), {"mixedContentKind": "0"})
    dialogue.text = "2"

    objects = {element.attrib.get("audioObjectID"): element for element in extended
               if local_name(element.tag) == "audioObject"}
    bed = objects["AO_1001"]
    bed.attrib.update({"audioObjectName": "9.1.6 BED 7.1.2", "start": time_text(0),
                       "duration": time_text(DURATION_SECONDS)})

    for index, track in enumerate(object_tracks, start=1):
        object_id = f"AO_{0x100A + index:04x}"
        audio_object = objects[object_id]
        audio_object.attrib.update({
            "audioObjectName": f"9.1.6 {track['label']} {track['name']}",
            "start": time_text(0),
            "duration": time_text(DURATION_SECONDS),
        })

    packs = {element.attrib.get("audioPackFormatID"): element for element in extended
             if local_name(element.tag) == "audioPackFormat"}
    packs["AP_00011001"].attrib["audioPackFormatName"] = "9.1.6 BED 7.1.2"

    channels = {element.attrib.get("audioChannelFormatID"): element for element in extended
                if local_name(element.tag) == "audioChannelFormat"}
    for index, track in enumerate(object_tracks, start=1):
        object_format_id = 0x1000 + index
        pack_id = f"AP_0003{object_format_id:04x}"
        channel_id = f"AC_0003{object_format_id:04x}"
        packs[pack_id].attrib["audioPackFormatName"] = f"9.1.6 {track['label']}"
        channel = channels[channel_id]
        channel.attrib["audioChannelFormatName"] = f"9.1.6_{track['label']}"
        for child in list(channel):
            channel.remove(child)
        block = ET.SubElement(channel, qname("audioBlockFormat"), {
            "audioBlockFormatID": f"AB_0003{object_format_id:04x}_00000001",
            "rtime": time_text(0),
            "duration": time_text(DURATION_SECONDS),
        })
        ET.SubElement(block, qname("cartesian")).text = "1"
        for coordinate in ("X", "Y", "Z"):
            ET.SubElement(block, qname("position"), {"coordinate": coordinate}).text = (
                f"{track['position'][coordinate]:.10f}"
            )
        jump = ET.SubElement(block, qname("jumpPosition"), {"interpolationLength": "0.000000"})
        jump.text = "1"

    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml + b"\n"


def build_chna(template_chna: bytes) -> bytes:
    if len(template_chna) < 4:
        raise ValueError("template chna chunk is truncated")
    track_count, uid_count = struct.unpack_from("<HH", template_chna)
    if track_count != uid_count or uid_count < len(TRACKS):
        raise ValueError(f"unexpected template chna counts: {track_count}, {uid_count}")
    record_size, remainder = divmod(len(template_chna) - 4, uid_count)
    if remainder or record_size != 40:
        raise ValueError(f"unexpected template chna record size: {record_size}")
    return struct.pack("<HH", len(TRACKS), len(TRACKS)) + template_chna[4:4 + record_size * len(TRACKS)]


def write_chunk(handle: BinaryIO, chunk_id: bytes, payload: bytes) -> None:
    handle.write(struct.pack("<4sI", chunk_id, len(payload)))
    handle.write(payload)
    if len(payload) & 1:
        handle.write(b"\0")


def envelope(relative_seconds: float) -> float:
    if not 0.0 <= relative_seconds < SLOT_SECONDS:
        return 0.0
    # Three 250 ms bursts followed by a sustained 750 ms tone. The final 200 ms
    # is silent, making channel boundaries unambiguous.
    regions = ((0.10, 0.35), (0.50, 0.75), (0.90, 1.15), (1.25, 1.80))
    for start, end in regions:
        if start <= relative_seconds < end:
            attack = min(1.0, (relative_seconds - start) / 0.010)
            release = min(1.0, (end - relative_seconds) / 0.010)
            return max(0.0, min(attack, release))
    return 0.0


def sample_value(track: dict[str, object], time_seconds: float) -> float:
    sequence_index = SEQUENCE.index(str(track["label"]))
    relative = time_seconds - (SEQUENCE_START_SECONDS + sequence_index * SLOT_SECONDS)
    level = envelope(relative)
    if not level:
        return 0.0
    frequency = float(track["frequency_hz"])
    amplitude = 0.20 if track["label"] != "LFE" else 0.14
    fundamental = math.sin(2.0 * math.pi * frequency * time_seconds)
    harmonic = 0.18 * math.sin(2.0 * math.pi * frequency * 2.0 * time_seconds)
    return amplitude * level * (fundamental + harmonic) / 1.18


def pack_pcm24(value: float) -> bytes:
    integer = max(-8_388_608, min(8_388_607, round(value * 8_388_607)))
    return int(integer & 0xFFFFFF).to_bytes(3, byteorder="little", signed=False)


def write_data_chunk(handle: BinaryIO) -> None:
    data_size = TOTAL_SAMPLES * len(TRACKS) * BYTES_PER_SAMPLE
    handle.write(struct.pack("<4sI", b"data", data_size))
    block_frames = 2_000  # exactly one 24 fps video frame at 48 kHz
    for first_sample in range(0, TOTAL_SAMPLES, block_frames):
        block = bytearray()
        for sample_index in range(first_sample, min(first_sample + block_frames, TOTAL_SAMPLES)):
            time_seconds = sample_index / SAMPLE_RATE
            for track in TRACKS:
                block.extend(pack_pcm24(sample_value(track, time_seconds)))
        handle.write(block)
    if data_size & 1:
        handle.write(b"\0")


def make_fmt_chunk() -> bytes:
    channel_count = len(TRACKS)
    block_align = channel_count * BYTES_PER_SAMPLE
    byte_rate = SAMPLE_RATE * block_align
    return struct.pack("<HHIIHH", 1, channel_count, SAMPLE_RATE, byte_rate, block_align, BIT_DEPTH)


def riff_payload_size(chunks: list[tuple[bytes, bytes]], data_size: int) -> int:
    size = 4  # WAVE form type
    for _chunk_id, payload in chunks:
        size += 8 + len(payload) + (len(payload) & 1)
    size += 8 + data_size + (data_size & 1)
    return size


def write_master(template: Path, output: Path) -> dict[str, object]:
    required_chunks = {b"JUNK", b"axml", b"chna", b"dbmd"}
    chunks = read_riff_chunks(template, required_chunks)
    for required in required_chunks:
        if required not in chunks:
            raise ValueError(f"template is missing required {required!r} chunk")

    axml = build_axml(chunks[b"axml"])
    chna = build_chna(chunks[b"chna"])
    ordered_chunks = [(b"JUNK", chunks[b"JUNK"]), (b"fmt ", make_fmt_chunk())]
    trailing_chunks = [(b"axml", axml), (b"chna", chna), (b"dbmd", chunks[b"dbmd"])]
    data_size = TOTAL_SAMPLES * len(TRACKS) * BYTES_PER_SAMPLE
    riff_size = riff_payload_size(ordered_chunks + trailing_chunks, data_size)
    if riff_size > 0xFFFFFFFF:
        raise OverflowError("generated master exceeds RIFF's 4 GiB limit")

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    try:
        with output.open("xb") as handle:
            handle.write(struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE"))
            for chunk_id, payload in ordered_chunks:
                write_chunk(handle, chunk_id, payload)
            write_data_chunk(handle)
            for chunk_id, payload in trailing_chunks:
                write_chunk(handle, chunk_id, payload)
    except Exception:
        output.unlink(missing_ok=True)
        raise

    schedule = []
    by_label = {str(track["label"]): track for track in TRACKS}
    for index, label in enumerate(SEQUENCE):
        track = by_label[label]
        start = SEQUENCE_START_SECONDS + index * SLOT_SECONDS
        schedule.append({
            "start_seconds": start,
            "end_seconds": start + SLOT_SECONDS,
            "label": label,
            "name": track["name"],
            "track": track["track"],
            "kind": track["kind"],
            "frequency_hz": track["frequency_hz"],
            "position": track.get("position"),
        })
    report = {
        "schema_version": 1,
        "purpose": [
            "verify the DD+ 7.1 compatibility presentation's coded-channel rendering",
            "verify Dolby Atmos spatial rendering on a 9.1.6 playback layout",
        ],
        "template": str(template.resolve()),
        "output": str(output.resolve()),
        "sha256": sha256_file(output),
        "size": output.stat().st_size,
        "format": {
            "container": "Dolby-authored ADM BWF structure",
            "sample_rate": SAMPLE_RATE,
            "bit_depth": BIT_DEPTH,
            "duration_seconds": DURATION_SECONDS,
            "channels": len(TRACKS),
            "composition": "7.1.2 bed plus 6 fixed objects targeting 9.1.6",
        },
        "tracks": TRACKS,
        "schedule": schedule,
    }
    report_path = output.with_suffix(output.suffix + ".json")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deterministic 9.1.6 Atmos ADM BWF test master")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = write_master(args.template.resolve(), args.output.resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
