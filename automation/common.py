from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


AUTOMATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = AUTOMATION_DIR.parent
DEFAULT_CONFIG = AUTOMATION_DIR / "config" / "cases.json"
CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def timestamp_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, *, hash_file: bool = True) -> dict[str, Any]:
    stat = path.stat()
    record: dict[str, Any] = {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if hash_file:
        record["sha256"] = sha256_file(path)
    return record


def tree_manifest(root: Path, *, hash_files: bool = True) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda p: p.as_posix().lower()):
        stat = path.stat()
        record: dict[str, Any] = {
            "relative_path": path.relative_to(root).as_posix(),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
        if hash_files:
            record["sha256"] = sha256_file(path)
        records.append(record)
    return records


def manifest_changes(before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    old = {item["relative_path"]: item for item in before}
    new = {item["relative_path"]: item for item in after}
    changes: list[dict[str, Any]] = []
    for name in sorted(set(old) | set(new)):
        if name not in old:
            changes.append({"path": name, "change": "added", "after": new[name]})
        elif name not in new:
            changes.append({"path": name, "change": "removed", "before": old[name]})
        elif old[name] != new[name]:
            changes.append({"path": name, "change": "modified", "before": old[name], "after": new[name]})
    return changes


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = (path or DEFAULT_CONFIG).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schema_version") != 1:
        raise ValueError(f"unsupported configuration schema: {config.get('schema_version')!r}")
    return config


def repo_path(value: str, *, must_exist: bool = False) -> Path:
    path = (REPO_ROOT / value).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {value}") from exc
    if must_exist and not path.exists():
        raise FileNotFoundError(path)
    return path


def validate_case_id(case_id: str) -> str:
    if not CASE_ID_RE.fullmatch(case_id):
        raise ValueError(f"unsafe case id: {case_id!r}")
    return case_id


def find_case(config: dict[str, Any], case_id: str) -> dict[str, Any]:
    validate_case_id(case_id)
    for case in config["cases"]:
        if case["id"] == case_id:
            return case
    raise KeyError(f"unknown case: {case_id}")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def reserve_unique_paths(output: Path, log: Path, evidence: Path, *, rerun: bool) -> tuple[Path, Path, Path, str]:
    if not any(path.exists() for path in (output, log, evidence)):
        return output, log, evidence, ""
    if not rerun:
        occupied = [str(path) for path in (output, log, evidence) if path.exists()]
        raise FileExistsError("refusing to overwrite retained evidence: " + ", ".join(occupied))

    index = 2
    while True:
        suffix = f"_r{index:02d}"
        candidate_output = output.with_name(output.stem + suffix + output.suffix)
        candidate_log = log.with_name(log.stem + suffix + log.suffix)
        candidate_evidence = evidence.with_name(evidence.name + suffix)
        if not any(path.exists() for path in (candidate_output, candidate_log, candidate_evidence)):
            return candidate_output, candidate_log, candidate_evidence, suffix
        index += 1

