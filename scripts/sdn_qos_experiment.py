#!/usr/bin/env python3
"""Automated Mininet experiment for QoS priority controller validation.

Runs mandatory scenarios:
1) Allowed vs blocked communication
2) Latency under congestion (baseline vs QoS)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Dict

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController

# Allow running this script directly while importing project modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from topology.orange_qos_topology import OrangeQoSTopo


PING_STATS_RE = re.compile(
    r"rtt min/avg/max/mdev = (?P<min>[0-9.]+)/(?P<avg>[0-9.]+)/(?P<max>[0-9.]+)/(?P<mdev>[0-9.]+) ms"
)
PING_LOSS_RE = re.compile(r"(?P<loss>[0-9]+)% packet loss")


def parse_ping_metrics(ping_output: str) -> Dict[str, float]:
    """Extract average RTT and packet loss from ping output."""
    result = {"avg_ms": -1.0, "loss_percent": 100.0}

    loss_match = PING_LOSS_RE.search(ping_output)
    if loss_match:
        result["loss_percent"] = float(loss_match.group("loss"))

    stats_match = PING_STATS_RE.search(ping_output)
    if stats_match:
        result["avg_ms"] = float(stats_match.group("avg"))

    return result


def run_command_and_store(host, command: str, output_file: Path) -> str:
    """Execute host command and persist full output to file."""
    output = host.cmd(command)
    output_file.write_text(output, encoding="utf-8")
    return output


def configure_switch_queues(net: Mininet, enable_qos: bool) -> None:
    """Configure OVS queues on bottleneck interface toward h5."""
    switch = net.get("s1")
    iface = "s1-eth5"

    switch.cmd("ovs-vsctl --if-exists clear Port s1-eth5 qos")
    switch.cmd("ovs-vsctl -- --all destroy QoS -- --all destroy Queue")

    if not enable_qos:
        return

    switch.cmd(
        "ovs-vsctl -- "
        "--id=@q0 create Queue other-config:min-rate=1000000 other-config:max-rate=2000000 -- "
        "--id=@q1 create Queue other-config:min-rate=6000000 other-config:max-rate=10000000 -- "
        "--id=@newqos create QoS type=linux-htb other-config:max-rate=10000000 queues:0=@q0 queues:1=@q1 -- "
        f"set Port {iface} qos=@newqos"
    )


def dump_flow_state(net: Mininet, output_dir: Path, label: str) -> None:
    """Collect flow table and queue statistics for reporting."""
    switch = net.get("s1")
    flows = switch.cmd("ovs-ofctl -O OpenFlow13 dump-flows s1")
    queue_stats = switch.cmd("ovs-ofctl -O OpenFlow13 queue-stats s1")
    output_dir.joinpath(f"{label}_flow_table.txt").write_text(flows, encoding="utf-8")
    output_dir.joinpath(f"{label}_queue_stats.txt").write_text(queue_stats, encoding="utf-8")


def run_scenarios(net: Mininet, output_dir: Path) -> Dict[str, object]:
    """Run required test scenarios and return summarized metrics."""
    h1 = net.get("h1")
    h2 = net.get("h2")
    h4 = net.get("h4")
    h5 = net.get("h5")

    metrics: Dict[str, object] = {}

    # Scenario 1: Allowed vs blocked.
    allowed_out = run_command_and_store(
        h1, "ping -c 5 -i 0.2 -W 1 10.0.0.5", output_dir / "scenario1_allowed_ping.txt"
    )
    blocked_out = run_command_and_store(
        h4, "ping -c 5 -i 0.2 -W 1 10.0.0.5", output_dir / "scenario1_blocked_ping.txt"
    )
    allowed_metrics = parse_ping_metrics(allowed_out)
    blocked_metrics = parse_ping_metrics(blocked_out)

    metrics["scenario1_allowed_vs_blocked"] = {
        "allowed": allowed_metrics,
        "blocked": blocked_metrics,
        "pass": allowed_metrics["loss_percent"] < 100.0 and blocked_metrics["loss_percent"] == 100.0,
    }

    # Scenario 2: Latency under congestion.
    h5.cmd("pkill -f 'iperf -s' || true")
    h5.cmd("iperf -s -u -p 5001 > /tmp/iperf_server_udp.log 2>&1 &")
    h5.cmd("iperf -s -p 5002 > /tmp/iperf_server_tcp.log 2>&1 &")
    time.sleep(1)

    no_load_out = run_command_and_store(
        h1, "ping -c 20 -i 0.2 -W 1 10.0.0.5", output_dir / "scenario2_ping_no_load.txt"
    )

    h2.cmd("iperf -c 10.0.0.5 -p 5002 -t 18 > /tmp/bulk_tcp_client.log 2>&1 &")
    time.sleep(1)

    under_load_out = run_command_and_store(
        h1, "ping -c 20 -i 0.2 -W 1 10.0.0.5", output_dir / "scenario2_ping_under_load.txt"
    )
    udp_out = run_command_and_store(
        h1,
        "iperf -u -b 8M -c 10.0.0.5 -p 5001 -t 8",
        output_dir / "scenario2_high_priority_udp.txt",
    )

    bulk_out = h2.cmd("cat /tmp/bulk_tcp_client.log")
    (output_dir / "scenario2_bulk_tcp.txt").write_text(bulk_out, encoding="utf-8")

    (output_dir / "scenario2_udp_server.txt").write_text(
        h5.cmd("cat /tmp/iperf_server_udp.log"), encoding="utf-8"
    )
    (output_dir / "scenario2_tcp_server.txt").write_text(
        h5.cmd("cat /tmp/iperf_server_tcp.log"), encoding="utf-8"
    )

    no_load_metrics = parse_ping_metrics(no_load_out)
    under_load_metrics = parse_ping_metrics(under_load_out)

    metrics["scenario2_latency_under_congestion"] = {
        "no_load": no_load_metrics,
        "under_load": under_load_metrics,
        "high_priority_udp_excerpt": "\n".join(udp_out.strip().splitlines()[-3:]),
    }

    h5.cmd("pkill -f 'iperf -s' || true")
    h2.cmd("pkill -f 'iperf -c 10.0.0.5 -p 5002' || true")

    return metrics


def run_experiment(mode: str, output_root: Path, controller_ip: str, controller_port: int) -> Dict[str, object]:
    """Boot topology, run tests, and collect artifacts."""
    output_dir = output_root / mode
    output_dir.mkdir(parents=True, exist_ok=True)

    net = Mininet(
        topo=OrangeQoSTopo(),
        switch=OVSKernelSwitch,
        controller=None,
        link=TCLink,
        autoSetMacs=False,
        build=False,
    )

    net.addController("c0", controller=RemoteController, ip=controller_ip, port=controller_port)

    summary: Dict[str, object] = {"mode": mode, "qos_enabled": mode == "qos"}

    try:
        net.build()
        net.start()
        time.sleep(2)

        configure_switch_queues(net, enable_qos=(mode == "qos"))
        net.pingAll(timeout=1)

        summary["scenarios"] = run_scenarios(net, output_dir)
        dump_flow_state(net, output_dir, mode)

    finally:
        net.stop()

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SDN QoS experiment in Mininet")
    parser.add_argument("--mode", choices=["baseline", "qos"], required=True)
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6653)
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args()

    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.mode == "baseline":
        os.environ["QOS_ENABLED"] = "0"
    else:
        os.environ["QOS_ENABLED"] = "1"

    summary = run_experiment(
        mode=args.mode,
        output_root=output_root,
        controller_ip=args.controller_ip,
        controller_port=args.controller_port,
    )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    setLogLevel("warning")
    raise SystemExit(main())
