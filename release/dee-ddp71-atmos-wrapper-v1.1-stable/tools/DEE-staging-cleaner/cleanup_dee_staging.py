#!/usr/bin/env python3
"""Force-clear DD+ 7.1 Atmos Wrapper staging roots."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Sequence


STAGING_DIRECTORY_NAME = "dee-ddp71-wrapper"
PRODUCT_DIR = Path(__file__).resolve().parents[2]


def staging_roots() -> list[Path]:
    """Return the same candidate roots used by the wrapper."""
    parents = [Path(tempfile.gettempdir()), PRODUCT_DIR / "work" / "staging"]
    if os.name == "nt" and os.environ.get("SystemRoot"):
        parents.append(Path(os.environ["SystemRoot"]) / "Temp")
    roots: list[Path] = []
    identities: set[str] = set()
    for parent in parents:
        root = parent / STAGING_DIRECTORY_NAME
        identity = os.path.normcase(os.path.abspath(root))
        if identity not in identities:
            identities.add(identity)
            roots.append(root)
    return roots


def is_linked_directory(path: Path) -> bool:
    try:
        is_junction = getattr(path, "is_junction", None)
        return path.is_symlink() or bool(is_junction and is_junction())
    except OSError:
        return True


def validate_root(root: Path) -> None:
    """Restrict deletion to an exact wrapper staging-root name."""
    if root.name.casefold() != STAGING_DIRECTORY_NAME.casefold():
        raise ValueError(f"staging root must be named {STAGING_DIRECTORY_NAME!r}: {root}")
    if root.exists() and is_linked_directory(root):
        raise ValueError(f"refusing to clear a linked staging root: {root}")


def remove_with_retries(path: Path) -> None:
    """Force-remove a staging root after transient Windows handles close."""
    last_error: OSError | None = None
    for attempt in range(20):
        try:
            shutil.rmtree(path)
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


def list_root(root: Path) -> None:
    if not root.exists():
        print(f"[absent] {root}")
        return
    try:
        entries = list(root.iterdir())
    except OSError as exc:
        print(f"[inaccessible] {root}: {exc}")
        return
    print(f"[present: {len(entries)} direct entr{'y' if len(entries) == 1 else 'ies'}] {root}")
    for entry in sorted(entries, key=lambda path: path.name.casefold()):
        print(f"  {entry.name}")


def clear_root(root: Path) -> bool:
    """Remove the exact staging root and everything below it."""
    if not root.exists():
        print(f"[absent] {root}")
        return True
    try:
        remove_with_retries(root)
    except OSError as exc:
        print(f"[failed] {root}: {exc}")
        return False
    print(f"[cleared] {root}")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Force-clear every automatically discovered DD+ 7.1 Atmos Wrapper staging root. "
            "The default action is deletion; use --list to inspect without deleting."
        )
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list staging roots without deleting")
    action.add_argument("--clean", action="store_true", help="explicit alias for the default force-clear action")
    parser.add_argument(
        "--staging-root",
        action="append",
        type=Path,
        metavar="PATH",
        help="force-clear this exact dee-ddp71-wrapper root instead of auto-discovered roots",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    roots = [path.resolve() for path in args.staging_root] if args.staging_root else staging_roots()
    try:
        for root in roots:
            validate_root(root)
    except ValueError as exc:
        print(f"cleaner error: {exc}")
        return 2

    if args.list:
        for root in roots:
            list_root(root)
        return 0

    success = True
    for root in roots:
        success = clear_root(root) and success
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
