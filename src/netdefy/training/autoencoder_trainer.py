"""NETDEFY — Deep Autoencoder Training Engine.

Implements an unsupervised one-class neural training loop with AdamW optimizer,
mini-batch gradient updates, gradient clipping, and early stopping strictly on
benign validation reconstruction error.
"""

from __future__ import annotations

import copy
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from netdefy.models.autoencoder import DeepAutoencoder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoencoderTrainingConfig:
    """Hyperparameter and optimization configuration for AutoencoderTrainer."""

    learning_rate: float = 0.001
    weight_decay: float = 1e-5
    epochs: int = 100
    batch_size: int = 512
    early_stopping_patience: int = 10
    min_delta: float = 1e-5
    gradient_clip_val: float = 1.0
    optimizer: Literal["adamw", "adam"] = "adamw"
    random_seed: int = 42
    device: str = "cpu"
    num_workers: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutoencoderTrainingConfig:
        return cls(
            learning_rate=float(data.get("learning_rate", 0.001)),
            weight_decay=float(data.get("weight_decay", 1e-5)),
            epochs=int(data.get("epochs", 100)),
            batch_size=int(data.get("batch_size", 512)),
            early_stopping_patience=int(data.get("early_stopping_patience", 10)),
            min_delta=float(data.get("min_delta", 1e-5)),
            gradient_clip_val=float(data.get("gradient_clip_val", 1.0)),
            optimizer=data.get("optimizer", "adamw"),
            random_seed=int(data.get("random_seed", 42)),
            device=str(data.get("device", "cpu")),
            num_workers=int(data.get("num_workers", 0)),
        )


@dataclass
class TrainingHistory:
    """Complete per-epoch training and validation metrics history."""

    train_losses: list[float]
    val_losses: list[float]
    epoch_durations: list[float]
    best_epoch: int
    best_val_loss: float
    early_stopping_triggered: bool
    total_duration_seconds: float
    total_epochs_trained: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "train_losses": self.train_losses,
            "val_losses": self.val_losses,
            "epoch_durations": self.epoch_durations,
            "best_epoch": self.best_epoch,
            "best_val_loss": round(self.best_val_loss, 8),
            "early_stopping_triggered": self.early_stopping_triggered,
            "total_duration_seconds": round(self.total_duration_seconds, 3),
            "total_epochs_trained": self.total_epochs_trained,
        }


class AutoencoderTrainer:
    """Manages model training, optimization, and early stopping."""

    def __init__(
        self,
        model: DeepAutoencoder,
        config: AutoencoderTrainingConfig | None = None,
        device: torch.device | str | None = None,
    ) -> None:
        self.config = config or AutoencoderTrainingConfig()
        if device is not None:
            self.device = torch.device(device) if isinstance(device, str) else device
        else:
            self.device = torch.device(self.config.device)

        self.model = model.to(self.device)
        self.loss_fn = nn.MSELoss()

        # Deterministic seed
        torch.manual_seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)

        # Configure Optimizer
        self.optimizer: torch.optim.Optimizer
        if self.config.optimizer == "adamw":
            self.optimizer = torch.optim.AdamW(
                self.model.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )
        elif self.config.optimizer == "adam":
            self.optimizer = torch.optim.Adam(
                self.model.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
            )
        else:
            raise ValueError(f"Unsupported optimizer: {self.config.optimizer}")

    def train(
        self,
        train_features: np.ndarray,
        val_benign_features: np.ndarray,
    ) -> tuple[DeepAutoencoder, TrainingHistory]:
        """Execute one-class training on pure benign features with benign validation early stopping.

        Args:
            train_features: 2D numpy array [N, D] of pure benign training flows.
            val_benign_features: 2D numpy array [M, D] of pure benign validation flows.

        Returns:
            Tuple of (model_with_best_weights, training_history).
        """
        start_time = time.perf_counter()

        # Validate inputs
        if np.isnan(train_features).any() or np.isinf(train_features).any():
            raise ValueError("Training feature array contains NaN or Inf values!")
        if np.isnan(val_benign_features).any() or np.isinf(val_benign_features).any():
            raise ValueError("Validation feature array contains NaN or Inf values!")

        # Create PyTorch DataLoaders
        train_tensor = torch.from_numpy(train_features.astype(np.float32))
        train_dataset = TensorDataset(train_tensor)
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(self.config.random_seed),
            num_workers=self.config.num_workers,
        )

        val_tensor = torch.from_numpy(val_benign_features.astype(np.float32))
        val_dataset = TensorDataset(val_tensor)
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size * 2,
            shuffle=False,
            num_workers=self.config.num_workers,
        )

        train_losses: list[float] = []
        val_losses: list[float] = []
        epoch_durations: list[float] = []

        best_val_loss = float("inf")
        best_epoch = 0
        best_state_dict: dict[str, torch.Tensor] = copy.deepcopy(self.model.state_dict())
        epochs_without_improvement = 0
        stopped_early = False

        logger.info(
            "Starting Autoencoder Training (%d epochs, batch_size=%d, lr=%.6f, device=%s)",
            self.config.epochs,
            self.config.batch_size,
            self.config.learning_rate,
            self.device,
        )

        for epoch in range(1, self.config.epochs + 1):
            epoch_start = time.perf_counter()

            # --- Training Loop ---
            self.model.train()
            total_train_loss = 0.0
            total_train_batches = 0

            for (batch_x,) in train_loader:
                batch_x = batch_x.to(self.device)

                self.optimizer.zero_grad()
                reconstructed = self.model(batch_x)
                loss = self.loss_fn(reconstructed, batch_x)

                if torch.isnan(loss) or torch.isinf(loss):
                    raise RuntimeError(f"Gradient explosion or NaN loss detected at epoch {epoch}!")

                loss.backward()

                # Gradient clipping to ensure numerical stability
                if self.config.gradient_clip_val > 0.0:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(), max_norm=self.config.gradient_clip_val
                    )

                self.optimizer.step()

                total_train_loss += loss.item()
                total_train_batches += 1

            epoch_train_loss = total_train_loss / max(total_train_batches, 1)

            # --- Validation Loop (Pure Benign) ---
            self.model.eval()
            total_val_loss = 0.0
            total_val_batches = 0

            with torch.no_grad():
                for (val_batch_x,) in val_loader:
                    val_batch_x = val_batch_x.to(self.device)
                    val_recon = self.model(val_batch_x)
                    val_loss_batch = self.loss_fn(val_recon, val_batch_x)
                    total_val_loss += val_loss_batch.item()
                    total_val_batches += 1

            epoch_val_loss = total_val_loss / max(total_val_batches, 1)
            epoch_duration = time.perf_counter() - epoch_start

            train_losses.append(epoch_train_loss)
            val_losses.append(epoch_val_loss)
            epoch_durations.append(epoch_duration)

            # Check improvement
            if epoch_val_loss < (best_val_loss - self.config.min_delta):
                best_val_loss = epoch_val_loss
                best_epoch = epoch
                best_state_dict = copy.deepcopy(self.model.state_dict())
                epochs_without_improvement = 0
                improvement_flag = "(*)"
            else:
                epochs_without_improvement += 1
                improvement_flag = "   "

            if epoch % 5 == 0 or epoch == 1 or improvement_flag == "(*)":
                logger.info(
                    "Epoch %3d/%3d %s | Train Loss: %.6f | Benign Val Loss: %.6f | Time: %.3fs",
                    epoch,
                    self.config.epochs,
                    improvement_flag,
                    epoch_train_loss,
                    epoch_val_loss,
                    epoch_duration,
                )

            # Early stopping check
            if epochs_without_improvement >= self.config.early_stopping_patience:
                logger.info(
                    "Early stopping triggered at epoch %d (best epoch: %d, best val loss: %.6f)",
                    epoch,
                    best_epoch,
                    best_val_loss,
                )
                stopped_early = True
                break

        # Restore best model weights
        self.model.load_state_dict(best_state_dict)
        total_duration = time.perf_counter() - start_time

        history = TrainingHistory(
            train_losses=train_losses,
            val_losses=val_losses,
            epoch_durations=epoch_durations,
            best_epoch=best_epoch,
            best_val_loss=best_val_loss,
            early_stopping_triggered=stopped_early,
            total_duration_seconds=total_duration,
            total_epochs_trained=len(train_losses),
        )

        logger.info(
            "Training complete in %.2f s | Best Epoch: %d | Best Val Loss: %.6f",
            total_duration,
            best_epoch,
            best_val_loss,
        )
        return self.model, history
