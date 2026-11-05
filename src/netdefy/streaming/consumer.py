"""NETDEFY — Stream Consumer & Hybrid Inference Worker (Phase 6).

Consumes validated network flow events from the message broker, executes
Phase 3 preprocessing, Phase 4D hybrid multi-model scoring, and Phase 5
behavioural context tracking, synthesizing and persisting SOC alerts.
"""

from __future__ import annotations

import logging
import time

import pandas as pd

from netdefy.alerts.alert_engine import AlertEngine
from netdefy.alerts.correlation import AlertCorrelator
from netdefy.behaviour.pipeline_adapter import BehavioralHybridPipeline
from netdefy.behaviour.schema import NetworkEvent
from netdefy.integrations.siem_export import SIEMExportRouter
from netdefy.storage.alert_repository import AlertRepository
from netdefy.streaming.adaptive_baseline import AdaptiveBaselinePolicy
from netdefy.streaming.broker_interface import MessageBroker, StreamMessage
from netdefy.streaming.dead_letter_queue import DeadLetterQueue
from netdefy.streaming.event_schema import NetworkFlowEvent
from netdefy.streaming.metrics import StreamMetrics

logger = logging.getLogger(__name__)


class StreamConsumer:
    """Production stream worker orchestrating inference, alert generation, and offset commit."""

    def __init__(
        self,
        broker: MessageBroker,
        stream: str = "netdefy:events:stream",
        group: str = "netdefy-engine-cg",
        consumer_name: str = "consumer-worker-01",
        pipeline: BehavioralHybridPipeline | None = None,
        alert_engine: AlertEngine | None = None,
        alert_repository: AlertRepository | None = None,
        alert_correlator: AlertCorrelator | None = None,
        siem_router: SIEMExportRouter | None = None,
        dlq: DeadLetterQueue | None = None,
        metrics: StreamMetrics | None = None,
        adaptive_baseline: AdaptiveBaselinePolicy | None = None,
    ) -> None:
        self.broker = broker
        self.stream = stream
        self.group = group
        self.consumer_name = consumer_name
        self.pipeline = pipeline
        self.alert_engine = alert_engine or AlertEngine()
        self.alert_repository = alert_repository
        self.alert_correlator = alert_correlator or AlertCorrelator()
        self.siem_router = siem_router or SIEMExportRouter()
        self.dlq = dlq or DeadLetterQueue(broker=broker)
        self.metrics = metrics or StreamMetrics()
        self.adaptive_baseline = adaptive_baseline or AdaptiveBaselinePolicy()

        # Initialize consumer group
        try:
            self.broker.create_consumer_group(
                self.stream, self.group, start_id="0", make_stream=True
            )
        except Exception as e:
            logger.debug("Group creation note: %s", e)

    def _convert_to_network_event(self, event: NetworkFlowEvent) -> NetworkEvent:
        """Map canonical NetworkFlowEvent to Phase 5 NetworkEvent dataclass."""
        ts_sec = float(event.event_timestamp.timestamp())
        proto_int = (
            6
            if "tcp" in event.source.protocol.lower()
            else (17 if "udp" in event.source.protocol.lower() else 0)
        )

        return NetworkEvent(
            flow_id=event.event_id,
            timestamp=ts_sec,
            source_ip=event.source.source_ip,
            destination_ip=event.source.destination_ip,
            source_port=event.source.source_port or 0,
            destination_port=event.source.destination_port,
            protocol=proto_int,
            features=event.features,
        )

    def _extract_feature_series(self, event: NetworkFlowEvent) -> pd.Series:
        """Construct canonical 76-feature Series for inference."""
        if self.pipeline and self.pipeline.feature_names:
            expected = self.pipeline.feature_names
            data = {f: float(event.features.get(f, 0.0)) for f in expected}
            return pd.Series(data)

        # Fallback if pipeline features are empty
        return pd.Series(event.features)

    def process_single_message(self, msg: StreamMessage) -> tuple[bool, str | None]:
        """Process one stream message through hybrid scoring, alert creation, and offset commit."""
        start_t = time.time()
        payload = msg.payload

        # 1. Parse and validate schema
        try:
            event = NetworkFlowEvent.model_validate(payload)
        except Exception as e:
            # Poison pill: route to DLQ and ACK to prevent infinite loop
            self.dlq.route_to_dlq(
                original_payload=payload,
                error_code="INVALID_PAYLOAD",
                error_message=str(e),
                message_id=msg.message_id,
                attempt_count=msg.delivery_count,
            )
            self.broker.ack(self.stream, self.group, [msg.message_id])
            self.metrics.record_dlq(1)
            return False, "POISON_PILL_QUARANTINED"

        # 2. Hybrid inference and behavioural analysis
        infer_start = time.time()
        b_event = self._convert_to_network_event(event)
        features_series = self._extract_feature_series(event)

        if self.pipeline is not None:
            prediction = self.pipeline.predict_flow(
                flow=features_series,
                event=b_event,
                is_scaled=False,
                flow_id=event.event_id,
            )
        else:
            # Mock / fallback prediction if pipeline not injected
            from netdefy.behaviour.schema import (
                BehavioralDecisionCategory,
                BehavioralEvidence,
                EnhancedHybridPrediction,
                IntraFlowBehavior,
            )
            from netdefy.hybrid.schemas import (
                AnomalyEvidence,
                ClassifierEvidence,
                DecisionCategory,
                FlowExplanation,
                HybridFlowPrediction,
            )

            dummy_anom = AnomalyEvidence(
                isolation_forest_raw_score=0.5,
                isolation_forest_calibrated_score=0.5,
                autoencoder_raw_error=0.01,
                autoencoder_calibrated_score=0.5,
                fused_score=0.5,
                threshold=0.982,
                is_anomaly=False,
            )
            dummy_clf = ClassifierEvidence(
                predicted_class="BENIGN",
                top_probability=0.99,
                second_probability=0.01,
                probability_margin=0.98,
                entropy=0.01,
                rejected=False,
                rejection_reason=None,
            )
            dummy_exp = FlowExplanation(
                decision=DecisionCategory.NORMAL,
                decision_reason="Normal benign traffic",
            )
            dummy_p4d = HybridFlowPrediction(
                decision=DecisionCategory.NORMAL,
                decision_reason="Normal benign traffic",
                anomaly=dummy_anom,
                classifier=dummy_clf,
                explanation=dummy_exp,
                flow_id=event.event_id,
            )
            prediction = EnhancedHybridPrediction(
                flow_id=event.event_id,
                original_phase4d_decision="NORMAL",
                behavioral_decision=BehavioralDecisionCategory.NORMAL,
                final_decision="NORMAL",
                decision_reason="Normal baseline traffic",
                phase4d_evidence=dummy_p4d.to_dict(),
                behavioral_evidence=BehavioralEvidence(
                    decision=BehavioralDecisionCategory.NORMAL,
                    intra_flow=IntraFlowBehavior(
                        directional_packet_ratio=0.5,
                        directional_byte_ratio=0.5,
                        burstiness_index=0.0,
                        iat_asymmetry=0.0,
                        active_duration_ratio=1.0,
                        window_disparity=0.0,
                        is_scan_signature=False,
                    ),
                ),
            )

        infer_ms = (time.time() - infer_start) * 1000.0

        # 3. Update Adaptive Baseline (with strict anti-poisoning gate)
        p4d_ev = prediction.phase4d_evidence
        anom_score = float(
            p4d_ev.get("anomaly", {}).get(
                "fused_score", p4d_ev.get("anomaly", {}).get("fused_anomaly_score", 0.5)
            )
        )
        pred_threat = p4d_ev.get("classifier", {}).get("predicted_class", "BENIGN")
        has_b_flag = prediction.behavioral_decision.value != "NORMAL"
        self.adaptive_baseline.update(
            anomaly_score=anom_score,
            decision=prediction.final_decision,
            supervised_label=pred_threat,
            has_behavioral_flag=has_b_flag,
        )

        # 4. Synthesize Alert (if suspicious / review-required)
        persist_start = time.time()
        alert = self.alert_engine.generate_alert(prediction, event)

        if alert is not None:
            # Persist alert idempotently to database
            if self.alert_repository is not None:
                _, is_created = self.alert_repository.create_alert(alert)
                self.metrics.record_alert(
                    generated=True, persisted=is_created, is_duplicate=not is_created
                )
            else:
                self.metrics.record_alert(generated=True, persisted=False)

            # Correlate alert
            self.alert_correlator.correlate(alert)

            # Export to SIEM sinks (CEF and STIX)
            self.siem_router.export_alert(alert, format="ALL")

        persist_ms = (time.time() - persist_start) * 1000.0
        e2e_ms = (time.time() - start_t) * 1000.0

        # 5. Acknowledge message offset
        self.broker.ack(self.stream, self.group, [msg.message_id])

        # Record metrics
        self.metrics.record_processed(
            count=1,
            inference_ms=infer_ms,
            persistence_ms=persist_ms,
            e2e_ms=e2e_ms,
        )

        return True, prediction.final_decision

    def consume_batch(self, count: int = 50, block_ms: int = 1000) -> int:
        """Fetch and process up to `count` messages from stream."""
        messages = self.broker.read_group(
            stream=self.stream,
            group=self.group,
            consumer=self.consumer_name,
            count=count,
            block_ms=block_ms,
        )
        if not messages:
            return 0

        success_count = 0
        for msg in messages:
            ok, _ = self.process_single_message(msg)
            if ok:
                success_count += 1

        return success_count
