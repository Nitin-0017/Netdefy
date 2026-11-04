"""Unit tests for AutoencoderEvaluator and evaluation bundle serialization."""

from __future__ import annotations

import numpy as np
import pandas as pd

from netdefy.evaluation.autoencoder_evaluator import AutoencoderEvaluator
from netdefy.models.autoencoder import (
    AutoencoderArchitectureConfig,
    AutoencoderDetector,
    DeepAutoencoder,
)


def test_autoencoder_evaluator_evaluate_test_holdout() -> None:
    """Verify evaluator processes test dataframe and builds complete metric bundle."""
    config = AutoencoderArchitectureConfig(
        input_dim=4, encoder_dims=(3,), latent_dim=2, decoder_dims=(3,)
    )
    model = DeepAutoencoder(config=config)
    detector = AutoencoderDetector(model=model, config=config, device="cpu")
    detector.feature_names = ["f0", "f1", "f2", "f3"]
    detector.is_fitted = True

    # 20 samples: 15 BENIGN, 5 ATTACK
    np.random.seed(42)
    features = np.random.randn(20, 4).astype(np.float32)
    labels = ["BENIGN"] * 15 + ["DDoS"] * 5
    df = pd.DataFrame(features, columns=["f0", "f1", "f2", "f3"])
    df["Label"] = labels

    thresholds = {"p95.0": 0.5, "p99.0": 1.0}
    is_ambiguous = [False] * 18 + [True] * 2

    evaluator = AutoencoderEvaluator(
        detector=detector,
        feature_columns=["f0", "f1", "f2", "f3"],
        label_column="Label",
        benign_label="BENIGN",
    )

    bundle = evaluator.evaluate_test_holdout(
        test_df=df,
        thresholds=thresholds,
        is_ambiguous_flags=is_ambiguous,
        default_threshold_key="p99.0",
        batch_size=8,
    )

    assert bundle.total_test_samples == 20
    assert bundle.unambiguous_samples == 18
    assert bundle.ambiguous_samples == 2
    assert bundle.latency_ms_per_flow > 0.0
    assert bundle.throughput_flows_per_second > 0.0

    # Serialization tests
    metrics_dict = bundle.to_test_metrics_dict()
    assert metrics_dict["model_type"] == "deep_autoencoder"
    assert "full_test_report" in metrics_dict
    assert "disambiguated_test_report" in metrics_dict

    error_dict = bundle.to_error_analysis_dict("p99.0", 1.0)
    assert error_dict["evaluation_threshold"]["key"] == "p99.0"
    assert "false_positive_analysis" in error_dict
    assert "false_negative_analysis" in error_dict
    assert "ambiguity_comparison_by_threshold" in error_dict
