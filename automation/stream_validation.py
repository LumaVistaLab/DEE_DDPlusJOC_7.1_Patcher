from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from common import sha256_file, utc_now, write_json


SYNCWORD = 0x0B77

# Entries are 16-bit words indexed by frmsizecod and fscod.
AC3_FRAME_SIZE_WORDS = (
    (64, 69, 96), (64, 70, 96), (80, 87, 120), (80, 88, 120),
    (96, 104, 144), (96, 105, 144), (112, 121, 168), (112, 122, 168),
    (128, 139, 192), (128, 140, 192), (160, 174, 240), (160, 175, 240),
    (192, 208, 288), (192, 209, 288), (224, 243, 336), (224, 244, 336),
    (256, 278, 384), (256, 279, 384), (320, 348, 480), (320, 349, 480),
    (384, 417, 576), (384, 418, 576), (448, 487, 672), (448, 488, 672),
    (512, 557, 768), (512, 558, 768), (640, 696, 960), (640, 697, 960),
    (768, 835, 1152), (768, 836, 1152), (896, 975, 1344), (896, 976, 1344),
    (1024, 1114, 1536), (1024, 1115, 1536),
    (1152, 1253, 1728), (1152, 1254, 1728),
    (1280, 1393, 1920), (1280, 1394, 1920),
)


class BitReader:
    def __init__(self, data: bytes, bitpos: int) -> None:
        self.data = data
        self.bitpos = bitpos

    def read(self, count: int) -> int:
        value = 0
        for _ in range(count):
            if self.bitpos >= len(self.data) * 8:
                raise EOFError("unexpected end of bitstream")
            byte = self.data[self.bitpos >> 3]
            value = (value << 1) | ((byte >> (7 - (self.bitpos & 7))) & 1)
            self.bitpos += 1
        return value


def _ac3_header(data: bytes, offset: int) -> dict[str, int] | None:
    if offset + 8 > len(data):
        return None
    reader = BitReader(data, offset * 8)
    if reader.read(16) != SYNCWORD:
        return None
    reader.read(16)
    fscod = reader.read(2)
    frmsizecod = reader.read(6)
    bsid = reader.read(5)
    if fscod > 2 or frmsizecod >= len(AC3_FRAME_SIZE_WORDS) or bsid > 10:
        return None
    bsmod = reader.read(3)
    acmod = reader.read(3)
    if (acmod & 1) and acmod != 1:
        reader.read(2)
    if acmod & 4:
        reader.read(2)
    if acmod == 2:
        reader.read(2)
    lfeon = reader.read(1)
    return {
        "kind": "ac3",
        "offset": offset,
        "frame_size": AC3_FRAME_SIZE_WORDS[frmsizecod][fscod] * 2,
        "fscod": fscod,
        "frmsizecod": frmsizecod,
        "bsid": bsid,
        "bsmod": bsmod,
        "acmod": acmod,
        "lfeon": lfeon,
    }


def _eac3_header(data: bytes, offset: int) -> dict[str, int] | None:
    if offset + 8 > len(data):
        return None
    reader = BitReader(data, offset * 8)
    if reader.read(16) != SYNCWORD:
        return None
    strmtyp = reader.read(2)
    substreamid = reader.read(3)
    frmsiz = reader.read(11)
    fscod = reader.read(2)
    numblkscod = -1
    if fscod == 3:
        fscod2 = reader.read(2)
    else:
        fscod2 = -1
        numblkscod = reader.read(2)
    acmod = reader.read(3)
    lfeon = reader.read(1)
    bsid = reader.read(5)
    if bsid <= 10 or bsid > 16 or strmtyp == 3:
        return None
    return {
        "kind": "eac3",
        "offset": offset,
        "frame_size": (frmsiz + 1) * 2,
        "strmtyp": strmtyp,
        "substreamid": substreamid,
        "fscod": fscod,
        "fscod2": fscod2,
        "numblkscod": numblkscod,
        "bsid": bsid,
        "acmod": acmod,
        "lfeon": lfeon,
    }


def scan_frames(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if size == 0:
        return {
            "status": "empty",
            "file_size": 0,
            "frame_count": 0,
            "ac3_frames": 0,
            "eac3_frames": 0,
        }

    data = path.read_bytes()
    offset = 0
    counts: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    stream_types: Counter[str] = Counter()
    substream_ids: Counter[str] = Counter()
    sequence: list[str] = []
    first_headers: list[dict[str, int]] = []
    error: str | None = None

    while offset < len(data):
        if offset + 2 > len(data) or int.from_bytes(data[offset : offset + 2], "big") != SYNCWORD:
            error = f"syncword missing at byte offset {offset}"
            break
        header = _ac3_header(data, offset) or _eac3_header(data, offset)
        if header is None:
            error = f"unsupported AC-3/E-AC-3 header at byte offset {offset}"
            break
        frame_size = header["frame_size"]
        if frame_size <= 0 or offset + frame_size > len(data):
            error = f"truncated {header['kind']} frame at byte offset {offset}: size={frame_size}"
            break
        kind = str(header["kind"])
        counts[kind] += 1
        sizes[f"{kind}:{frame_size}"] += 1
        if kind == "eac3":
            stream_types[str(header["strmtyp"])] += 1
            substream_ids[str(header["substreamid"])] += 1
        if len(sequence) < 32:
            sequence.append(kind)
        if len(first_headers) < 8:
            first_headers.append(header)
        offset += frame_size

    return {
        "status": "valid" if error is None and offset == len(data) else "invalid",
        "file_size": len(data),
        "bytes_parsed": offset,
        "trailing_bytes": len(data) - offset,
        "frame_count": sum(counts.values()),
        "ac3_frames": counts["ac3"],
        "eac3_frames": counts["eac3"],
        "frame_sizes": dict(sorted(sizes.items())),
        "eac3_stream_types": dict(sorted(stream_types.items())),
        "eac3_substream_ids": dict(sorted(substream_ids.items())),
        "first_sequence": sequence,
        "first_headers": first_headers,
        "error": error,
    }


def _tool_result(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "available": False, "error": str(exc)}
    result: dict[str, Any] = {
        "command": command,
        "available": True,
        "returncode": completed.returncode,
        "stderr": completed.stderr,
        "stdout": completed.stdout,
    }
    try:
        result["json"] = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result["json"] = None
    return result


def inspect_media(path: Path) -> dict[str, Any]:
    mediainfo = shutil.which("mediainfo")
    ffprobe = shutil.which("ffprobe")
    return {
        "mediainfo": _tool_result([mediainfo, "--Output=JSON", str(path)]) if mediainfo else {"available": False},
        "ffprobe": _tool_result([
            ffprobe,
            "-v", "error",
            "-show_streams",
            "-show_format",
            "-of", "json",
            str(path),
        ]) if ffprobe else {"available": False},
    }


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _interesting_media_fields(value: Any, prefix: str = "") -> dict[str, Any]:
    selected: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(child, (dict, list)):
                selected.update(_interesting_media_fields(child, child_prefix))
            elif re.search(r"channel|layout|format|profile|commercial|atmos|joc", str(key), re.I):
                selected[child_prefix] = child
    elif isinstance(value, list):
        for index, child in enumerate(value):
            selected.update(_interesting_media_fields(child, f"{prefix}[{index}]"))
    return selected


def classify_layout(media: dict[str, Any], frame_scan: dict[str, Any]) -> dict[str, Any]:
    parsed_values = []
    for result in media.values():
        if isinstance(result, dict) and result.get("json") is not None:
            parsed_values.append(result["json"])
    joined = "\n".join(string for value in parsed_values for string in _walk_strings(value))

    rear_patterns = (
        r"\bLrs\b[^\r\n]*\bRrs\b",
        r"\bLb\b[^\r\n]*\bRb\b",
        r"(?:rear|back)[^\r\n]*(?:left|L)[^\r\n]*(?:right|R)",
    )
    height_patterns = (r"\bTfl\b", r"\bTfr\b", r"top[ _-]*front", r"height")
    rear_matches = sorted({match.group(0) for pattern in rear_patterns for match in re.finditer(pattern, joined, re.I)})
    height_matches = sorted({match.group(0) for pattern in height_patterns for match in re.finditer(pattern, joined, re.I)})
    joc_matches = sorted({match.group(0) for match in re.finditer(r"JOC|Dolby(?: Digital Plus)? with Dolby Atmos", joined, re.I)})

    if frame_scan.get("status") == "empty":
        verdict = "empty"
    elif frame_scan.get("status") != "valid":
        verdict = "invalid_bitstream"
    elif rear_matches and not height_matches and joc_matches:
        verdict = "flat_7_1_joc_evidence"
    elif height_matches:
        verdict = "height_layout_evidence"
    else:
        verdict = "inconclusive"
    return {
        "verdict": verdict,
        "rear_layout_matches": rear_matches,
        "height_layout_matches": height_matches,
        "joc_matches": joc_matches,
        "note": "No Dolby Surround EX flag is read, changed, or used for this verdict.",
    }


def validate_stream(path: Path, evidence_dir: Path | None = None) -> dict[str, Any]:
    if not path.exists():
        report = {
            "generated_at": utc_now(),
            "path": str(path),
            "status": "missing",
            "scope": "flat 7.1 layout only",
        }
        if evidence_dir:
            write_json(evidence_dir / "validation.json", report)
        return report

    frame_scan = scan_frames(path)
    media = inspect_media(path) if path.stat().st_size else {
        "mediainfo": {"available": bool(shutil.which("mediainfo")), "skipped": "empty file"},
        "ffprobe": {"available": bool(shutil.which("ffprobe")), "skipped": "empty file"},
    }
    classification = classify_layout(media, frame_scan)
    media_fields: dict[str, Any] = {}
    for name, result in media.items():
        if isinstance(result, dict) and result.get("json") is not None:
            media_fields[name] = _interesting_media_fields(result["json"])

    report = {
        "generated_at": utc_now(),
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "scope": "DD+ JOC flat 7.1 layout only; Dolby Surround EX is out of scope",
        "frame_scan": frame_scan,
        "classification": classification,
        "media_fields": media_fields,
        "tools": media,
    }
    if evidence_dir:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        write_json(evidence_dir / "validation.json", report)
    return report

