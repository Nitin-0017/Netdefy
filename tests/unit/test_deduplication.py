"""Unit tests for hash-indexed duplicate detection and exact-value verification."""

from __future__ import annotations

import pandas as pd
import pytest

from netdefy.preprocessing.deduplication import HashVerifiedDeduplicator


def test_deduplicator_intra_and_cross_partition() -> None:
    """Verify intra-partition and cross-partition duplicate separation."""
    feature_cols = ["Dur", "Bytes"]
    dedup = HashVerifiedDeduplicator(feature_columns=feature_cols, label_column="Label")

    # Training chunk with 1 duplicate (row 0 and row 2 are identical)
    train_chunk = pd.DataFrame(
        {
            "Dur": [10.0, 20.0, 10.0],
            "Bytes": [100.0, 200.0, 100.0],
            "Label": ["BENIGN", "BENIGN", "BENIGN"],
        }
    )

    raw_tr, dedup_tr = dedup.process_training_chunk(train_chunk)
    assert len(raw_tr) == 3
    assert len(dedup_tr) == 2  # Exactly 1 intra-training duplicate removed
    assert dedup.audits["train"].intra_partition_duplicates == 1
    assert dedup.audits["train"].retained_rows_view_b == 2

    # Validation chunk:
    # row 0 matches training (cross-partition overlap)
    # row 1 is unique validation flow
    # row 2 is identical to row 1 (intra-validation duplicate)
    val_chunk = pd.DataFrame(
        {
            "Dur": [10.0, 50.0, 50.0],
            "Bytes": [100.0, 500.0, 500.0],
            "Label": ["BENIGN", "SSH-Patator", "SSH-Patator"],
        }
    )

    dedup.reset_partition_context("validation")
    raw_val, dedup_val = dedup.process_eval_chunk(
        val_chunk, "validation", filter_cross_partition_leakage=True
    )

    assert len(raw_val) == 3
    assert (
        len(dedup_val) == 1
    )  # Only row 1 retained (row 0 was training overlap, row 2 was intra-val dup)
    assert dedup.audits["validation"].cross_partition_overlap == 1
    assert dedup.audits["validation"].intra_partition_duplicates == 1
    assert dedup.audits["validation"].retained_rows_view_b == 1
    assert dedup.audits["validation"].retained_attacks == 1


def test_hash_collision_verification_prevents_false_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that if two distinct rows yield the same hash, exact tuple matching prevents false dropping."""
    feature_cols = ["A", "B"]
    dedup = HashVerifiedDeduplicator(feature_columns=feature_cols)

    # Force a mock collision by overriding _compute_row_hash to return a constant for different tuples
    monkeypatch.setattr(dedup, "_compute_row_hash", lambda _: 424242)

    chunk = pd.DataFrame(
        {
            "A": [1.0, 99.0],  # Different values!
            "B": [2.0, 88.0],
            "Label": ["BENIGN", "BENIGN"],
        }
    )

    raw, dedup_df = dedup.process_training_chunk(chunk)

    # Because values (1.0, 2.0) != (99.0, 88.0), it must NOT drop row 1 despite hash collision!
    assert len(dedup_df) == 2
    assert dedup.audits["train"].intra_partition_duplicates == 0
    assert dedup.audits["train"].retained_rows_view_b == 2
