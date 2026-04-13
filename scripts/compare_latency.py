#!/usr/bin/env python3
"""Compare latency metrics between baseline and QoS experiment outputs."""

from __future__ import annotations

import json
from pathlib import Path


def load_summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    base = load_summary(Path("artifacts/baseline/summary.json"))
    qos = load_summary(Path("artifacts/qos/summary.json"))

    base_latency = base["scenarios"]["scenario2_latency_under_congestion"]["under_load"]["avg_ms"]
    qos_latency = qos["scenarios"]["scenario2_latency_under_congestion"]["under_load"]["avg_ms"]

    improvement = base_latency - qos_latency
    improvement_pct = (improvement / base_latency * 100.0) if base_latency > 0 else 0.0

    print("=== Latency Comparison (Under Load) ===")
    print(f"Baseline avg RTT: {base_latency:.3f} ms")
    print(f"QoS avg RTT:      {qos_latency:.3f} ms")
    print(f"Improvement:      {improvement:.3f} ms ({improvement_pct:.2f}%)")

    base_s1 = base["scenarios"]["scenario1_allowed_vs_blocked"]["pass"]
    qos_s1 = qos["scenarios"]["scenario1_allowed_vs_blocked"]["pass"]
    print("=== Scenario 1 Validation ===")
    print(f"Baseline allowed-vs-blocked pass: {base_s1}")
    print(f"QoS allowed-vs-blocked pass:      {qos_s1}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
