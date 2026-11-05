"""NETDEFY — Behavioral & Temporal Network Intelligence Engine (Phase 5).

Provides intra-flow behavioral feature extraction, multi-flow temporal sliding windows,
destination & port diversity analysis, burst detection, host profiling, temporal validation,
and hybrid pipeline integration.
"""

from __future__ import annotations

from netdefy.behaviour.behavioural_profiles import HostProfile, HostProfileManager
from netdefy.behaviour.burst_detection import BurstDetector, BurstStatus
from netdefy.behaviour.connection_patterns import (
    ConnectionPatternAnalyzer,
    ConnectionPatternProfile,
)
from netdefy.behaviour.destination_diversity import (
    DestinationDiversityAnalyzer,
    DiversityProfile,
)
from netdefy.behaviour.feature_builder import BehavioralFeatureBuilder
from netdefy.behaviour.pipeline_adapter import BehavioralHybridPipeline
from netdefy.behaviour.schema import (
    BehavioralDecisionCategory,
    BehavioralEvidence,
    EnhancedHybridPrediction,
    IntraFlowBehavior,
    MultiFlowContext,
    NetworkEvent,
)
from netdefy.behaviour.validation import TemporalValidationError, TemporalValidator
from netdefy.behaviour.window_aggregator import (
    WindowAggregator,
    WindowAggregatorConfig,
)

__all__ = [
    "BehavioralDecisionCategory",
    "BehavioralEvidence",
    "BehavioralFeatureBuilder",
    "BehavioralHybridPipeline",
    "BurstDetector",
    "BurstStatus",
    "ConnectionPatternAnalyzer",
    "ConnectionPatternProfile",
    "DestinationDiversityAnalyzer",
    "DiversityProfile",
    "EnhancedHybridPrediction",
    "HostProfile",
    "HostProfileManager",
    "IntraFlowBehavior",
    "MultiFlowContext",
    "NetworkEvent",
    "TemporalValidationError",
    "TemporalValidator",
    "WindowAggregator",
    "WindowAggregatorConfig",
]
