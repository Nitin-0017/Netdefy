"""NETDEFY — Intra-Flow Behavioral Feature Builder.

Extracts directional packet/byte asymmetries, transfer burstiness indices,
active/idle periodicities, and protocol flag signatures from network flow features.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from netdefy.behaviour.schema import IntraFlowBehavior
from netdefy.preprocessing.schema import map_destination_port_to_service

logger = logging.getLogger(__name__)


class BehavioralFeatureBuilder:
    """Builds Tier A intra-flow behavioral metrics with optional scaler inversion."""

    def __init__(
        self,
        scaler_path: Path | str | None = None,
        feature_names: list[str] | None = None,
    ) -> None:
        self.feature_names = feature_names or []
        self.scaler = None
        self.scaler_center: dict[str, float] = {}
        self.scaler_scale: dict[str, float] = {}

        if scaler_path is not None:
            p = Path(scaler_path).resolve()
            if p.exists():
                self.scaler = joblib.load(p)
                if hasattr(self.scaler, "center_") and hasattr(self.scaler, "scale_"):
                    self.scaler_center = dict(self.scaler.center_)
                    self.scaler_scale = dict(self.scaler.scale_)
                    if not self.feature_names and hasattr(self.scaler, "feature_names_in_"):
                        self.feature_names = list(self.scaler.feature_names_in_)
                elif hasattr(self.scaler, "feature_names_in_") and hasattr(self.scaler, "mean_"):
                    for i, name in enumerate(self.scaler.feature_names_in_):
                        self.scaler_center[name] = float(self.scaler.mean_[i])
                        self.scaler_scale[name] = float(self.scaler.scale_[i])
                    if not self.feature_names:
                        self.feature_names = list(self.scaler.feature_names_in_)

    def _get_val(
        self,
        feat_dict: dict[str, float],
        name: str,
        default: float = 0.0,
        unscale: bool = False,
    ) -> float:
        val = feat_dict.get(name, default)
        if unscale and name in self.scaler_scale:
            # Physical = z * scale + mean
            return val * self.scaler_scale[name] + self.scaler_center[name]
        return val

    def compute_intra_flow(
        self,
        flow: dict[str, float] | pd.Series | np.ndarray,
        feature_names: list[str] | None = None,
        is_scaled: bool = False,
        destination_port: int | None = None,
    ) -> IntraFlowBehavior:
        """Compute Tier A intra-flow behavioral metrics for a single flow."""
        names = feature_names or self.feature_names

        if isinstance(flow, np.ndarray):
            feat_dict = {names[i]: float(flow[i]) for i in range(min(len(names), len(flow)))}
        elif isinstance(flow, pd.Series):
            feat_dict = {}
            for k, v in flow.to_dict().items():
                with contextlib.suppress(ValueError, TypeError):
                    feat_dict[str(k)] = float(v)
        elif isinstance(flow, dict):
            feat_dict = {}
            for k, v in flow.items():
                with contextlib.suppress(ValueError, TypeError):
                    feat_dict[str(k)] = float(v)
        else:
            raise TypeError(f"Unsupported flow data type: {type(flow)}")

        # Retrieve relevant physical flow counters
        fwd_pkts = max(0.0, self._get_val(feat_dict, "Total Fwd Packets", 0.0, unscale=is_scaled))
        bwd_pkts = max(
            0.0, self._get_val(feat_dict, "Total Backward Packets", 0.0, unscale=is_scaled)
        )
        fwd_bytes = max(
            0.0, self._get_val(feat_dict, "Total Length of Fwd Packets", 0.0, unscale=is_scaled)
        )
        bwd_bytes = max(
            0.0, self._get_val(feat_dict, "Total Length of Bwd Packets", 0.0, unscale=is_scaled)
        )
        duration = max(0.0, self._get_val(feat_dict, "Flow Duration", 0.0, unscale=is_scaled))

        iat_mean = max(0.0, self._get_val(feat_dict, "Flow IAT Mean", 0.0, unscale=is_scaled))
        iat_std = max(0.0, self._get_val(feat_dict, "Flow IAT Std", 0.0, unscale=is_scaled))
        fwd_iat_mean = max(0.0, self._get_val(feat_dict, "Fwd IAT Mean", 0.0, unscale=is_scaled))
        bwd_iat_mean = max(0.0, self._get_val(feat_dict, "Bwd IAT Mean", 0.0, unscale=is_scaled))
        active_mean = max(0.0, self._get_val(feat_dict, "Active Mean", 0.0, unscale=is_scaled))

        win_fwd = self._get_val(feat_dict, "Init_Win_bytes_forward", 0.0, unscale=is_scaled)
        win_bwd = self._get_val(feat_dict, "Init_Win_bytes_backward", 0.0, unscale=is_scaled)

        # 1. Directional Ratios
        dir_pkt_ratio = float(fwd_pkts / (bwd_pkts + 1.0))
        dir_byte_ratio = float((fwd_bytes + 1.0) / (bwd_bytes + 1.0))

        # 2. Burstiness Index (Coefficient of Variation of IAT)
        burstiness_idx = float(iat_std / (iat_mean + 1e-6))

        # 3. IAT Directional Asymmetry
        max_iat = max(fwd_iat_mean, bwd_iat_mean, 1.0)
        iat_asym = float((fwd_iat_mean - bwd_iat_mean) / max_iat)

        # 4. Active Duration Ratio
        active_ratio = float(min(1.0, active_mean / (duration + 1.0)))

        # 5. Window Disparity
        max_win = max(abs(win_fwd), abs(win_bwd), 1.0)
        win_disp = float((win_fwd - win_bwd) / max_win)

        # 6. PortScan Closed-Port Signature: 1 forward packet, 1 backward packet, 6-40 backward bytes (TCP RST)
        is_scan = bool(
            (0.8 <= fwd_pkts <= 1.2) and (0.8 <= bwd_pkts <= 1.2) and (4.0 <= bwd_bytes <= 40.0)
        )

        # 7. Service category
        port = (
            destination_port
            if destination_port is not None
            else int(feat_dict.get("Destination Port", -1))
        )
        service_cat = map_destination_port_to_service(port) if port >= 0 else "UNKNOWN"

        return IntraFlowBehavior(
            directional_packet_ratio=dir_pkt_ratio,
            directional_byte_ratio=dir_byte_ratio,
            burstiness_index=burstiness_idx,
            iat_asymmetry=iat_asym,
            active_duration_ratio=active_ratio,
            window_disparity=win_disp,
            is_scan_signature=is_scan,
            service_category=service_cat,
        )

    def compute_intra_flow_batch(
        self,
        X: pd.DataFrame | np.ndarray,
        feature_names: list[str] | None = None,
        is_scaled: bool = False,
    ) -> list[IntraFlowBehavior]:
        """Compute Tier A intra-flow behavioral metrics across a batch."""
        names = feature_names or self.feature_names
        behaviors: list[IntraFlowBehavior] = []

        if isinstance(X, pd.DataFrame):
            for _, row in X.iterrows():
                behaviors.append(self.compute_intra_flow(row, names, is_scaled=is_scaled))
        else:
            arr = np.asarray(X, dtype=np.float32)
            for i in range(len(arr)):
                behaviors.append(self.compute_intra_flow(arr[i], names, is_scaled=is_scaled))

        return behaviors
