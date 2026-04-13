#!/usr/bin/env python3
"""Basic validation checks over experiment artifacts.

Used as simple regression guard to ensure required outputs are present.
"""

from __future__ import annotations

import json
from pathlib import Path


REQUIRED_FILES = [
    "summary.json",
    "scenario1_allowed_ping.txt",
    "scenario1_blocked_ping.txt",
    "scenario2_ping_no_load.txt",
    "scenario2_ping_under_load.txt",
]


def validate_mode(mode: str) -> None:
    mode_dir = Path("artifacts") / mode
    if not mode_dir.exists():
        raise FileNotFoundError(f"Missing artifacts directory: {mode_dir}")

    for file_name in REQUIRED_FILES:
        file_path = mode_dir / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"Missing required artifact: {file_path}")

    summary = json.loads((mode_dir / "summary.json").read_text(encoding="utf-8"))

    scenario1_pass = summary["scenarios"]["scenario1_allowed_vs_blocked"]["pass"]
    if not scenario1_pass:
        raise RuntimeError(f"Scenario 1 failed in {mode}")


def main() -> int:
    validate_mode("baseline")
    validate_mode("qos")
    print("Artifact validation passed for baseline and qos runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
