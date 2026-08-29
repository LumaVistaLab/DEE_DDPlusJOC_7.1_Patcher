from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from common import (
    REPO_ROOT,
    file_record,
    find_case,
    load_config,
    manifest_changes,
    repo_path,
    reserve_unique_paths,
    sha256_file,
    tree_manifest,
    utc_now,
    write_json,
)
from stream_validation import validate_stream


def _case_repo_path(config: dict[str, Any], case: dict[str, Any], key: str, *, must_exist: bool) -> Path:
    value = case.get(key, config["paths"][key])
    return repo_path(value, must_exist=must_exist)


def _runtime_state(source: Path) -> tuple[str, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    for path in sorted((item for item in source.rglob("*") if item.is_file()), key=lambda p: p.as_posix().lower()):
        stat = path.stat()
        records.append({
            "relative_path": path.relative_to(source).as_posix(),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        })
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), records


def prepare_runtime(config: dict[str, Any], candidate: Path) -> tuple[Path, dict[str, Any]]:
    paths = config["paths"]
    source = repo_path(paths["runtime_source"], must_exist=True)
    work_root = repo_path(paths["work_dir"])
    state_hash, source_records = _runtime_state(source)
    stage = work_root / f"runtime_{state_hash[:12]}"
    marker = stage / ".automation-runtime.json"

    if not marker.exists():
        if stage.exists():
            raise RuntimeError(f"incomplete runtime stage exists; refusing to reuse it: {stage}")
        stage.parent.mkdir(parents=True, exist_ok=True)
        print(f"creating disposable runtime copy ({len(source_records)} files): {stage}", flush=True)
        shutil.copytree(source, stage, copy_function=shutil.copy2)
        write_json(marker, {
            "created_at": utc_now(),
            "source": str(source),
            "source_state_sha256": state_hash,
            "source_files": source_records,
        })
    else:
        marker_data = json.loads(marker.read_text(encoding="utf-8"))
        if marker_data.get("source_state_sha256") != state_hash:
            raise RuntimeError(f"runtime stage marker mismatch: {stage}")

    target = stage / paths["runtime_target_dll"]
    shutil.copy2(candidate, target)
    candidate_hash = sha256_file(candidate)
    installed_hash = sha256_file(target)
    if installed_hash != candidate_hash:
        raise RuntimeError(f"candidate DLL copy verification failed: {target}")
    runtime_exe = stage / paths["runtime_exe"]
    if not runtime_exe.is_file():
        raise FileNotFoundError(runtime_exe)
    return runtime_exe, {
        "stage": str(stage),
        "source_state_sha256": state_hash,
        "installed_dll": file_record(target),
        "runtime_exe": file_record(runtime_exe),
    }


def preflight(config: dict[str, Any], case: dict[str, Any], *, allow_gated: bool) -> dict[str, Any]:
    paths = config["paths"]
    original = repo_path(paths["original_dll"], must_exist=True)
    candidate = repo_path(case["candidate_dll"], must_exist=True)
    workflow = _case_repo_path(config, case, "workflow_xml", must_exist=True)
    input_audio = _case_repo_path(config, case, "input_audio", must_exist=True)
    runtime_source = repo_path(paths["runtime_source"], must_exist=True)
    temp_dir = Path(paths["temp_dir"])

    original_hash = sha256_file(original)
    if original_hash != config["expected_original_sha256"]:
        raise RuntimeError(
            f"unsupported original DLL: expected {config['expected_original_sha256']}, got {original_hash}"
        )
    candidate_hash = sha256_file(candidate)
    if candidate_hash != case["expected_sha256"]:
        raise RuntimeError(
            f"candidate hash mismatch for {case['id']}: expected {case['expected_sha256']}, got {candidate_hash}"
        )
    input_record = file_record(input_audio)
    expected_input_hash = case.get("expected_input_sha256")
    if expected_input_hash and input_record["sha256"] != expected_input_hash:
        raise RuntimeError(
            f"input hash mismatch for {case['id']}: expected {expected_input_hash}, "
            f"got {input_record['sha256']}"
        )
    if case.get("gated") and not allow_gated:
        raise PermissionError(case.get("gate_reason", f"case {case['id']} is gated"))
    if not (runtime_source / paths["runtime_exe"]).is_file():
        raise FileNotFoundError(runtime_source / paths["runtime_exe"])
    if not temp_dir.is_dir():
        raise FileNotFoundError(f"DEE temporary directory does not exist: {temp_dir}")

    return {
        "checked_at": utc_now(),
        "case": case["id"],
        "scope": config["scope"],
        "original_dll": file_record(original),
        "candidate_dll": file_record(candidate),
        "workflow_xml": file_record(workflow),
        "input_audio": input_record,
        "runtime_source": str(runtime_source),
        "temp_dir": str(temp_dir),
        "temp_dir_exists": True,
        "gate_override": bool(allow_gated and case.get("gated")),
    }


def _kill_process(proc: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    if proc.poll() is None:
        proc.kill()


def capture_process(command: list[str], cwd: Path, log_path: Path, timeout_seconds: float) -> dict[str, Any]:
    start = time.monotonic()
    timed_out = False
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    command_line = subprocess.list2cmdline(command)

    with log_path.open("x", encoding="utf-8", newline="\n", buffering=1) as log:
        log.write(f"{cwd}>{command_line}\n")
        log.flush()
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )

        def pump() -> None:
            assert proc.stdout is not None
            for line in proc.stdout:
                log.write(line)
                log.flush()

        reader = threading.Thread(target=pump, name="dee-log-pump", daemon=True)
        reader.start()
        try:
            return_code = proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process(proc)
            return_code = proc.wait(timeout=30)
        reader.join(timeout=30)
        if proc.stdout is not None:
            proc.stdout.close()
        elapsed = time.monotonic() - start
        if timed_out:
            log.write(f"Automation timeout after {timeout_seconds:g} seconds.\n")
        log.write(f"Time elapsed: {elapsed:.4f} seconds\n")
        if return_code != 0:
            log.write(f"Application exits with error code: {return_code}\n")
        log.flush()

    return {
        "command": command,
        "command_line": command_line,
        "cwd": str(cwd),
        "returncode": return_code,
        "timed_out": timed_out,
        "elapsed_seconds": elapsed,
    }


def _allocated_case_paths(config: dict[str, Any], case: dict[str, Any], rerun: bool) -> tuple[Path, Path, Path, str]:
    output = repo_path(config["paths"]["results_dir"]) / case["output_name"]
    log = repo_path(config["paths"]["logs_dir"]) / case["log_name"]
    evidence = repo_path(config["paths"]["evidence_dir"]) / "runs" / case["id"]
    return reserve_unique_paths(output, log, evidence, rerun=rerun)


def run_case(
    config: dict[str, Any],
    case: dict[str, Any],
    *,
    allow_gated: bool,
    rerun: bool,
    timeout_seconds: float,
) -> int:
    preflight_report = preflight(config, case, allow_gated=allow_gated)
    output_path, log_path, evidence_dir, suffix = _allocated_case_paths(config, case, rerun)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=False)

    # Reserve the declared result before DEE starts. It is intentionally retained
    # even if DEE crashes before writing a single byte.
    with output_path.open("xb"):
        pass

    example_root = repo_path("example-flow", must_exist=True)
    print("hashing example-flow before the run (read-only integrity guard)", flush=True)
    example_before = tree_manifest(example_root, hash_files=True)
    candidate = repo_path(case["candidate_dll"], must_exist=True)
    process_report: dict[str, Any] | None = None
    validation_report: dict[str, Any] | None = None
    runtime_report: dict[str, Any] | None = None
    exception: str | None = None
    try:
        runtime_exe, runtime_report = prepare_runtime(config, candidate)
        run_cwd = repo_path(config["paths"]["work_dir"]) / "runs" / f"{case['id']}{suffix}"
        run_cwd.mkdir(parents=True, exist_ok=False)
        workflow = _case_repo_path(config, case, "workflow_xml", must_exist=True)
        input_audio = _case_repo_path(config, case, "input_audio", must_exist=True)
        command = [
            str(runtime_exe),
            "-x", str(workflow),
            "-a", str(input_audio),
            "-o", str(output_path),
            "--temp", str(Path(config["paths"]["temp_dir"])),
        ]
        process_report = capture_process(command, run_cwd, log_path, timeout_seconds)
        validation_report = validate_stream(output_path, evidence_dir / "stream")
    except Exception as exc:
        exception = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        if not output_path.exists():
            with output_path.open("xb"):
                pass
        print("hashing example-flow after the run (read-only integrity guard)", flush=True)
        example_after = tree_manifest(example_root, hash_files=True)
        changes = manifest_changes(example_before, example_after)
        run_report = {
            "generated_at": utc_now(),
            "scope": config["scope"],
            "case": case,
            "suffix": suffix,
            "preflight": preflight_report,
            "runtime": runtime_report,
            "process": process_report,
            "output": file_record(output_path),
            "log": file_record(log_path) if log_path.exists() else None,
            "validation_summary": {
                "classification": validation_report.get("classification") if validation_report else None,
                "frame_scan": validation_report.get("frame_scan") if validation_report else None,
            },
            "example_flow": {
                "before": example_before,
                "after": example_after,
                "changes": changes,
                "unchanged": not changes,
            },
            "exception": exception,
        }
        write_json(evidence_dir / "run.json", run_report)

    if changes:
        raise RuntimeError(f"example-flow integrity violation: {changes}")
    assert process_report is not None
    verdict = (validation_report or {}).get("classification", {}).get("verdict")
    print(f"log: {log_path}")
    print(f"output: {output_path} ({output_path.stat().st_size} bytes)")
    print(f"validation: {verdict}")
    print(f"evidence: {evidence_dir}")
    return int(process_report["returncode"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated DEE flat-7.1 test runner")
    parser.add_argument("--config", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list")
    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("case")
    preflight_parser.add_argument("--allow-gated", action="store_true")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("case")
    run_parser.add_argument("--allow-gated", action="store_true")
    run_parser.add_argument("--rerun", action="store_true")
    run_parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.command == "list":
        for case in config["cases"]:
            gate = "gated" if case.get("gated") else "ready"
            print(f"{case['id']}: {gate} -> {case['candidate_dll']}")
        return 0

    case = find_case(config, args.case)
    if args.command == "preflight":
        report = preflight(config, case, allow_gated=args.allow_gated)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    return run_case(
        config,
        case,
        allow_gated=args.allow_gated,
        rerun=args.rerun,
        timeout_seconds=args.timeout,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"automation error: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
