"""NETDEFY — Host Behavioral Profile Manager.

Maintains memory-bounded, LRU-cached behavioral profiles for network hosts, tracking
baseline activity, historical destination diversity, and cumulative threat signals.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from typing import Any

from netdefy.behaviour.schema import NetworkEvent


@dataclass
class HostProfile:
    """Historical behavioral profile for an observed IP address."""

    ip_address: str
    total_connections_seen: int = 0
    first_seen_timestamp: float | None = None
    last_seen_timestamp: float | None = None
    accessed_ports: Counter[int] = field(default_factory=Counter)
    contacted_destinations: set[str] = field(default_factory=set)
    total_fwd_bytes: int = 0
    total_bwd_bytes: int = 0
    anomalous_events_count: int = 0

    def update_from_event(self, event: NetworkEvent, is_anomaly: bool = False) -> None:
        """Update profile statistics with a newly observed traffic event."""
        self.total_connections_seen += 1
        ts = event.timestamp
        if ts is not None:
            if self.first_seen_timestamp is None or ts < self.first_seen_timestamp:
                self.first_seen_timestamp = ts
            if self.last_seen_timestamp is None or ts > self.last_seen_timestamp:
                self.last_seen_timestamp = ts

        if event.destination_port is not None:
            self.accessed_ports[event.destination_port] += 1

        if event.destination_ip is not None:
            self.contacted_destinations.add(event.destination_ip)

        feat = event.features
        fwd_bytes = int(feat.get("Total Length of Fwd Packets", 0))
        bwd_bytes = int(feat.get("Total Length of Bwd Packets", 0))
        self.total_fwd_bytes += max(0, fwd_bytes)
        self.total_bwd_bytes += max(0, bwd_bytes)

        if is_anomaly:
            self.anomalous_events_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert profile to serializable dictionary."""
        top_ports = [port for port, _ in self.accessed_ports.most_common(5)]
        return {
            "ip_address": self.ip_address,
            "total_connections_seen": self.total_connections_seen,
            "first_seen_timestamp": self.first_seen_timestamp,
            "last_seen_timestamp": self.last_seen_timestamp,
            "top_ports": top_ports,
            "unique_destinations_count": len(self.contacted_destinations),
            "total_fwd_bytes": self.total_fwd_bytes,
            "total_bwd_bytes": self.total_bwd_bytes,
            "anomalous_events_count": self.anomalous_events_count,
        }


class HostProfileManager:
    """Bounded, LRU-managed repository of host profiles preventing memory exhaustion."""

    def __init__(self, max_hosts: int = 10000) -> None:
        self.max_hosts = max_hosts
        self.profiles: OrderedDict[str, HostProfile] = OrderedDict()

    def get_or_create(self, ip_address: str) -> HostProfile:
        """Fetch profile for host, updating LRU access position, or create new."""
        if ip_address in self.profiles:
            self.profiles.move_to_end(ip_address)
            return self.profiles[ip_address]

        if len(self.profiles) >= self.max_hosts:
            # Evict oldest visited profile
            self.profiles.popitem(last=False)

        profile = HostProfile(ip_address=ip_address)
        self.profiles[ip_address] = profile
        return profile

    def record_event(
        self, ip_address: str, event: NetworkEvent, is_anomaly: bool = False
    ) -> HostProfile:
        """Record an event for a specific host IP."""
        profile = self.get_or_create(ip_address)
        profile.update_from_event(event, is_anomaly=is_anomaly)
        return profile

    def __contains__(self, ip_address: str) -> bool:
        return ip_address in self.profiles

    def __len__(self) -> int:
        return len(self.profiles)
