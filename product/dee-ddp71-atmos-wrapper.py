#!/usr/bin/env python3
"""DD+ 7.1 Atmos Wrapper for Dolby Encoding Engine 5.2.1.

This command-line wrapper builds DEE XML jobs from the original
atmos_mezz_encode_to_atmos_ddp_ec3.xml template, applies the validated P2+P3
patch only for flat-7.1 jobs, and always restores the DEE component afterward.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import locale
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence


PRODUCT_NAME = "DD+ 7.1 Atmos Wrapper for Dolby Encoding Engine"
VERSION = "0.1.0-dev"
PRODUCT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = PRODUCT_DIR / "templates" / "atmos_mezz_encode_to_atmos_ddp_ec3.xml"
DSUR_EX_PATCHER = PRODUCT_DIR / "tools" / "patch_dsur_ex.py"

PATCHED_COMPONENT = "dee_audio_filter_ddp_atmos.dll"
SUPPORTED_ORIGINAL_SHA256 = "3d66bcec36031fd48e6565d15f05fea656642377ca4f8c98cdce1cce8b7e95d2"
EXPECTED_FLAT71_SHA256 = "fd49c7b9b19bba5f7ec0b862a9811a7b822b2efe200bc82a033fb9b7f54c1588"
FLAT71_PATCHES = (
    # P3: set_params-side Blu-ray configuration, 19 -> 21.
    (0x17C0D7, bytes.fromhex("B8 13 00 00 00"), bytes.fromhex("B8 15 00 00 00")),
    # P2: querymem/open-side Blu-ray configuration, 19 -> 21.
    (0x17C9E8, bytes.fromhex("B8 13 00 00 00"), bytes.fromhex("B8 15 00 00 00")),
)

FRAME_RATES = ("not_indicated", "23.976", "24", "25", "29.97", "30", "48", "50", "59.94", "60")
BLURAY_DATA_RATES = (1152, 1280, 1408, 1512, 1536, 1664)
METERING_MODES = ("1770-4", "1770-3", "1770-2", "1770-1", "LeqA")
DRC_PROFILES = ("film_standard", "film_light", "music_standard", "music_light", "speech", "none")
CENTER_MIX_LEVELS = ("+3", "+1.5", "0", "-1.5", "-3", "-4.5", "-6", "-inf")
SURROUND_MIX_LEVELS = ("-1.5", "-3", "-4.5", "-6", "-inf")
SURROUND_TRIMS = ("0", "-3", "-6", "-9", "auto")
HEIGHT_TRIMS = ("-3", "-6", "-9", "-12", "auto")
SEGMENT_POINT_RE = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d):(\d{2})$")
SILENCE_RE = re.compile(r"^(?:\d+(?:\.\d+)?|\d+f)$")
CONSERVATIVE_WINDOWS_PATH_RE = re.compile(r"^[A-Za-z0-9_ .:\\/()\-]+$")


class WrapperError(RuntimeError):
    """Expected user-facing wrapper failure."""


class CommandFailure(WrapperError):
    def __init__(self, label: str, returncode: int) -> None:
        super().__init__(f"{label} failed with exit code {returncode}")
        self.returncode = returncode


@dataclass(frozen=True)
class JobPlan:
    index: int
    count: int
    start: str | None
    end: str | None
    final_output: Path
    encoded_output: Path
    finalized_output: Path | None
    xml_path: Path
    dee_log_path: Path
    ex_log_path: Path | None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_bool(value: str) -> bool:
    normalized = value.casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def bounded_integer(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("expected an integer") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"expected an integer from {minimum} to {maximum}")
        return number

    return parse


def silence_duration(value: str) -> str:
    if not SILENCE_RE.fullmatch(value):
        raise argparse.ArgumentTypeError("expected seconds.milliseconds or a frame count such as 12f")
    return value


def nonempty(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("value must not be empty")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dee-ddp71-atmos-wrapper",
        description=(
            "Generate and run complete DEE 5.2.1 Blu-ray DD+ Atmos jobs with a "
            "5.1+2 (7.1 Height) or flat-7.1 compatibility presentation."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("dee", type=Path, help="DEE 5.2.1 directory, or its dee.exe path")
    parser.add_argument("input", type=Path, help="Dolby Atmos mezzanine input path")
    parser.add_argument("output", type=Path, help="output .ec3/.eb3 path, or batch naming base")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    original = parser.add_argument_group(
        "original template parameter overrides (in XML order)",
        "Omitted values are reused from atmos_mezz_encode_to_atmos_ddp_ec3.xml, except data-rate.",
    )
    original.add_argument("--input-timecode-frame-rate", choices=FRAME_RATES)
    original.add_argument("--input-offset", type=nonempty, metavar="VALUE", help="auto, timecode, or decimal seconds")
    original.add_argument("--input-ffoa", type=nonempty, metavar="VALUE", help="auto, timecode, or decimal seconds")
    original.add_argument("--metering-mode", choices=METERING_MODES)
    original.add_argument("--dialogue-intelligence", type=parse_bool, metavar="{true,false}")
    original.add_argument("--speech-threshold", type=bounded_integer(0, 100), metavar="0..100")
    original.add_argument(
        "--data-rate",
        type=int,
        choices=BLURAY_DATA_RATES,
        default=1152,
        help="Blu-ray DD+ Atmos kbps (wrapper default: 1152)",
    )
    original.add_argument("--timecode-frame-rate", choices=FRAME_RATES)
    original.add_argument("--start", type=nonempty, help="timecode, decimal seconds, frame number, or first_frame_of_action")
    original.add_argument("--end", type=nonempty, help="timecode, decimal seconds, frame number, or end_of_file")
    original.add_argument("--time-base", choices=("file_position", "embedded_timecode"))
    original.add_argument("--prepend-silence-duration", type=silence_duration)
    original.add_argument("--append-silence-duration", type=silence_duration)
    original.add_argument("--line-mode-drc-profile", choices=DRC_PROFILES)
    original.add_argument("--rf-mode-drc-profile", choices=DRC_PROFILES)
    original.add_argument("--loro-center-mix-level", choices=CENTER_MIX_LEVELS)
    original.add_argument("--loro-surround-mix-level", choices=SURROUND_MIX_LEVELS)
    original.add_argument("--ltrt-center-mix-level", choices=CENTER_MIX_LEVELS)
    original.add_argument("--ltrt-surround-mix-level", choices=SURROUND_MIX_LEVELS)
    original.add_argument(
        "--preferred-downmix-mode",
        choices=("loro", "ltrt"),
        help="Blu-ray-valid values; flat-7.1 wrapper default is ltrt",
    )
    original.add_argument("--surround-trim-5-1", choices=SURROUND_TRIMS)
    original.add_argument("--height-trim-5-1", choices=HEIGHT_TRIMS)
    original.add_argument("--clean-temp", type=parse_bool, metavar="{true,false}")
    original.add_argument("--temp-dir", type=Path)

    extended = parser.add_argument_group("wrapper extensions (in processing order)")
    extended.add_argument(
        "--custom-dialnorm",
        type=bounded_integer(-31, 0),
        metavar="-31..0",
        help="0 means do not override the measured dialnorm",
    )
    extended.add_argument(
        "--segmented-batch",
        action="store_true",
        help="enable N-point / N+1-job segmented batch encoding",
    )
    extended.add_argument(
        "--segment-start",
        choices=("first_frame_of_action", "file_start"),
        help="first segment start; file_start is emitted as XML frame number 0",
    )
    extended.add_argument(
        "--segment-point",
        action="append",
        default=[],
        metavar="HH:MM:SS:FF",
        help="repeat in ascending order; each point is passed unchanged to adjacent jobs",
    )
    extended.add_argument(
        "--compatibility-layout",
        choices=("5.1+2", "flat-7.1"),
        default="5.1+2",
        help="coded compatibility presentation (default: 5.1+2)",
    )

    operation = parser.add_argument_group("wrapper operation")
    operation.add_argument(
        "--license-file",
        type=Path,
        help="DEE license file; defaults to license.lic beside dee.exe and is staged through a safe path",
    )
    operation.add_argument("--overwrite", action="store_true", help="replace requested output files")
    operation.add_argument(
        "--dry-run",
        action="store_true",
        help="back up and validate the DEE component and generate XML, but do not patch or encode",
    )
    return parser


def resolve_dee(dee_argument: Path) -> tuple[Path, Path, Path]:
    supplied = dee_argument.expanduser().resolve()
    if supplied.is_dir():
        dee_dir = supplied
        dee_exe = dee_dir / "dee.exe"
    else:
        dee_exe = supplied
        dee_dir = dee_exe.parent
    if not dee_exe.is_file():
        raise WrapperError(f"DEE executable not found: {dee_exe}")
    component = dee_dir / PATCHED_COMPONENT
    if not component.is_file():
        raise WrapperError(f"DEE component not found: {component}")
    return dee_dir, dee_exe, component


def validate_segment_point(value: str, frame_rate: str) -> tuple[int, int, int, int]:
    match = SEGMENT_POINT_RE.fullmatch(value)
    if not match:
        raise WrapperError(f"invalid segment point {value!r}; expected HH:MM:SS:FF")
    fields = tuple(int(item) for item in match.groups())
    nominal_rate = int(float(frame_rate) + 0.999999)
    if fields[3] >= nominal_rate:
        raise WrapperError(
            f"invalid frame field in segment point {value!r}: {fields[3]} is not below {nominal_rate}"
        )
    return fields


def validate_arguments(args: argparse.Namespace) -> tuple[Path, list[Path]]:
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        raise WrapperError(f"input file not found: {input_path}")
    output_base = args.output.expanduser().resolve()
    if output_base == input_path:
        raise WrapperError("input and output paths must be different")

    if args.segmented_batch:
        if args.start is not None or args.end is not None:
            raise WrapperError("--start/--end cannot be combined with --segmented-batch")
        if args.timecode_frame_rate in (None, "not_indicated"):
            raise WrapperError("segmented batch requires an explicit --timecode-frame-rate")
        if args.time_base is None:
            raise WrapperError("segmented batch requires --time-base")
        if args.segment_start is None:
            raise WrapperError("segmented batch requires --segment-start")
        if not args.segment_point:
            raise WrapperError("segmented batch requires at least one --segment-point")
        keys = [validate_segment_point(point, args.timecode_frame_rate) for point in args.segment_point]
        if any(left >= right for left, right in zip(keys, keys[1:])):
            raise WrapperError("segment points must be unique and strictly ascending")
    elif args.segment_point or args.segment_start is not None:
        raise WrapperError("--segment-start/--segment-point require --segmented-batch")

    outputs = output_paths(output_base, len(args.segment_point) + 1 if args.segmented_batch else 1)
    for output in outputs:
        if output == input_path:
            raise WrapperError(f"generated output collides with input: {output}")
        if output.exists() and not args.overwrite:
            raise WrapperError(f"output already exists (use --overwrite): {output}")
        if output.exists() and output.is_dir():
            raise WrapperError(f"output path is a directory: {output}")
    return input_path, outputs


def resolve_license(args: argparse.Namespace, dee_dir: Path) -> Path | None:
    if args.license_file is not None:
        license_path = args.license_file.expanduser().resolve()
        if not license_path.is_file():
            raise WrapperError(f"DEE license file not found: {license_path}")
        return license_path
    adjacent = dee_dir / "license.lic"
    return adjacent if adjacent.is_file() else None


def needs_safe_runtime_stage(dee_dir: Path) -> bool:
    """Return true for paths DEE 5.2.1's own plugin loader may mishandle."""
    return os.name == "nt" and CONSERVATIVE_WINDOWS_PATH_RE.fullmatch(str(dee_dir)) is None


def stage_safe_runtime(dee_dir: Path, run_dir: Path) -> tuple[Path, Path, Path, int, int]:
    """Copy the executable-directory files to a conservative disposable path."""
    stage = run_dir / "dee-runtime"
    if stage.exists():
        raise WrapperError(f"safe DEE runtime stage already exists: {stage}")
    stage.mkdir()
    count = 0
    total_bytes = 0
    try:
        for source in sorted((path for path in dee_dir.iterdir() if path.is_file()), key=lambda path: path.name.casefold()):
            destination = stage / source.name
            shutil.copy2(source, destination)
            count += 1
            total_bytes += destination.stat().st_size
        staged_exe = stage / "dee.exe"
        staged_component = stage / PATCHED_COMPONENT
        if not staged_exe.is_file() or not staged_component.is_file():
            raise WrapperError("safe DEE runtime stage is missing dee.exe or the Atmos filter")
        if sha256_file(staged_component) != SUPPORTED_ORIGINAL_SHA256:
            raise WrapperError("safe DEE runtime stage component failed original-hash verification")
        return stage, staged_exe, staged_component, count, total_bytes
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def output_paths(base: Path, count: int) -> list[Path]:
    if count == 1:
        return [base]
    suffix = base.suffix
    stem = base.stem if suffix else base.name
    return [
        base.with_name(f"{stem}.part{index:03d}of{count:03d}{suffix}")
        for index in range(1, count + 1)
    ]


def _update_pe_checksum(data: bytearray) -> int:
    if data[:2] != b"MZ":
        raise WrapperError("target component is not a PE binary")
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise WrapperError("target component has no valid PE signature")
    checksum_offset = pe_offset + 4 + 20 + 64
    total = 0
    for index in range(0, len(data), 2):
        if checksum_offset <= index < checksum_offset + 4:
            word = 0
        elif index + 1 < len(data):
            word = data[index] | (data[index + 1] << 8)
        else:
            word = data[index]
        total += word
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    total = (total + len(data)) & 0xFFFFFFFF
    struct.pack_into("<I", data, checksum_offset, total)
    return total


def build_flat71_binary(original: bytes) -> bytes:
    actual_hash = sha256_bytes(original)
    if actual_hash != SUPPORTED_ORIGINAL_SHA256:
        raise WrapperError(
            "unsupported dee_audio_filter_ddp_atmos.dll; "
            f"expected SHA-256 {SUPPORTED_ORIGINAL_SHA256}, got {actual_hash}"
        )
    patched = bytearray(original)
    for offset, expected, replacement in FLAT71_PATCHES:
        actual = bytes(patched[offset : offset + len(expected)])
        if actual != expected:
            raise WrapperError(
                f"patch byte assertion failed at file offset 0x{offset:X}: "
                f"expected {expected.hex(' ')}, got {actual.hex(' ')}"
            )
        patched[offset : offset + len(replacement)] = replacement
    _update_pe_checksum(patched)
    result = bytes(patched)
    result_hash = sha256_bytes(result)
    if result_hash != EXPECTED_FLAT71_SHA256:
        raise WrapperError(
            f"internal patch verification failed: expected {EXPECTED_FLAT71_SHA256}, got {result_hash}"
        )
    return result


def _atomic_write_bytes(path: Path, data: bytes, metadata_source: Path | None = None) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if metadata_source is not None:
            shutil.copystat(metadata_source, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_copy(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextlib.contextmanager
def installation_lock(dee_dir: Path) -> Iterator[None]:
    lock_root = PRODUCT_DIR / "backups" / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    identity = hashlib.sha256(os.path.normcase(str(dee_dir)).encode("utf-8")).hexdigest()[:20]
    lock_path = lock_root / f"{identity}.lock"
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise WrapperError(f"another wrapper process is using this DEE installation: {dee_dir}") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise WrapperError(f"another wrapper process is using this DEE installation: {dee_dir}") from exc
        yield
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def ensure_component_backup(dee_dir: Path, component: Path) -> tuple[Path, bool]:
    identity = hashlib.sha256(os.path.normcase(str(dee_dir)).encode("utf-8")).hexdigest()[:20]
    backup_dir = PRODUCT_DIR / "backups" / identity
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / PATCHED_COMPONENT
    recovered = False

    current_hash = sha256_file(component)
    if current_hash == EXPECTED_FLAT71_SHA256:
        if not backup.is_file() or sha256_file(backup) != SUPPORTED_ORIGINAL_SHA256:
            raise WrapperError(
                "DEE component is already patched and no verified wrapper backup is available; "
                f"restore the original {PATCHED_COMPONENT} manually"
            )
        _atomic_copy(backup, component)
        recovered = True
        current_hash = sha256_file(component)

    if current_hash != SUPPORTED_ORIGINAL_SHA256:
        raise WrapperError(
            f"unsupported {PATCHED_COMPONENT}; expected original SHA-256 "
            f"{SUPPORTED_ORIGINAL_SHA256}, got {current_hash}"
        )

    if backup.exists():
        backup_hash = sha256_file(backup)
        if backup_hash != SUPPORTED_ORIGINAL_SHA256:
            raise WrapperError(f"existing backup failed verification: {backup}")
    else:
        _atomic_copy(component, backup)
        if sha256_file(backup) != SUPPORTED_ORIGINAL_SHA256:
            raise WrapperError(f"new backup failed verification: {backup}")

    manifest = {
        "schema_version": 1,
        "product": PRODUCT_NAME,
        "dee_directory": str(dee_dir),
        "component": PATCHED_COMPONENT,
        "original_sha256": SUPPORTED_ORIGINAL_SHA256,
        "backup": str(backup),
        "verified_at": utc_now(),
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return backup, recovered


def install_flat71_patch(component: Path) -> None:
    original = component.read_bytes()
    patched = build_flat71_binary(original)
    _atomic_write_bytes(component, patched, metadata_source=component)
    actual = sha256_file(component)
    if actual != EXPECTED_FLAT71_SHA256:
        raise WrapperError(f"installed patch failed verification: {actual}")


def restore_component(backup: Path, component: Path) -> None:
    if sha256_file(backup) != SUPPORTED_ORIGINAL_SHA256:
        raise WrapperError(f"refusing to restore from invalid backup: {backup}")
    last_error: OSError | None = None
    for attempt in range(20):
        try:
            _atomic_copy(backup, component)
            actual = sha256_file(component)
            if actual != SUPPORTED_ORIGINAL_SHA256:
                raise WrapperError(f"DEE component restoration failed verification: {actual}")
            return
        except OSError as exc:
            last_error = exc
            if attempt == 19:
                break
            # A terminated DEE process can keep its loaded filter mapped for a
            # short interval. Give Windows time to release that handle while
            # retaining the verified backup and mandatory hash check.
            time.sleep(0.25)
    assert last_error is not None
    raise WrapperError(f"DEE component restoration failed after retries: {last_error}") from last_error


def remove_path_with_retries(path: Path, *, recursive: bool = False) -> None:
    """Remove one wrapper-owned temporary path after transient handles close."""
    last_error: OSError | None = None
    for attempt in range(20):
        try:
            if recursive:
                shutil.rmtree(path)
            else:
                path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            if attempt == 19:
                break
            time.sleep(0.25)
    assert last_error is not None
    raise last_error


def parse_template() -> ET.ElementTree:
    if not TEMPLATE_PATH.is_file():
        raise WrapperError(f"bundled XML template is missing: {TEMPLATE_PATH}")
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(TEMPLATE_PATH, parser=parser)


def require_element(root: ET.Element, path: str) -> ET.Element:
    element = root.find(path)
    if element is None:
        raise WrapperError(f"bundled XML template is missing element: {path}")
    return element


def set_optional(root: ET.Element, path: str, value: object | None) -> None:
    if value is not None:
        require_element(root, path).text = str(value).lower() if isinstance(value, bool) else str(value)


def make_job_xml(
    args: argparse.Namespace,
    input_path: Path,
    encoded_output: Path,
    temp_dir: Path,
    start: str | None,
    end: str | None,
) -> ET.ElementTree:
    tree = parse_template()
    root = tree.getroot()

    require_element(root, "./input/audio/atmos_mezz/file_name").text = input_path.name
    require_element(root, "./input/audio/atmos_mezz/storage/local/path").text = str(input_path.parent)
    require_element(root, "./output/ec3/file_name").text = encoded_output.name
    require_element(root, "./output/ec3/storage/local/path").text = str(encoded_output.parent)
    require_element(root, "./misc/temp_dir/path").text = str(temp_dir)

    set_optional(root, "./input/audio/atmos_mezz/timecode_frame_rate", args.input_timecode_frame_rate)
    set_optional(root, "./input/audio/atmos_mezz/offset", args.input_offset)
    set_optional(root, "./input/audio/atmos_mezz/ffoa", args.input_ffoa)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/loudness/measure_only/metering_mode", args.metering_mode)
    set_optional(
        root,
        "./filter/audio/encode_to_atmos_ddp/loudness/measure_only/dialogue_intelligence",
        args.dialogue_intelligence,
    )
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/loudness/measure_only/speech_threshold", args.speech_threshold)
    require_element(root, "./filter/audio/encode_to_atmos_ddp/data_rate").text = str(args.data_rate)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/timecode_frame_rate", args.timecode_frame_rate)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/start", start if start is not None else args.start)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/end", end if end is not None else args.end)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/time_base", args.time_base)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/prepend_silence_duration", args.prepend_silence_duration)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/append_silence_duration", args.append_silence_duration)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/drc/line_mode_drc_profile", args.line_mode_drc_profile)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/drc/rf_mode_drc_profile", args.rf_mode_drc_profile)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/downmix/loro_center_mix_level", args.loro_center_mix_level)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/downmix/loro_surround_mix_level", args.loro_surround_mix_level)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/downmix/ltrt_center_mix_level", args.ltrt_center_mix_level)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/downmix/ltrt_surround_mix_level", args.ltrt_surround_mix_level)
    preferred = args.preferred_downmix_mode
    if preferred is None and args.compatibility_layout == "flat-7.1":
        preferred = "ltrt"
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/downmix/preferred_downmix_mode", preferred)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/custom_trims/surround_trim_5_1", args.surround_trim_5_1)
    set_optional(root, "./filter/audio/encode_to_atmos_ddp/custom_trims/height_trim_5_1", args.height_trim_5_1)
    set_optional(root, "./misc/temp_dir/clean_temp", args.clean_temp)

    encoder = require_element(root, "./filter/audio/encode_to_atmos_ddp")
    require_element(root, "./filter/audio/encode_to_atmos_ddp/encoding_backend").text = "atmosprocessor"
    require_element(root, "./filter/audio/encode_to_atmos_ddp/encoder_mode").text = "bluray"
    if args.custom_dialnorm is not None:
        custom_dialnorm = encoder.find("custom_dialnorm")
        if custom_dialnorm is None:
            # Keep the filter schema order: custom_trims, custom_dialnorm,
            # encoding_backend, encoder_mode.
            backend = require_element(root, "./filter/audio/encode_to_atmos_ddp/encoding_backend")
            custom_dialnorm = ET.Element("custom_dialnorm")
            encoder.insert(list(encoder).index(backend), custom_dialnorm)
        custom_dialnorm.text = str(args.custom_dialnorm)
    return tree


def write_xml(tree: ET.ElementTree, path: Path) -> None:
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True, short_empty_elements=False)


def plan_jobs(
    args: argparse.Namespace,
    input_path: Path,
    outputs: list[Path],
    run_dir: Path,
    temp_dir: Path,
) -> list[JobPlan]:
    count = len(outputs)
    xml_dir = run_dir / "jobs"
    encoded_dir = run_dir / "encoded"
    finalized_dir = run_dir / "finalized"
    log_dir = run_dir / "logs"
    for directory in (xml_dir, encoded_dir, log_dir, temp_dir):
        directory.mkdir(parents=True, exist_ok=True)
    if args.compatibility_layout == "flat-7.1":
        finalized_dir.mkdir(parents=True, exist_ok=True)

    if args.segmented_batch:
        first_start = "first_frame_of_action" if args.segment_start == "first_frame_of_action" else "0"
        starts: list[str | None] = [first_start, *args.segment_point]
        ends: list[str | None] = [*args.segment_point, "end_of_file"]
    else:
        starts = [None]
        ends = [None]

    plans: list[JobPlan] = []
    for zero_index, (final_output, start, end) in enumerate(zip(outputs, starts, ends)):
        index = zero_index + 1
        label = f"part{index:03d}of{count:03d}" if count > 1 else "single"
        encoded_output = encoded_dir / f"{label}.encoded.eb3"
        finalized_output = (
            finalized_dir / f"{label}.dsur-ex.eb3" if args.compatibility_layout == "flat-7.1" else None
        )
        xml_path = xml_dir / f"{label}.xml"
        tree = make_job_xml(args, input_path, encoded_output, temp_dir, start, end)
        write_xml(tree, xml_path)
        plans.append(
            JobPlan(
                index=index,
                count=count,
                start=start,
                end=end,
                final_output=final_output,
                encoded_output=encoded_output,
                finalized_output=finalized_output,
                xml_path=xml_path,
                dee_log_path=log_dir / f"{label}.dee.log",
                ex_log_path=log_dir / f"{label}.dsur-ex.log" if finalized_output else None,
            )
        )
    return plans


def run_logged(command: Sequence[str], cwd: Path, log_path: Path, label: str) -> None:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    process_encoding = locale.getpreferredencoding(False) if os.name == "nt" else "utf-8"
    with log_path.open("x", encoding="utf-8", newline="\n", buffering=1) as log:
        log.write(f"cwd: {cwd}\n")
        log.write(f"command: {subprocess.list2cmdline(list(command))}\n")
        log.flush()
        process = subprocess.Popen(
            list(command),
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=process_encoding,
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                log.write(line)
            returncode = process.wait()
        except BaseException:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=creationflags,
                )
            elif process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        finally:
            if process.stdout is not None:
                process.stdout.close()
        log.write(f"exit_code: {returncode}\n")
    if returncode != 0:
        raise CommandFailure(label, returncode)


def publish(source: Path, destination: Path, overwrite: bool) -> None:
    if not source.is_file() or source.stat().st_size == 0:
        raise WrapperError(f"refusing to publish missing or empty output: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        if destination.exists() and not overwrite:
            raise WrapperError(f"output appeared during encoding; refusing to overwrite: {destination}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def plan_record(plan: JobPlan) -> dict[str, object]:
    return {
        "index": plan.index,
        "count": plan.count,
        "start": plan.start,
        "end": plan.end,
        "job_xml": str(plan.xml_path),
        "encoded_output": str(plan.encoded_output),
        "finalized_output": str(plan.finalized_output) if plan.finalized_output else None,
        "requested_output": str(plan.final_output),
        "dee_log": str(plan.dee_log_path),
        "dsur_ex_log": str(plan.ex_log_path) if plan.ex_log_path else None,
    }


def execute(args: argparse.Namespace) -> int:
    dee_dir, dee_exe, component = resolve_dee(args.dee)
    input_path, outputs = validate_arguments(args)
    license_source = resolve_license(args, dee_dir)
    if not DSUR_EX_PATCHER.is_file():
        raise WrapperError(f"bundled independent Surround EX patcher is missing: {DSUR_EX_PATCHER}")

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{uuid.uuid4().hex[:8]}"
    run_dir = PRODUCT_DIR / "work" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    temp_dir = args.temp_dir.expanduser().resolve() if args.temp_dir else run_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    plans = plan_jobs(args, input_path, outputs, run_dir, temp_dir)
    manifest_path = run_dir / "run.json"
    manifest: dict[str, object] = {
        "schema_version": 1,
        "product": PRODUCT_NAME,
        "product_version": VERSION,
        "started_at": utc_now(),
        "status": "preflight",
        "dee_directory": str(dee_dir),
        "dee_executable": str(dee_exe),
        "component": str(component),
        "input": str(input_path),
        "compatibility_layout": args.compatibility_layout,
        "data_rate": args.data_rate,
        "encoding_backend": "atmosprocessor",
        "encoder_mode": "bluray",
        "segmented_batch": args.segmented_batch,
        "jobs": [plan_record(plan) for plan in plans],
        "dry_run": args.dry_run,
    }
    backup: Path | None = None
    staged_license: Path | None = None
    runtime_stage: Path | None = None
    execution_dee_dir = dee_dir
    execution_dee_exe = dee_exe
    execution_component = component
    restore_required = False
    primary_error: BaseException | None = None

    with installation_lock(dee_dir):
        try:
            backup, recovered = ensure_component_backup(dee_dir, component)
            manifest["backup"] = str(backup)
            manifest["recovered_stale_patch"] = recovered
            manifest["original_component_sha256"] = sha256_file(component)
            # Validate the patch recipe even for 5.1+2 and dry runs.
            build_flat71_binary(component.read_bytes())
            manifest["status"] = "prepared"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            print(f"Run directory: {run_dir}")
            print(f"Verified backup: {backup}")
            print(f"Generated {len(plans)} DEE job XML file(s).")
            if args.dry_run:
                manifest["status"] = "dry-run-complete"
                print("Dry run complete; DEE was not patched or started.")
                return 0

            if needs_safe_runtime_stage(dee_dir):
                (
                    runtime_stage,
                    execution_dee_exe,
                    execution_component,
                    staged_file_count,
                    staged_total_bytes,
                ) = stage_safe_runtime(dee_dir, run_dir)
                execution_dee_dir = runtime_stage
                manifest["safe_runtime_stage"] = str(runtime_stage)
                manifest["safe_runtime_file_count"] = staged_file_count
                manifest["safe_runtime_total_bytes"] = staged_total_bytes
                print(
                    "DEE path needs a conservative execution stage; "
                    f"copied {staged_file_count} runtime file(s) to {runtime_stage}."
                )

            if license_source is not None:
                # DEE 5.2.1 cannot open a license whose own pathname contains
                # some otherwise Windows-valid characters. Stage the bytes in
                # the wrapper's conservative run path, then pass -l explicitly.
                staged_license = run_dir / "dee-license.lic"
                shutil.copy2(license_source, staged_license)
                if sha256_file(staged_license) != sha256_file(license_source):
                    raise WrapperError("staged DEE license failed verification")
                manifest["license_source"] = str(license_source)
                manifest["license_staged"] = True

            if args.compatibility_layout == "flat-7.1":
                # From this point onward, restoration is mandatory even if the
                # atomic install returns an unexpected post-write error.
                restore_required = True
                install_flat71_patch(execution_component)
                manifest["patched_component_sha256"] = sha256_file(execution_component)
                manifest["status"] = "encoding-flat-7.1"
                print("Installed validated P2+P3 patch for flat-7.1 encoding.")
            else:
                manifest["status"] = "encoding-5.1+2"
                print("Using the verified original DEE component for 5.1+2 encoding.")

            for plan in plans:
                print(f"[{plan.index}/{plan.count}] DEE encode: {plan.final_output.name}")
                command = [str(execution_dee_exe)]
                if staged_license is not None:
                    command.extend(["--license-file", str(staged_license)])
                # Match the original DEE example-flow invocation. DEE 5.2.1's
                # XML local-storage parser can truncate a path at its first
                # space, while the corresponding quoted CLI overrides retain
                # the complete path. The XML remains fully populated as the
                # auditable job definition; these options make it executable.
                command.extend(
                    [
                        "-x",
                        str(plan.xml_path),
                        "-a",
                        str(input_path),
                        "-o",
                        str(plan.encoded_output),
                        "--temp",
                        str(temp_dir),
                    ]
                )
                run_logged(
                    command,
                    execution_dee_dir,
                    plan.dee_log_path,
                    f"DEE job {plan.index}/{plan.count}",
                )
                if not plan.encoded_output.is_file() or plan.encoded_output.stat().st_size == 0:
                    raise WrapperError(f"DEE reported success but produced no non-empty stream: {plan.encoded_output}")
        except BaseException as exc:
            primary_error = exc
            manifest["status"] = "failed"
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            restore_failure: BaseException | None = None
            if restore_required:
                try:
                    assert backup is not None
                    restore_component(backup, execution_component)
                    restore_required = False
                    manifest["restored_component_sha256"] = sha256_file(execution_component)
                    manifest["source_component_sha256_after_run"] = sha256_file(component)
                    print("Restored and verified the original DEE component.")
                except BaseException as restore_error:
                    restore_failure = restore_error
                    manifest["status"] = "restore-failed"
                    manifest["restore_error"] = f"{type(restore_error).__name__}: {restore_error}"
                    if primary_error is not None:
                        print(f"CRITICAL: DEE restoration also failed: {restore_error}", file=sys.stderr)
            if staged_license is not None and staged_license.exists():
                try:
                    remove_path_with_retries(staged_license)
                    manifest["license_stage_removed"] = True
                except OSError as license_cleanup_error:
                    manifest["license_cleanup_warning"] = str(license_cleanup_error)
            if runtime_stage is not None and runtime_stage.exists():
                try:
                    remove_path_with_retries(runtime_stage, recursive=True)
                    manifest["safe_runtime_stage_removed"] = True
                except OSError as runtime_cleanup_error:
                    manifest["runtime_cleanup_warning"] = str(runtime_cleanup_error)
            manifest["updated_at"] = utc_now()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if restore_failure is not None and primary_error is None:
                raise restore_failure

    try:
        if args.compatibility_layout == "flat-7.1":
            manifest["status"] = "setting-surround-ex"
            for plan in plans:
                assert plan.finalized_output is not None and plan.ex_log_path is not None
                print(f"[{plan.index}/{plan.count}] Surround EX finalization: {plan.final_output.name}")
                run_logged(
                    [sys.executable, str(DSUR_EX_PATCHER), str(plan.encoded_output), str(plan.finalized_output)],
                    PRODUCT_DIR,
                    plan.ex_log_path,
                    f"Surround EX finalization {plan.index}/{plan.count}",
                )

        manifest["status"] = "publishing"
        for plan in plans:
            source = plan.finalized_output or plan.encoded_output
            publish(source, plan.final_output, args.overwrite)
            print(f"Wrote: {plan.final_output}")

        manifest["status"] = "complete"
        manifest["completed_at"] = utc_now()
        manifest["outputs"] = [
            {"path": str(path), "size": path.stat().st_size, "sha256": sha256_file(path)} for path in outputs
        ]
    except BaseException as exc:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        manifest["updated_at"] = utc_now()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except KeyboardInterrupt:
        print("wrapper interrupted", file=sys.stderr)
        return 130
    except CommandFailure as exc:
        print(f"wrapper error: {exc}", file=sys.stderr)
        return exc.returncode if 0 < exc.returncode < 256 else 1
    except WrapperError as exc:
        print(f"wrapper error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"wrapper internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
