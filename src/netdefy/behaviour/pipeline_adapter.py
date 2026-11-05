"""NETDEFY — Behavioral Hybrid Pipeline Adapter.

Augments Phase 4D Hybrid Intelligence with Phase 5 Intra-Flow and Multi-Flow
Context, producing EnhancedHybridPrediction with graceful degradation when
sequential host or timestamp metadata is absent.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from netdefy.behaviour.burst_detection import BurstDetector
from netdefy.behaviour.destination_diversity import DestinationDiversityAnalyzer
from netdefy.behaviour.feature_builder import BehavioralFeatureBuilder
from netdefy.behaviour.schema import (
    BehavioralDecisionCategory,
    BehavioralEvidence,
    EnhancedHybridPrediction,
    IntraFlowBehavior,
    MultiFlowContext,
    NetworkEvent,
)
from netdefy.behaviour.window_aggregator import WindowAggregator, WindowAggregatorConfig
from netdefy.hybrid.inference_pipeline import HybridInferencePipeline
from netdefy.hybrid.schemas import DecisionCategory, HybridFlowPrediction

logger = logging.getLogger(__name__)


class BehavioralHybridPipeline:
    """Integrated engine fusing Phase 4D hybrid multi-model inference with Phase 5 behavioral analysis."""

    def __init__(
        self,
        hybrid_pipeline: HybridInferencePipeline,
        feature_builder: BehavioralFeatureBuilder | None = None,
        window_aggregator: WindowAggregator | None = None,
        diversity_analyzer: DestinationDiversityAnalyzer | None = None,
        burst_detector: BurstDetector | None = None,
    ) -> None:
        self.hybrid = hybrid_pipeline
        self.feature_names = hybrid_pipeline.feature_names
        self.builder = feature_builder or BehavioralFeatureBuilder(feature_names=self.feature_names)
        self.window_aggregator = window_aggregator or WindowAggregator(
            WindowAggregatorConfig(window_duration_seconds=30.0)
        )
        self.diversity_analyzer = diversity_analyzer or DestinationDiversityAnalyzer()
        self.burst_detector = burst_detector or BurstDetector()

    def evaluate_behavior(
        self,
        intra_flow: IntraFlowBehavior,
        event: NetworkEvent | None = None,
    ) -> tuple[BehavioralDecisionCategory, MultiFlowContext | None, list[str], float]:
        """Synthesize behavioral category, multi-flow context, evidence, and confidence score."""
        evidence: list[str] = []
        confidence = 0.5
        multi_context: MultiFlowContext | None = None

        # 1. Intra-flow Tier A evaluations
        if intra_flow.is_scan_signature:
            evidence.append(
                "Matched PortScan closed-port signature: 1 forward packet, 1 backward packet, TCP RST byte range"
            )
            confidence = max(confidence, 0.90)

        if intra_flow.burstiness_index > 5.0:
            evidence.append(
                f"Elevated packet IAT burstiness index: {intra_flow.burstiness_index:.2f} (erratic/pulsed transmission)"
            )
            confidence = max(confidence, 0.75)
        elif intra_flow.burstiness_index < 0.05 and intra_flow.directional_packet_ratio > 3.0:
            evidence.append(
                f"Near-zero IAT variance: {intra_flow.burstiness_index:.3f} (automated periodic beaconing)"
            )
            confidence = max(confidence, 0.70)

        if intra_flow.directional_packet_ratio > 10.0:
            evidence.append(
                f"Extreme forward-to-backward packet asymmetry: {intra_flow.directional_packet_ratio:.1f}:1"
            )

        # 2. Tier B Multi-flow evaluations (if timestamp/IP context provided)
        has_temporal_context = event is not None and event.timestamp is not None
        if has_temporal_context:
            assert event is not None
            self.window_aggregator.add_event(event)
            multi_context = self.window_aggregator.get_context(event.timestamp)
            events_in_window = list(self.window_aggregator.events)

            # Analyze destination and port diversity
            div_profile = self.diversity_analyzer.analyze(events_in_window)
            if div_profile.is_horizontal_scan:
                evidence.append(
                    f"Multi-flow horizontal scan detected: {div_profile.unique_destination_ips} destinations "
                    f"probed in window (fan-out {div_profile.destination_fan_out_ratio:.2f})"
                )
                confidence = max(confidence, 0.95)
            elif div_profile.is_vertical_scan:
                evidence.append(
                    f"Multi-flow vertical port scan detected: {div_profile.unique_destination_ports} ports "
                    f"probed on single host (fan-out {div_profile.port_fan_out_ratio:.2f})"
                )
                confidence = max(confidence, 0.95)

            # Analyze connection rate and burst status
            burst_status = self.burst_detector.update_and_check(multi_context.connection_rate)
            if burst_status.is_burst:
                evidence.append(
                    f"Traffic rate burst detected: {burst_status.current_rate:.1f} conns/sec "
                    f"(Z-score {burst_status.rate_z_score:.2f}, baseline {burst_status.baseline_rate:.1f})"
                )
                confidence = max(confidence, 0.85)
                multi_context = MultiFlowContext(
                    window_duration_seconds=multi_context.window_duration_seconds,
                    connection_count=multi_context.connection_count,
                    unique_destinations=multi_context.unique_destinations,
                    unique_destination_ports=multi_context.unique_destination_ports,
                    destination_diversity_ratio=multi_context.destination_diversity_ratio,
                    port_diversity_ratio=multi_context.port_diversity_ratio,
                    connection_rate=multi_context.connection_rate,
                    burst_z_score=burst_status.rate_z_score,
                )

        # Decide behavioral category
        if intra_flow.is_scan_signature or (
            has_temporal_context
            and multi_context is not None
            and (
                multi_context.destination_diversity_ratio >= 0.7
                or multi_context.port_diversity_ratio >= 0.7
            )
        ):
            category = BehavioralDecisionCategory.SCANNING_BEHAVIOUR
        elif (
            has_temporal_context
            and multi_context is not None
            and multi_context.burst_z_score >= 3.0
        ):
            category = BehavioralDecisionCategory.BURST_ACTIVITY
        elif evidence:
            category = BehavioralDecisionCategory.SUSPICIOUS_BEHAVIOUR
        elif not has_temporal_context:
            category = BehavioralDecisionCategory.INSUFFICIENT_CONTEXT
        else:
            category = BehavioralDecisionCategory.NORMAL

        return category, multi_context, evidence, confidence

    def predict_flow(
        self,
        flow: dict[str, float] | pd.Series | np.ndarray,
        event: NetworkEvent | None = None,
        is_scaled: bool = False,
        flow_id: Any = None,
    ) -> EnhancedHybridPrediction:
        """Execute unified Phase 4D + Phase 5 inference on a single network traffic flow."""
        # 1. Execute Phase 4D Hybrid Prediction
        phase4d_pred: HybridFlowPrediction = self.hybrid.predict(flow=flow, flow_id=flow_id)

        # 2. Extract Tier A Intra-Flow Behavior
        intra_flow = self.builder.compute_intra_flow(
            flow=flow,
            feature_names=self.feature_names,
            is_scaled=is_scaled,
            destination_port=event.destination_port if event else None,
        )

        # 3. Evaluate Behavioral Context
        b_cat, m_ctx, ev_list, b_conf = self.evaluate_behavior(intra_flow, event)
        behavioral_evidence = BehavioralEvidence(
            decision=b_cat,
            intra_flow=intra_flow,
            multi_flow=m_ctx,
            evidence_summary=ev_list,
            confidence_score=b_conf,
        )

        # 4. Integrate Phase 4D and Phase 5 Final Decision
        final_decision, reason = self._integrate_decisions(phase4d_pred, behavioral_evidence)

        model_versions = dict(phase4d_pred.model_versions)
        model_versions["behaviour_engine"] = "v1"

        return EnhancedHybridPrediction(
            flow_id=flow_id or phase4d_pred.flow_id,
            original_phase4d_decision=phase4d_pred.decision.value,
            behavioral_decision=b_cat,
            final_decision=final_decision,
            decision_reason=reason,
            phase4d_evidence=phase4d_pred.to_dict(),
            behavioral_evidence=behavioral_evidence,
            model_versions=model_versions,
        )

    def _integrate_decisions(
        self,
        phase4d: HybridFlowPrediction,
        behavioral: BehavioralEvidence,
    ) -> tuple[str, str]:
        """Synthesize final decision and actionable operational reason."""
        p4d_dec = phase4d.decision
        b_cat = behavioral.decision

        # High priority 1: PortScan confirmation
        if (
            phase4d.classifier.predicted_class == "PortScan"
            and behavioral.intra_flow.is_scan_signature
        ):
            return (
                DecisionCategory.SUSPICIOUS_KNOWN.value,
                "Confirmed PortScan: Supervised classifier and intra-flow RST signature both indicate active port probe",
            )

        # High priority 2: Behavioral scan detection elevates normal or review
        if b_cat == BehavioralDecisionCategory.SCANNING_BEHAVIOUR and p4d_dec in (
            DecisionCategory.NORMAL,
            DecisionCategory.REVIEW_REQUIRED,
        ):
            return (
                DecisionCategory.SUSPICIOUS_KNOWN.value,
                "Behavioral Scanning Alert: Intra-flow or multi-flow scanning pattern detected despite ambiguous flow score",
            )

        # High priority 3: Known attack with behavioral corroboration
        if p4d_dec == DecisionCategory.SUSPICIOUS_KNOWN:
            return (
                DecisionCategory.SUSPICIOUS_KNOWN.value,
                f"Threat Confirmed: {phase4d.classifier.predicted_class} with supporting flow telemetry",
            )

        # High priority 4: Burst activity under unknown anomaly
        if p4d_dec == DecisionCategory.SUSPICIOUS_UNKNOWN:
            if b_cat == BehavioralDecisionCategory.BURST_ACTIVITY:
                return (
                    DecisionCategory.SUSPICIOUS_UNKNOWN.value,
                    "Zero-Day / Unknown Volumetric Anomaly: High anomaly score combined with significant rate burst",
                )
            return (
                DecisionCategory.SUSPICIOUS_UNKNOWN.value,
                phase4d.decision_reason,
            )

        # Fallback to Phase 4D decision
        return p4d_dec.value, phase4d.decision_reason

    def predict_batch(
        self,
        X: pd.DataFrame | np.ndarray,
        events: Sequence[NetworkEvent] | None = None,
        is_scaled: bool = False,
        flow_ids: list[Any] | None = None,
    ) -> list[EnhancedHybridPrediction]:
        """Execute unified Phase 4D + Phase 5 inference across a batch of flows."""
        n_flows = len(X)
        ids = flow_ids or list(range(n_flows))
        results: list[EnhancedHybridPrediction] = []

        if isinstance(X, pd.DataFrame):
            for i in range(n_flows):
                ev = events[i] if events and i < len(events) else None
                row = X.iloc[i]
                pred = self.predict_flow(flow=row, event=ev, is_scaled=is_scaled, flow_id=ids[i])
                results.append(pred)
        else:
            arr = np.asarray(X, dtype=np.float32)
            for i in range(n_flows):
                ev = events[i] if events and i < len(events) else None
                pred = self.predict_flow(flow=arr[i], event=ev, is_scaled=is_scaled, flow_id=ids[i])
                results.append(pred)

        return results
