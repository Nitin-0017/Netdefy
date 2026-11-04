"""Unit tests for Netdefy error analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd

from netdefy.evaluation.error_analysis import (
    analyze_ambiguity_impact,
    analyze_false_negatives,
    analyze_false_positives,
)


def test_analyze_false_positives() -> None:
    df = pd.DataFrame(
        {
            "Label": ["BENIGN"] * 20,
            "feature1": [1.0] * 18 + [50.0, 100.0],
            "feature2": [2.0] * 20,
        }
    )
    scores = np.array([0.2] * 18 + [0.8, 0.9], dtype=np.float32)

    res = analyze_false_positives(
        df=df,
        anomaly_scores=scores,
        threshold=0.5,
        feature_columns=["feature1", "feature2"],
        label_column="Label",
        benign_label="BENIGN",
        top_k=2,
    )

    assert res["total_benign"] == 20
    assert res["false_positive_count"] == 2
    assert res["false_positive_rate"] == 0.1
    assert len(res["top_false_positives"]) == 2
    assert "feature1" in res["divergent_features"]


def test_analyze_false_negatives() -> None:
    df = pd.DataFrame(
        {
            "Label": ["BENIGN"] * 10 + ["PortScan"] * 5 + ["DDoS"] * 5,
        }
    )
    # PortScan has low scores (missed), DDoS has high scores (detected)
    scores = np.array([0.1] * 10 + [0.2] * 5 + [0.9] * 5, dtype=np.float32)

    res = analyze_false_negatives(
        df=df,
        anomaly_scores=scores,
        threshold=0.5,
        label_column="Label",
        benign_label="BENIGN",
    )

    assert res["total_attacks"] == 10
    assert res["total_false_negatives"] == 5
    assert res["evasion_by_attack_class"]["PortScan"]["recall"] == 0.0
    assert res["evasion_by_attack_class"]["DDoS"]["recall"] == 1.0


def test_analyze_ambiguity_impact() -> None:
    df = pd.DataFrame(
        {
            "Label": ["BENIGN", "BENIGN", "PortScan", "PortScan"],
        }
    )
    scores = np.array([0.8, 0.2, 0.8, 0.2], dtype=np.float32)
    is_ambiguous = [True, False, True, False]

    res = analyze_ambiguity_impact(
        df=df,
        anomaly_scores=scores,
        threshold=0.5,
        is_ambiguous_flags=is_ambiguous,
        label_column="Label",
        benign_label="BENIGN",
    )

    assert "ambiguous" in res
    assert "disambiguated" in res
    assert res["ambiguous"]["sample_count"] == 2
    assert res["disambiguated"]["sample_count"] == 2
