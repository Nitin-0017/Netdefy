"""Unit tests for NETDEFY Deep Autoencoder neural architecture and detector."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from netdefy.models.autoencoder import (
    AutoencoderArchitectureConfig,
    AutoencoderDetector,
    DeepAutoencoder,
)


def test_autoencoder_architecture_dimensions() -> None:
    """Verify input, hidden, latent, and output dimensions."""
    config = AutoencoderArchitectureConfig(
        input_dim=76,
        encoder_dims=(64, 32, 16),
        latent_dim=8,
        decoder_dims=(16, 32, 64),
        activation="relu",
    )
    model = DeepAutoencoder(config=config)

    # 15,412 parameters:
    # Enc: (76*64+64) + (64*32+32) + (32*16+16) + (16*8+8) = 4928 + 2080 + 528 + 136 = 7672
    # Dec: (8*16+16) + (16*32+32) + (32*64+64) + (64*76+76) = 144 + 544 + 2112 + 4940 = 7740
    # Total = 15,412
    assert model.parameter_count == 15412


def test_autoencoder_forward_and_reconstruct_shapes() -> None:
    """Verify tensor shapes through encode, decode, and reconstruction passes."""
    config = AutoencoderArchitectureConfig(input_dim=76, latent_dim=8)
    model = DeepAutoencoder(config=config)
    model.eval()

    batch_size = 16
    x = torch.randn(batch_size, 76, dtype=torch.float32)

    # Latent projection shape
    z = model.encode(x)
    assert z.shape == (batch_size, 8)

    # Reconstruction shape
    x_hat = model.decode(z)
    assert x_hat.shape == (batch_size, 76)

    # Direct forward
    out = model(x)
    assert out.shape == (batch_size, 76)

    # Per-sample reconstruction error shape
    errors = model.reconstruction_error(x)
    assert errors.shape == (batch_size,)
    assert (errors >= 0.0).all()


def test_autoencoder_deterministic_initialization() -> None:
    """Verify identical random seeds produce bit-identical initial parameters."""
    cfg1 = AutoencoderArchitectureConfig(random_seed=123)
    cfg2 = AutoencoderArchitectureConfig(random_seed=123)
    cfg3 = AutoencoderArchitectureConfig(random_seed=999)

    m1 = DeepAutoencoder(config=cfg1)
    m2 = DeepAutoencoder(config=cfg2)
    m3 = DeepAutoencoder(config=cfg3)

    for p1, p2 in zip(m1.parameters(), m2.parameters(), strict=True):
        torch.testing.assert_close(p1, p2)

    # Different seed must produce different weights
    diff_found = False
    for p1, p3 in zip(m1.parameters(), m3.parameters(), strict=True):
        if not torch.allclose(p1, p3):
            diff_found = True
            break
    assert diff_found


def test_autoencoder_detector_fit_and_score_samples() -> None:
    """Verify AutoencoderDetector interface, score orientation, and predictions."""
    config = AutoencoderArchitectureConfig(
        input_dim=10, encoder_dims=(8,), latent_dim=4, decoder_dims=(8,)
    )
    base_model = DeepAutoencoder(config=config)
    detector = AutoencoderDetector(model=base_model, config=config, device="cpu")
    detector.feature_names = [f"f_{i}" for i in range(10)]
    detector.is_fitted = True

    # High anomaly vector (extreme outliers) vs normal vector (near zero)
    normal_data = np.zeros((5, 10), dtype=np.float32)
    anomaly_data = np.full((5, 10), fill_value=50.0, dtype=np.float32)

    normal_scores = detector.score_samples(normal_data)
    anomaly_scores = detector.score_samples(anomaly_data)

    assert normal_scores.shape == (5,)
    assert anomaly_scores.shape == (5,)
    assert normal_scores.dtype == np.float32

    # Higher score = more anomalous
    assert anomaly_scores.mean() > normal_scores.mean()

    # Binary prediction
    threshold = float((normal_scores.max() + anomaly_scores.min()) / 2.0)
    preds_normal = detector.predict(normal_data, threshold=threshold)
    preds_anomaly = detector.predict(anomaly_data, threshold=threshold)

    assert (preds_normal == 0).all()
    assert (preds_anomaly == 1).all()


def test_autoencoder_detector_nan_inf_rejection() -> None:
    """Verify detector rejects inputs with NaN or Inf."""
    config = AutoencoderArchitectureConfig(input_dim=5, latent_dim=2)
    detector = AutoencoderDetector(config=config, device="cpu")
    detector.feature_names = [f"f_{i}" for i in range(5)]
    detector.is_fitted = True

    bad_nan = np.zeros((3, 5), dtype=np.float32)
    bad_nan[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN or Inf"):
        detector.score_samples(bad_nan)

    bad_inf = np.zeros((3, 5), dtype=np.float32)
    bad_inf[1, 2] = np.inf
    with pytest.raises(ValueError, match="NaN or Inf"):
        detector.score_samples(bad_inf)


def test_autoencoder_detector_save_and_load_roundtrip() -> None:
    """Verify model save and load roundtrip with checksum computation."""
    config = AutoencoderArchitectureConfig(input_dim=8, latent_dim=4)
    model = DeepAutoencoder(config=config)
    detector = AutoencoderDetector(model=model, config=config, device="cpu")
    detector.feature_names = [f"feat_{i}" for i in range(8)]
    detector.is_fitted = True
    detector.train_sample_count = 100
    detector.train_duration_seconds = 1.23

    with tempfile.TemporaryDirectory() as tmp_dir:
        save_path = Path(tmp_dir) / "test_model.pt"
        sha256 = detector.save(save_path)
        assert save_path.exists()
        assert len(sha256) == 64

        loaded_detector = AutoencoderDetector.load(save_path, device="cpu")
        assert loaded_detector.is_fitted
        assert loaded_detector.feature_names == detector.feature_names
        assert loaded_detector.train_sample_count == 100
        assert loaded_detector.train_duration_seconds == 1.23

        # Test score parity
        x = np.random.randn(10, 8).astype(np.float32)
        orig_scores = detector.score_samples(x)
        loaded_scores = loaded_detector.score_samples(x)
        np.testing.assert_allclose(orig_scores, loaded_scores, rtol=1e-5)
