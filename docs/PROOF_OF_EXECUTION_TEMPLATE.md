# Proof of Execution Template

Use this template to attach required screenshots/log snippets in your public GitHub submission.

## 1. Controller and Topology Startup

- Screenshot: `ryu-manager controller/qos_priority_controller.py` running
- Screenshot: experiment script start output

## 2. Scenario 1 (Allowed vs Blocked)

- Attach from `artifacts/<mode>/scenario1_allowed_ping.txt`
- Attach from `artifacts/<mode>/scenario1_blocked_ping.txt`
- Explain why blocked host reaches 100% loss while allowed host succeeds.

## 3. Scenario 2 (Latency Under Congestion)

- Attach from `artifacts/<mode>/scenario2_ping_no_load.txt`
- Attach from `artifacts/<mode>/scenario2_ping_under_load.txt`
- Attach from `artifacts/<mode>/scenario2_bulk_tcp.txt`
- Attach from `artifacts/<mode>/scenario2_high_priority_udp.txt`

## 4. Flow Tables and Queue Statistics

- Attach from `artifacts/<mode>/<mode>_flow_table.txt`
- Attach from `artifacts/<mode>/<mode>_queue_stats.txt`
- Highlight match fields, priorities, actions, and queue IDs.

## 5. Baseline vs QoS Comparison

- Attach `artifacts/latency_comparison.txt`
- Mention observed latency difference and interpretation.

## 6. Wireshark Evidence

- Capture one interface (recommended: `s1-eth5`)
- Suggested filters:
  - `icmp && ip.addr == 10.0.0.5`
  - `tcp.port == 5002`
  - `udp.port == 5001`
- Show one frame for each traffic class and explain.
