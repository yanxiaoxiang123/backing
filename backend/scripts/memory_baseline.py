"""Capture a small, repeatable memory baseline for the backend process.

Examples::

    python scripts/memory_baseline.py --import-app
    python scripts/memory_baseline.py --import-app --seconds 30

The script deliberately reports both Python allocations and process RSS. RSS
includes native allocations from pandas, torch, database drivers, and charts'
server-side helpers that tracemalloc cannot see.
"""

from __future__ import annotations

import argparse
import importlib
import json
import time
import tracemalloc

try:  # resource is unavailable on Windows
    import resource
except ImportError:  # pragma: no cover - exercised on Windows hosts
    resource = None  # type: ignore[assignment]


def _rss_bytes() -> int:
    if resource is None:
        return 0
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB; macOS reports bytes.
    return int(value * 1024 if value < 10_000_000 else value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--import-app",
        action="store_true",
        help="import app.main to measure cold application import overhead",
    )
    parser.add_argument(
        "--seconds", type=float, default=0, help="keep the process alive for observation"
    )
    args = parser.parse_args()

    tracemalloc.start(25)
    before = _rss_bytes()
    if args.import_app:
        importlib.import_module("main")
    if args.seconds > 0:
        time.sleep(args.seconds)
    current, peak = tracemalloc.get_traced_memory()
    print(
        json.dumps(
            {
                "rss_before_bytes": before,
                "rss_max_bytes": _rss_bytes(),
                "python_allocated_bytes": current,
                "python_peak_bytes": peak,
                "seconds": args.seconds,
                "imported_app": args.import_app,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
