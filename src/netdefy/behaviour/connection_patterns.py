"""NETDEFY — Connection Pattern Analyzer.

Analyzes connection attempt sequences, TCP handshake completions, SYN-without-ACK patterns,
and reset storms across sequential network events.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from netdefy.behaviour.schema import NetworkEvent
from netdefy.preprocessing.schema import map_destination_port_to_service


@dataclass(frozen=True)
class ConnectionPatternProfile:
    """Quantitative connection pattern dynamics across a sequence of flows."""

    total_connections: int
    failed_connection_ratio: float
    syn_only_ratio: float
    repeated_destination_ratio: float
    is_syn_flood: bool
    is_rst_storm: bool
    dominant_service: str


class ConnectionPatternAnalyzer:
    """Evaluates multi-flow connection establishment, failure rates, and handshake anomalies."""

    def __init__(
        self,
        min_connections: int = 10,
        syn_flood_ratio_threshold: float = 0.80,
        rst_storm_ratio_threshold: float = 0.75,
    ) -> None:
        self.min_connections = min_connections
        self.syn_flood_ratio = syn_flood_ratio_threshold
        self.rst_storm_ratio = rst_storm_ratio_threshold

    def analyze(self, events: Sequence[NetworkEvent]) -> ConnectionPatternProfile:
        """Analyze connection completion and handshake patterns over events."""
        n_conn = len(events)
        if n_conn == 0:
            return ConnectionPatternProfile(
                total_connections=0,
                failed_connection_ratio=0.0,
                syn_only_ratio=0.0,
                repeated_destination_ratio=0.0,
                is_syn_flood=False,
                is_rst_storm=False,
                dominant_service="UNKNOWN",
            )

        syn_only_count = 0
        rst_count = 0
        services: list[str] = []
        dest_counts: Counter[str] = Counter()

        for ev in events:
            feat = ev.features
            fwd_pkts = feat.get("Total Fwd Packets", 1.0)
            bwd_pkts = feat.get("Total Backward Packets", 0.0)
            bwd_bytes = feat.get("Total Length of Bwd Packets", 0.0)

            # SYN only: forward packets sent, but 0 backward packets returned
            if fwd_pkts > 0 and bwd_pkts == 0:
                syn_only_count += 1

            # Closed port / RST signature: exactly 1 bwd packet with 6-40 bytes
            if fwd_pkts >= 1 and bwd_pkts == 1 and 6.0 <= bwd_bytes <= 40.0:
                rst_count += 1

            if ev.destination_ip is not None:
                dest_counts[ev.destination_ip] += 1

            if ev.destination_port is not None:
                services.append(map_destination_port_to_service(ev.destination_port))

        syn_ratio = float(syn_only_count / n_conn)
        rst_ratio = float(rst_count / n_conn)
        failed_ratio = float((syn_only_count + rst_count) / n_conn)

        # Repeated destination ratio: proportion of connections that revisit a previously seen IP
        if dest_counts:
            repeated_conns = sum(count - 1 for count in dest_counts.values() if count > 1)
            repeated_ratio = float(repeated_conns / n_conn)
        else:
            repeated_ratio = 0.0

        is_syn_flood = bool(n_conn >= self.min_connections and syn_ratio >= self.syn_flood_ratio)
        is_rst_storm = bool(n_conn >= self.min_connections and rst_ratio >= self.rst_storm_ratio)

        dom_service = Counter(services).most_common(1)[0][0] if services else "UNKNOWN"

        return ConnectionPatternProfile(
            total_connections=n_conn,
            failed_connection_ratio=failed_ratio,
            syn_only_ratio=syn_ratio,
            repeated_destination_ratio=repeated_ratio,
            is_syn_flood=is_syn_flood,
            is_rst_storm=is_rst_storm,
            dominant_service=dom_service,
        )
