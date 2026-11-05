"""NETDEFY — Destination & Port Diversity Analyzer.

Detects horizontal network scans (one source targeting many destination hosts)
and vertical port scans (one source probing many ports on a single target).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from netdefy.behaviour.schema import NetworkEvent


@dataclass(frozen=True)
class DiversityProfile:
    """Quantitative diversity metrics across destinations and destination ports."""

    total_connections: int
    unique_destination_ips: int
    unique_destination_ports: int
    destination_fan_out_ratio: float
    port_fan_out_ratio: float
    is_horizontal_scan: bool
    is_vertical_scan: bool


class DestinationDiversityAnalyzer:
    """Analyzes destination and port distribution over multi-flow sequences."""

    def __init__(
        self,
        min_connections_for_scan: int = 10,
        horizontal_scan_ip_threshold: int = 8,
        horizontal_scan_fan_out: float = 0.70,
        vertical_scan_port_threshold: int = 8,
        vertical_scan_fan_out: float = 0.70,
    ) -> None:
        self.min_connections = min_connections_for_scan
        self.horizontal_ip_thresh = horizontal_scan_ip_threshold
        self.horizontal_fan_out = horizontal_scan_fan_out
        self.vertical_port_thresh = vertical_scan_port_threshold
        self.vertical_fan_out = vertical_scan_fan_out

    def analyze(self, events: Sequence[NetworkEvent]) -> DiversityProfile:
        """Analyze destination and port distribution across a collection of events."""
        n_conn = len(events)
        if n_conn == 0:
            return DiversityProfile(
                total_connections=0,
                unique_destination_ips=0,
                unique_destination_ports=0,
                destination_fan_out_ratio=0.0,
                port_fan_out_ratio=0.0,
                is_horizontal_scan=False,
                is_vertical_scan=False,
            )

        dst_ips: set[str] = set()
        dst_ports: set[int] = set()

        for ev in events:
            if ev.destination_ip is not None:
                dst_ips.add(ev.destination_ip)
            if ev.destination_port is not None:
                dst_ports.add(ev.destination_port)

        u_ips = len(dst_ips)
        u_ports = len(dst_ports)
        ip_fan_out = float(u_ips / n_conn)
        port_fan_out = float(u_ports / n_conn)

        # Horizontal scan: many unique destination IPs with high fan-out
        is_horiz = bool(
            n_conn >= self.min_connections
            and u_ips >= self.horizontal_ip_thresh
            and ip_fan_out >= self.horizontal_fan_out
        )

        # Vertical scan: many unique destination ports on single or few destination IPs
        is_vert = bool(
            n_conn >= self.min_connections
            and u_ports >= self.vertical_port_thresh
            and port_fan_out >= self.vertical_fan_out
            and (u_ips <= 3 or u_ips == 0)
        )

        return DiversityProfile(
            total_connections=n_conn,
            unique_destination_ips=u_ips,
            unique_destination_ports=u_ports,
            destination_fan_out_ratio=ip_fan_out,
            port_fan_out_ratio=port_fan_out,
            is_horizontal_scan=is_horiz,
            is_vertical_scan=is_vert,
        )
