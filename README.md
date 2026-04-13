# Simple QoS Priority Controller (SDN Mininet + Ryu)

## 1. Problem Statement

This project implements an SDN-based QoS priority controller that prioritizes specific traffic types over others using explicit OpenFlow rules.

Primary controller runtime is Ryu. For Python 3.12 environments where legacy Ryu packaging fails, the project supports OS-Ken manager as a compatible fallback while preserving the same OpenFlow logic.

The implementation satisfies the Orange assignment requirements:

- Mininet topology with OpenFlow 1.3 switch
- Ryu controller with PacketIn handling and match-action flow logic
- Explicit flow rules for prioritization and filtering
- Demonstrable behavior with at least two scenarios
- Latency and throughput observation using ping and iperf

## 2. Project Structure

```
.
├── controller/
│   └── qos_priority_controller.py
├── topology/
│   └── orange_qos_topology.py
├── scripts/
│   ├── compare_latency.py
│   ├── run_demo.sh
│   ├── sdn_qos_experiment.py
│   └── validate_artifacts.py
├── docs/
│   └── PROOF_OF_EXECUTION_TEMPLATE.md
├── Makefile
├── requirements.txt
└── README.md
```

## 3. Network Design

### Hosts

- h1 (`10.0.0.1`): high-priority client
- h2 (`10.0.0.2`): best-effort bulk client
- h3 (`10.0.0.3`): normal client
- h4 (`10.0.0.4`): blocked client
- h5 (`10.0.0.5`): server

### Topology

- Single switch `s1` (OpenFlow13)
- Deterministic port mapping:
  - port1->h1, port2->h2, port3->h3, port4->h4, port5->h5
- Bottleneck link on `s1-h5` at 10 Mbps for measurable congestion

## 4. Traffic Types and Priority Levels

1. High priority

   - ICMP from h1 to h5 (latency-sensitive)
   - UDP stream on port 5001 from h1 to h5 (voice-like)
   - Queue ID: 1

2. Best effort

   - TCP bulk traffic on port 5002 from h2 to h5
   - Queue ID: 0

3. Blocked traffic
   - Any IPv4 from h4 to h5 is dropped

## 5. OpenFlow Rule Design

Controller installs explicit rules with priority ordering:

- Priority 450+: drop blocked host traffic
- Priority 340: high-priority ICMP flows
- Priority 330: high-priority UDP voice flows
- Priority 250: best-effort TCP bulk flows
- Priority 120: ARP flood rule
- Priority 20: dynamic learning-switch unicast entries from PacketIn
- Priority 0: table-miss to controller

Actions include:

- `set_queue(1)` + output for high-priority traffic
- `set_queue(0)` + output for best-effort traffic
- drop action for blocked traffic

## 6. Setup Instructions

### 6.1 System prerequisites (Ubuntu recommended)

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf wireshark python3-pip
bash scripts/setup_env.sh
```

This creates `.venv/` and attempts to install Ryu.

If Ryu installation fails on Python 3.12, setup falls back to installing system `osken-manager`.

`run_demo.sh` auto-detects available manager in this order:

1. `.venv/bin/ryu-manager`
2. `.venv/bin/osken-manager`
3. system `ryu-manager`
4. system `osken-manager`

### 6.2 Verify syntax

```bash
make lint
```

## 7. Execution

Run the full demonstration (baseline + qos + comparison):

```bash
bash scripts/run_demo.sh all
```

Run only one mode:

```bash
bash scripts/run_demo.sh baseline
bash scripts/run_demo.sh qos
```

Validate generated artifacts:

```bash
python3 scripts/validate_artifacts.py
```

## 8. Mandatory Test Scenarios Covered

### Scenario 1: Allowed vs Blocked

- Allowed: h1 can ping h5
- Blocked: h4 cannot ping h5 (100% loss expected)

Evidence files:

- `artifacts/<mode>/scenario1_allowed_ping.txt`
- `artifacts/<mode>/scenario1_blocked_ping.txt`

### Scenario 2: Latency under Congestion

- Normal/no-load latency measured via h1->h5 ping
- Congested latency measured while h2 runs TCP iperf bulk flow
- High-priority UDP flow generated in parallel (h1->h5, port 5001)
- Baseline vs QoS comparison produced in `artifacts/latency_comparison.txt`

## 9. Expected Output and Interpretation

After `run_demo.sh all`, expect:

- `artifacts/baseline/summary.json`
- `artifacts/qos/summary.json`
- `artifacts/latency_comparison.txt`
- flow table and queue stats in each mode directory

Interpretation guidance:

- Scenario 1 pass must be true in both modes
- Under-load average RTT in QoS mode should be lower than baseline in most runs
- Flow table must show high-priority and best-effort matches with corresponding queue actions

## 10. Proof of Execution for GitHub Submission

Use:

- `docs/PROOF_OF_EXECUTION_TEMPLATE.md`

Attach screenshots/log excerpts for:

- Controller logs
- Scenario outputs
- Flow table dumps
- Queue stats
- Wireshark captures

## 11. Basic Validation / Regression

- `scripts/validate_artifacts.py` checks required output files and scenario pass flag
- Re-run after controller changes to ensure behavior does not regress

## 12. References

1. Mininet Documentation: http://mininet.org/walkthrough/
2. Ryu SDN Framework: https://ryu.readthedocs.io/en/latest/
3. OpenFlow Switch Specification (v1.3):
   https://opennetworking.org/sdn-resources/openflow-switch-specification/
