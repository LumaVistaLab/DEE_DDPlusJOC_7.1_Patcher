from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("success", "crash", "no-output", "slow"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    print("fake DEE: measurement pass", flush=True)
    if args.mode == "success":
        args.output.write_bytes(b"synthetic-output")
        print("fake DEE: encoder pass complete", flush=True)
        return 0
    if args.mode == "crash":
        print("Access violation occurred at address: 0x00000000FAKE0001", flush=True)
        return 10
    if args.mode == "slow":
        time.sleep(10)
        return 0
    print("fake DEE: exited without opening the output", flush=True)
    return 7


if __name__ == "__main__":
    raise SystemExit(main())

