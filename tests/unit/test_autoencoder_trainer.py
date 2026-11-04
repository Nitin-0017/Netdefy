"""Unit tests for NETDEFY AutoencoderTrainer and training engine."""

from __future__ import annotations

import numpy as np
import pytest

from netdefy.models.autoencoder import AutoencoderArchitectureConfig, DeepAutoencoder
from netdefy.training.autoencoder_trainer import (
    AutoencoderTrainer,
    AutoencoderTrainingConfig,
)


def test_trainer_runs_and_decreases_loss() -> None:
    """Verify trainer executes and reduces loss on learnable data."""
    arch_cfg = AutoencoderArchitectureConfig(
        input_dim=10, encoder_dims=(8,), latent_dim=4, decoder_dims=(8,)
    )
    model = DeepAutoencoder(config=arch_cfg)

    train_cfg = AutoencoderTrainingConfig(
        learning_rate=0.01,
        epochs=15,
        batch_size=32,
        early_stopping_patience=10,
        device="cpu",
    )
    trainer = AutoencoderTrainer(model=model, config=train_cfg, device="cpu")

    # Generate synthetic correlated data
    np.random.seed(42)
    base = np.random.randn(200, 4)
    data = np.dot(base, np.random.randn(4, 10)).astype(np.float32)

    train_data = data[:150]
    val_data = data[150:]

    best_model, history = trainer.train(train_data, val_data)

    assert history.total_epochs_trained > 0
    assert len(history.train_losses) == history.total_epochs_trained
    assert len(history.val_losses) == history.total_epochs_trained
    # Final train loss should be significantly lower than initial loss
    assert history.train_losses[-1] < history.train_losses[0]
    assert history.best_val_loss > 0.0


def test_trainer_early_stopping_triggers() -> None:
    """Verify early stopping terminates when validation loss stops improving."""
    arch_cfg = AutoencoderArchitectureConfig(input_dim=8, latent_dim=2)
    model = DeepAutoencoder(config=arch_cfg)

    # Extreme min_delta forces early stopping quickly
    train_cfg = AutoencoderTrainingConfig(
        learning_rate=0.001,
        epochs=50,
        batch_size=16,
        early_stopping_patience=3,
        min_delta=100.0,  # Impossible threshold, ensures no epoch improves
        device="cpu",
    )
    trainer = AutoencoderTrainer(model=model, config=train_cfg, device="cpu")

    data = np.random.randn(100, 8).astype(np.float32)
    _, history = trainer.train(data[:80], data[80:])

    assert history.early_stopping_triggered
    # Must stop at or around epoch 4 (epoch 1 is best, then 3 without improvement)
    assert history.total_epochs_trained <= 5


def test_trainer_nan_inf_rejection() -> None:
    """Verify trainer rejects training matrices containing NaN or Inf."""
    arch_cfg = AutoencoderArchitectureConfig(input_dim=4, latent_dim=2)
    model = DeepAutoencoder(config=arch_cfg)
    trainer = AutoencoderTrainer(model=model, device="cpu")

    bad_data = np.zeros((10, 4), dtype=np.float32)
    bad_data[0, 0] = np.nan
    val_data = np.zeros((10, 4), dtype=np.float32)

    with pytest.raises(ValueError, match="NaN or Inf"):
        trainer.train(bad_data, val_data)


def test_trainer_invalid_optimizer_raises() -> None:
    """Verify trainer raises ValueError for unknown optimizer string."""
    arch_cfg = AutoencoderArchitectureConfig(input_dim=4, latent_dim=2)
    model = DeepAutoencoder(config=arch_cfg)
    cfg = AutoencoderTrainingConfig(optimizer="invalid_opt")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Unsupported optimizer"):
        AutoencoderTrainer(model=model, config=cfg)
