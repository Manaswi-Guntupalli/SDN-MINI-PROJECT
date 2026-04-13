"""Mininet topology for Orange SDN QoS assignment.

Topology:
  h1 (high-priority client)
  h2 (bulk/best-effort client)
  h3 (normal client)
  h4 (blocked client)
  h5 (application server)
  all attached to switch s1

The link to h5 is bottlenecked to expose QoS behavior.
"""

from __future__ import annotations

from mininet.topo import Topo


class OrangeQoSTopo(Topo):
    """Single-switch topology with deterministic port mapping."""

    def build(self):
        switch = self.addSwitch("s1", protocols="OpenFlow13")

        h1 = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        h2 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        h3 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")
        h4 = self.addHost("h4", ip="10.0.0.4/24", mac="00:00:00:00:00:04")
        h5 = self.addHost("h5", ip="10.0.0.5/24", mac="00:00:00:00:00:05")

        # Port order matters because controller uses static host-port mapping.
        self.addLink(h1, switch, bw=100, delay="1ms", use_htb=True)
        self.addLink(h2, switch, bw=100, delay="1ms", use_htb=True)
        self.addLink(h3, switch, bw=100, delay="1ms", use_htb=True)
        self.addLink(h4, switch, bw=100, delay="1ms", use_htb=True)

        # Bottleneck link for measurable queueing/latency effect.
        self.addLink(h5, switch, bw=10, delay="4ms", max_queue_size=1000, use_htb=True)


topos = {"orangeqos": OrangeQoSTopo}
