from __future__ import annotations

import argparse
from pathlib import Path

from common import load_config, repo_path, timestamp_id, write_json
from stream_validation import validate_stream


def baseline(config_path: Path | None) -> int:
    config = load_config(config_path)
    evidence_root = repo_path(config["paths"]["evidence_dir"]) / "baseline" / timestamp_id()
    summary = {
        "scope": "flat 7.1 layout only; PLIIx signal and Surround EX metadata use separate validators",
        "streams": [],
    }
    for item in config["baseline_streams"]:
        path = repo_path(item["path"])
        report = validate_stream(path, evidence_root / item["id"])
        summary["streams"].append({
            "id": item["id"],
            "path": str(path),
            "role": item["role"],
            "size": report.get("size"),
            "sha256": report.get("sha256"),
            "classification": report.get("classification"),
            "frame_scan": report.get("frame_scan"),
        })
        print(f"{item['id']}: {report.get('classification', {}).get('verdict', report.get('status'))}")
    write_json(evidence_root / "baseline.json", summary)
    print(f"evidence: {evidence_root}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only DD+ JOC flat-7.1 validator")
    parser.add_argument("--config", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("baseline")
    stream_parser = subparsers.add_parser("stream")
    stream_parser.add_argument("path", type=Path)
    stream_parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()

    if args.command == "baseline":
        return baseline(args.config)
    report = validate_stream(args.path.resolve(), args.evidence_dir.resolve() if args.evidence_dir else None)
    print(report.get("classification", {}).get("verdict", report.get("status")))
    return 0 if report.get("frame_scan", {}).get("status") in {"valid", "empty"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
