"""Ryu controller for SDN QoS priority handling in Mininet.

Implements:
- PacketIn handling with MAC learning behavior
- Explicit OpenFlow match-action rules for block/allow/QoS
- Queue assignment for high-priority and best-effort traffic
"""

from __future__ import annotations

import os
from typing import Dict, List

try:
    from ryu.base import app_manager
    from ryu.controller import ofp_event
    from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
    from ryu.lib.packet import ethernet, ether_types, ipv4, packet, tcp, udp
    from ryu.ofproto import ofproto_v1_3
    ControllerBaseApp = app_manager.RyuApp
except ModuleNotFoundError:
    from os_ken.base import app_manager
    from os_ken.controller import ofp_event
    from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
    from os_ken.lib.packet import ethernet, ether_types, ipv4, packet, tcp, udp
    from os_ken.ofproto import ofproto_v1_3
    ControllerBaseApp = app_manager.OSKenApp


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class QoSPriorityController(ControllerBaseApp):
    """OpenFlow 1.3 controller with traffic prioritization rules."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port: Dict[int, Dict[str, int]] = {}

        self.qos_enabled = _read_bool_env("QOS_ENABLED", True)
        self.high_prio_host = os.getenv("HIGH_PRIORITY_HOST", "10.0.0.1")
        self.bulk_host = os.getenv("BULK_HOST", "10.0.0.2")
        self.blocked_host = os.getenv("BLOCKED_HOST", "10.0.0.4")
        self.server_host = os.getenv("SERVER_HOST", "10.0.0.5")
        self.voice_udp_port = int(os.getenv("VOICE_UDP_PORT", "5001"))
        self.bulk_tcp_port = int(os.getenv("BULK_TCP_PORT", "5002"))

        # Static port mapping is deterministic based on link creation order.
        self.ip_to_port = {
            "10.0.0.1": 1,
            "10.0.0.2": 2,
            "10.0.0.3": 3,
            "10.0.0.4": 4,
            "10.0.0.5": 5,
        }

        self.queue_best_effort = 0
        self.queue_high_priority = 1

        self.logger.info("QoS enabled: %s", self.qos_enabled)

    def _add_flow(
        self,
        datapath,
        priority: int,
        match,
        actions: List,
        idle_timeout: int = 0,
        hard_timeout: int = 0,
        buffer_id=None,
    ) -> None:
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id is not None and buffer_id != ofproto.OFP_NO_BUFFER:
            message = parser.OFPFlowMod(
                datapath=datapath,
                buffer_id=buffer_id,
                priority=priority,
                match=match,
                instructions=instructions,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
            )
        else:
            message = parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=instructions,
                idle_timeout=idle_timeout,
                hard_timeout=hard_timeout,
            )

        datapath.send_msg(message)

    def _install_static_policy(self, datapath) -> None:
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        server_port = self.ip_to_port[self.server_host]
        high_port = self.ip_to_port[self.high_prio_host]
        bulk_port = self.ip_to_port[self.bulk_host]

        # Rule 1: block blocked-host -> server traffic.
        blocked_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=self.blocked_host,
            ipv4_dst=self.server_host,
        )
        self._add_flow(datapath, priority=450, match=blocked_match, actions=[])

        high_actions_to_server = []
        if self.qos_enabled:
            high_actions_to_server.append(parser.OFPActionSetQueue(self.queue_high_priority))
        high_actions_to_server.append(parser.OFPActionOutput(server_port))

        high_actions_to_client = []
        if self.qos_enabled:
            high_actions_to_client.append(parser.OFPActionSetQueue(self.queue_high_priority))
        high_actions_to_client.append(parser.OFPActionOutput(high_port))

        # Rule 2: prioritize ICMP from high-priority host to server.
        icmp_req_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=self.high_prio_host,
            ipv4_dst=self.server_host,
            ip_proto=1,
        )
        self._add_flow(datapath, priority=340, match=icmp_req_match, actions=high_actions_to_server)

        icmp_rep_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=self.server_host,
            ipv4_dst=self.high_prio_host,
            ip_proto=1,
        )
        self._add_flow(datapath, priority=340, match=icmp_rep_match, actions=high_actions_to_client)

        # Rule 3: prioritize UDP voice stream.
        voice_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=self.high_prio_host,
            ipv4_dst=self.server_host,
            ip_proto=17,
            udp_dst=self.voice_udp_port,
        )
        self._add_flow(datapath, priority=330, match=voice_match, actions=high_actions_to_server)

        voice_rev_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=self.server_host,
            ipv4_dst=self.high_prio_host,
            ip_proto=17,
            udp_src=self.voice_udp_port,
        )
        self._add_flow(datapath, priority=330, match=voice_rev_match, actions=high_actions_to_client)

        best_effort_actions = []
        if self.qos_enabled:
            best_effort_actions.append(parser.OFPActionSetQueue(self.queue_best_effort))
        best_effort_actions.append(parser.OFPActionOutput(server_port))

        best_effort_actions_rev = []
        if self.qos_enabled:
            best_effort_actions_rev.append(parser.OFPActionSetQueue(self.queue_best_effort))
        best_effort_actions_rev.append(parser.OFPActionOutput(bulk_port))

        # Rule 4: classify bulk TCP to best-effort queue.
        bulk_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=self.bulk_host,
            ipv4_dst=self.server_host,
            ip_proto=6,
            tcp_dst=self.bulk_tcp_port,
        )
        self._add_flow(datapath, priority=250, match=bulk_match, actions=best_effort_actions)

        bulk_rev_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ipv4_src=self.server_host,
            ipv4_dst=self.bulk_host,
            ip_proto=6,
            tcp_src=self.bulk_tcp_port,
        )
        self._add_flow(datapath, priority=250, match=bulk_rev_match, actions=best_effort_actions_rev)

        # Keep ARP working across hosts.
        arp_match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_ARP)
        arp_actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self._add_flow(datapath, priority=120, match=arp_match, actions=arp_actions)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # Table miss rule sends unmatched packets to controller.
        miss_match = parser.OFPMatch()
        miss_actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, priority=0, match=miss_match, actions=miss_actions)

        self._install_static_policy(datapath)

    def _classify_actions(self, parser, pkt_ipv4: ipv4.ipv4, pkt_tcp: tcp.tcp, pkt_udp: udp.udp):
        actions = []

        if not self.qos_enabled:
            return actions

        if (
            pkt_ipv4.src == self.high_prio_host
            and pkt_ipv4.dst == self.server_host
            and pkt_ipv4.proto == 1
        ):
            actions.append(parser.OFPActionSetQueue(self.queue_high_priority))
            return actions

        if (
            pkt_ipv4.src == self.high_prio_host
            and pkt_ipv4.dst == self.server_host
            and pkt_ipv4.proto == 17
            and pkt_udp
            and pkt_udp.dst_port == self.voice_udp_port
        ):
            actions.append(parser.OFPActionSetQueue(self.queue_high_priority))
            return actions

        if (
            pkt_ipv4.src == self.bulk_host
            and pkt_ipv4.dst == self.server_host
            and pkt_ipv4.proto == 6
            and pkt_tcp
            and pkt_tcp.dst_port == self.bulk_tcp_port
        ):
            actions.append(parser.OFPActionSetQueue(self.queue_best_effort))
            return actions

        return actions

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth.src] = in_port

        out_port = self.mac_to_port[dpid].get(eth.dst, ofproto.OFPP_FLOOD)

        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
        pkt_tcp = pkt.get_protocol(tcp.tcp)
        pkt_udp = pkt.get_protocol(udp.udp)

        if pkt_ipv4 and pkt_ipv4.src == self.blocked_host and pkt_ipv4.dst == self.server_host:
            drop_match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=self.blocked_host,
                ipv4_dst=self.server_host,
            )
            self._add_flow(datapath, priority=460, match=drop_match, actions=[], idle_timeout=120)
            return

        actions = []
        if out_port != ofproto.OFPP_FLOOD and pkt_ipv4:
            actions.extend(self._classify_actions(parser, pkt_ipv4, pkt_tcp, pkt_udp))

        actions.append(parser.OFPActionOutput(out_port))

        if out_port != ofproto.OFPP_FLOOD:
            flow_match = parser.OFPMatch(in_port=in_port, eth_src=eth.src, eth_dst=eth.dst)
            self._add_flow(
                datapath,
                priority=20,
                match=flow_match,
                actions=actions,
                idle_timeout=60,
                hard_timeout=180,
                buffer_id=msg.buffer_id,
            )
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                return

        packet_out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=None if msg.buffer_id != ofproto.OFP_NO_BUFFER else msg.data,
        )
        datapath.send_msg(packet_out)
