from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from common import file_record, utc_now, write_json
from stream_validation import _ac3_header, _eac3_header, scan_frames


CHANNELS_5_1 = ("L", "R", "C", "LFE", "Ls", "Rs")


def extract_ac3_core(data: bytes) -> tuple[bytes, dict[str, int]]:
    """Return concatenated AC-3 frames from an interleaved Blu-ray DD+ stream."""
    offset = 0
    core = bytearray()
    ac3_frames = 0
    eac3_frames = 0
    while offset < len(data):
        header = _ac3_header(data, offset) or _eac3_header(data, offset)
        if header is None:
            raise ValueError(f"unsupported frame at byte offset {offset}")
        frame_size = int(header["frame_size"])
        if frame_size <= 0 or offset + frame_size > len(data):
            raise ValueError(f"truncated frame at byte offset {offset}: size={frame_size}")
        if header["kind"] == "ac3":
            core.extend(data[offset : offset + frame_size])
            ac3_frames += 1
        else:
            eac3_frames += 1
        offset += frame_size
    return bytes(core), {
        "ac3_frames": ac3_frames,
        "eac3_frames": eac3_frames,
        "input_bytes": len(data),
        "core_bytes": len(core),
    }


def _ffmpeg_path(explicit: Path | None) -> Path:
    if explicit is not None:
        resolved = explicit.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        return resolved
    discovered = shutil.which("ffmpeg")
    if not discovered:
        raise FileNotFoundError("ffmpeg is not available on PATH; pass --ffmpeg")
    return Path(discovered).resolve()


def decode_core(ffmpeg: Path, core_path: Path, sample_rate: int) -> tuple[np.ndarray, dict[str, Any]]:
    command = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel", "error",
        "-f", "ac3",
        "-i", str(core_path),
        "-map", "0:a:0",
        "-ac", str(len(CHANNELS_5_1)),
        "-ar", str(sample_rate),
        "-c:a", "pcm_f32le",
        "-f", "f32le",
        "pipe:1",
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg core decode failed ({completed.returncode}): {stderr}")
    flat = np.frombuffer(completed.stdout, dtype="<f4")
    if flat.size % len(CHANNELS_5_1):
        raise ValueError(f"decoded sample count is not divisible by {len(CHANNELS_5_1)}")
    samples = flat.reshape((-1, len(CHANNELS_5_1)))
    return samples, {
        "command": command,
        "returncode": completed.returncode,
        "stderr": completed.stderr.decode("utf-8", errors="replace"),
        "sample_rate": sample_rate,
        "channels": list(CHANNELS_5_1),
        "samples_per_channel": int(samples.shape[0]),
        "duration_seconds": samples.shape[0] / sample_rate,
    }


def _db(value: float, floor: float = -160.0) -> float:
    if value <= 0:
        return floor
    return max(floor, 20.0 * math.log10(value))


def _tone_measurement(samples: np.ndarray, frequency: float, sample_rate: int) -> tuple[float, float]:
    count = samples.shape[0]
    phase = np.exp(-2j * np.pi * frequency * np.arange(count, dtype=np.float64) / sample_rate)
    coefficient = (2.0 / count) * np.dot(samples.astype(np.float64, copy=False), phase)
    return float(abs(coefficient)), float(np.degrees(np.angle(coefficient)))


def _wrap_phase_degrees(value: float) -> float:
    return ((value + 180.0) % 360.0) - 180.0


def analyze_schedule(
    samples: np.ndarray,
    schedule: list[dict[str, Any]],
    *,
    sample_rate: int,
    guard_seconds: float,
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for event in schedule:
        start_seconds = float(event["start_seconds"]) + guard_seconds
        end_seconds = float(event["end_seconds"]) - guard_seconds
        if end_seconds <= start_seconds:
            raise ValueError(f"guard leaves no samples for event {event['label']}")
        start = max(0, round(start_seconds * sample_rate))
        end = min(samples.shape[0], round(end_seconds * sample_rate))
        segment = samples[start:end]
        if segment.size == 0:
            raise ValueError(f"decoded core does not cover event {event['label']}")
        frequency = float(event["frequency_hz"])
        channels: dict[str, dict[str, float]] = {}
        for index, channel in enumerate(CHANNELS_5_1):
            channel_samples = segment[:, index]
            rms = float(np.sqrt(np.mean(np.square(channel_samples.astype(np.float64, copy=False)))))
            tone_amplitude, tone_phase = _tone_measurement(channel_samples, frequency, sample_rate)
            channels[channel] = {
                "rms_dbfs": round(_db(rms), 3),
                "tone_amplitude_dbfs": round(_db(tone_amplitude), 3),
                "tone_phase_degrees": round(tone_phase, 3),
            }
        dominant = sorted(
            CHANNELS_5_1,
            key=lambda name: channels[name]["tone_amplitude_dbfs"],
            reverse=True,
        )
        ls = channels["Ls"]
        rs = channels["Rs"]
        phase_delta = ((rs["tone_phase_degrees"] - ls["tone_phase_degrees"] + 180.0) % 360.0) - 180.0
        report.append({
            "label": event["label"],
            "source_kind": event["kind"],
            "frequency_hz": frequency,
            "analysis_window_seconds": [start_seconds, end_seconds],
            "channels": channels,
            "dominant_tone_channels": dominant[:3],
            "surround_pair": {
                "ls_tone_dbfs": ls["tone_amplitude_dbfs"],
                "rs_tone_dbfs": rs["tone_amplitude_dbfs"],
                "weaker_to_stronger_db": round(
                    min(ls["tone_amplitude_dbfs"], rs["tone_amplitude_dbfs"])
                    - max(ls["tone_amplitude_dbfs"], rs["tone_amplitude_dbfs"]),
                    3,
                ),
                "rs_minus_ls_phase_degrees": round(phase_delta, 3),
            },
        })
    return report


def summarize_surround_matrix(
    events: list[dict[str, Any]],
    *,
    coefficient_tolerance_db: float = 0.75,
    phase_tolerance_degrees: float = 10.0,
) -> dict[str, Any]:
    selected = {
        event["label"]: event["surround_pair"]
        for event in events
        if event["label"] in {"Lss", "Rss", "Lrs", "Rrs"}
    }
    required = {"Lss", "Rss", "Lrs", "Rrs"}
    coefficient_checks: list[dict[str, Any]] = []
    if required.issubset(selected):
        references = {
            "Lrs_to_Ls": (selected["Lrs"]["ls_tone_dbfs"], selected["Lss"]["ls_tone_dbfs"], -1.2),
            "Lrs_to_Rs": (selected["Lrs"]["rs_tone_dbfs"], selected["Lss"]["ls_tone_dbfs"], -6.2),
            "Rrs_to_Ls": (selected["Rrs"]["ls_tone_dbfs"], selected["Rss"]["rs_tone_dbfs"], -6.2),
            "Rrs_to_Rs": (selected["Rrs"]["rs_tone_dbfs"], selected["Rss"]["rs_tone_dbfs"], -1.2),
        }
        for name, (observed_level, reference_level, expected) in references.items():
            observed = observed_level - reference_level
            error = observed - expected
            coefficient_checks.append({
                "name": name,
                "expected_db": expected,
                "observed_db": round(observed, 3),
                "error_db": round(error, 3),
                "within_tolerance": abs(error) <= coefficient_tolerance_db,
            })
        phase_checks = [
            abs(float(selected[label]["rs_minus_ls_phase_degrees"])) <= phase_tolerance_degrees
            for label in ("Lrs", "Rrs")
        ]
        coefficients_match = all(check["within_tolerance"] for check in coefficient_checks)
        phases_match = all(phase_checks)
        verdict = (
            "matches_dolby_pliix_7_1_to_5_1_coefficients"
            if coefficients_match and phases_match
            else "does_not_match_dolby_pliix_7_1_to_5_1_coefficients"
        )
    else:
        coefficients_match = False
        phases_match = False
        verdict = "inconclusive_missing_surround_events"
    return {
        "verdict": verdict,
        "events": selected,
        "reference_equations": [
            "Ls = Lss + (-1.2 dB x Lrs) + (-6.2 dB x Rrs)",
            "Rs = Rss + (-6.2 dB x Lrs) + (-1.2 dB x Rrs)",
        ],
        "coefficient_tolerance_db": coefficient_tolerance_db,
        "phase_tolerance_degrees": phase_tolerance_degrees,
        "coefficient_checks": coefficient_checks,
        "coefficients_match": coefficients_match,
        "rear_pair_phases_match": phases_match,
        "method_note": (
            "Observed rear coefficients are normalized to the corresponding isolated Lss/Rss event, "
            "whose generated source amplitude is identical. The phase check expects the positive-sum "
            "polarity shown by the reference equations."
        ),
    }


def summarize_surround_phase_shift(
    events: list[dict[str, Any]],
    *,
    sample_rate: int,
    reference_labels: tuple[str, ...] = ("L", "R", "C"),
    surround_labels: tuple[str, ...] = ("Lss", "Rss", "Lrs", "Rrs"),
    phase_tolerance_degrees: float = 10.0,
) -> dict[str, Any]:
    """Detect a common +/-90-degree shift on surround-coded identification tones.

    The generated source tones are zero-phase sines on the absolute file time
    axis. L/R/C establish the integer-sample codec delay, after which the
    residual phase of the isolated surround events can be measured directly.
    """
    by_label = {str(event["label"]): event for event in events}
    missing_references = [label for label in reference_labels if label not in by_label]
    missing_surrounds = [label for label in surround_labels if label not in by_label]
    if missing_references or missing_surrounds:
        return {
            "verdict": "inconclusive_missing_phase_events",
            "missing_reference_events": missing_references,
            "missing_surround_events": missing_surrounds,
            "surround_90_degree_phase_shift_observed": False,
        }

    def raw_residual(event: dict[str, Any]) -> tuple[float, float, str]:
        frequency = float(event["frequency_hz"])
        start_seconds = float(event["analysis_window_seconds"][0])
        channel = str(event["dominant_tone_channels"][0])
        output_phase = float(event["channels"][channel]["tone_phase_degrees"])
        # The Fourier coefficient of sin(wt) is at -90 degrees.
        source_phase = _wrap_phase_degrees(360.0 * frequency * start_seconds - 90.0)
        return frequency, _wrap_phase_degrees(output_phase - source_phase), channel

    references = [raw_residual(by_label[label]) for label in reference_labels]
    candidate_limit = max(1, sample_rate // 2)
    delay_samples = min(
        range(candidate_limit + 1),
        key=lambda candidate: sum(
            _wrap_phase_degrees(residual + 360.0 * frequency * candidate / sample_rate) ** 2
            for frequency, residual, _channel in references
        ),
    )

    def compensated_record(label: str) -> dict[str, Any]:
        frequency, residual, channel = raw_residual(by_label[label])
        compensated = _wrap_phase_degrees(
            residual + 360.0 * frequency * delay_samples / sample_rate
        )
        return {
            "label": label,
            "frequency_hz": frequency,
            "coded_channel": channel,
            "phase_after_delay_compensation_degrees": round(compensated, 3),
        }

    reference_records = [compensated_record(label) for label in reference_labels]
    surround_records = [compensated_record(label) for label in surround_labels]
    reference_rms = math.sqrt(sum(
        float(record["phase_after_delay_compensation_degrees"]) ** 2
        for record in reference_records
    ) / len(reference_records))
    surround_values = [
        float(record["phase_after_delay_compensation_degrees"])
        for record in surround_records
    ]
    negative_90_errors = [_wrap_phase_degrees(value + 90.0) for value in surround_values]
    positive_90_errors = [_wrap_phase_degrees(value - 90.0) for value in surround_values]
    negative_90_max_error = max(abs(value) for value in negative_90_errors)
    positive_90_max_error = max(abs(value) for value in positive_90_errors)
    observed_sign = -90.0 if negative_90_max_error <= positive_90_max_error else 90.0
    max_error = min(negative_90_max_error, positive_90_max_error)
    observed = max_error <= phase_tolerance_degrees
    return {
        "verdict": (
            "surround_90_degree_phase_shift_observed"
            if observed
            else "surround_90_degree_phase_shift_not_observed"
        ),
        "surround_90_degree_phase_shift_observed": observed,
        "observed_shift_degrees": observed_sign if observed else None,
        "phase_tolerance_degrees": phase_tolerance_degrees,
        "maximum_surround_error_degrees": round(max_error, 3),
        "estimated_common_delay_samples": delay_samples,
        "estimated_common_delay_seconds": delay_samples / sample_rate,
        "reference_phase_rms_degrees": round(reference_rms, 3),
        "reference_events": reference_records,
        "surround_events": surround_records,
        "method_note": (
            "The generated tones are absolute-time zero-phase sines. Integer-sample delay is fitted "
            "only from direct L/R/C events, then applied unchanged to Lss/Rss/Lrs/Rrs."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract and measure the 5.1 AC-3 core of a Blu-ray DD+ Atmos identification stream."
    )
    parser.add_argument("stream", type=Path)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--guard-seconds", type=float, default=0.25)
    args = parser.parse_args()

    stream = args.stream.resolve()
    schedule_path = args.schedule.resolve()
    output_dir = args.output_dir.resolve()
    if not stream.is_file():
        raise FileNotFoundError(stream)
    if not schedule_path.is_file():
        raise FileNotFoundError(schedule_path)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite analysis directory: {output_dir}")
    output_dir.mkdir(parents=True)

    data = stream.read_bytes()
    frame_scan = scan_frames(stream)
    if frame_scan.get("status") != "valid":
        raise ValueError(f"input is not a valid interleaved stream: {frame_scan.get('error')}")
    core, extraction = extract_ac3_core(data)
    core_path = output_dir / f"{stream.stem}.core.ac3"
    core_path.write_bytes(core)

    ffmpeg = _ffmpeg_path(args.ffmpeg)
    decoded, decode = decode_core(ffmpeg, core_path, args.sample_rate)
    schedule_document = json.loads(schedule_path.read_text(encoding="utf-8"))
    events = analyze_schedule(
        decoded,
        schedule_document["schedule"],
        sample_rate=args.sample_rate,
        guard_seconds=args.guard_seconds,
    )
    report = {
        "generated_at": utc_now(),
        "scope": "5.1 AC-3 compatibility-core signal analysis for a DD+ 7.1 Atmos stream",
        "stream": file_record(stream),
        "schedule": file_record(schedule_path),
        "core": file_record(core_path),
        "frame_scan": frame_scan,
        "extraction": extraction,
        "decode": decode,
        "matrix_screen": summarize_surround_matrix(events),
        "phase_shift_screen": summarize_surround_phase_shift(
            events,
            sample_rate=args.sample_rate,
        ),
        "events": events,
        "limitations": [
            "The measurement validates the documented fixed 7.1-to-5.1 PLIIx coefficients on isolated surround tones.",
            "A full listening or decoder test is still useful for end-to-end playback interoperability.",
            "The AC-3 dsurexmod flag is metadata and is intentionally not treated as proof of matrix processing.",
        ],
    }
    report_path = output_dir / "analysis.json"
    write_json(report_path, report)
    print(json.dumps({
        "report": str(report_path),
        "core": str(core_path),
        "matrix_screen": report["matrix_screen"],
        "phase_shift_screen": report["phase_shift_screen"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
