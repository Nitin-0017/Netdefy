"""NETDEFY — Deep Autoencoder Anomaly Detection Engine.

Implements a configurable, leakage-safe Deep Autoencoder in PyTorch
for one-class network traffic flow anomaly detection.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoencoderArchitectureConfig:
    """Hyperparameter and architectural configuration for DeepAutoencoder."""

    input_dim: int = 76
    encoder_dims: tuple[int, ...] = (64, 32, 16)
    latent_dim: int = 8
    decoder_dims: tuple[int, ...] = (16, 32, 64)
    activation: Literal["relu", "leaky_relu", "gelu", "elu"] = "relu"
    dropout_rate: float = 0.0
    use_batch_norm: bool = False
    random_seed: int = 42

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_dim": self.input_dim,
            "encoder_dims": list(self.encoder_dims),
            "latent_dim": self.latent_dim,
            "decoder_dims": list(self.decoder_dims),
            "activation": self.activation,
            "dropout_rate": self.dropout_rate,
            "use_batch_norm": self.use_batch_norm,
            "random_seed": self.random_seed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutoencoderArchitectureConfig:
        return cls(
            input_dim=int(data.get("input_dim", 76)),
            encoder_dims=tuple(data.get("encoder_dims", [64, 32, 16])),
            latent_dim=int(data.get("latent_dim", 8)),
            decoder_dims=tuple(data.get("decoder_dims", [16, 32, 64])),
            activation=data.get("activation", "relu"),
            dropout_rate=float(data.get("dropout_rate", 0.0)),
            use_batch_norm=bool(data.get("use_batch_norm", False)),
            random_seed=int(data.get("random_seed", 42)),
        )


def _get_activation_module(activation_name: str) -> nn.Module:
    name = activation_name.lower().strip()
    if name == "relu":
        return nn.ReLU()
    if name == "leaky_relu":
        return nn.LeakyReLU(negative_slope=0.01)
    if name == "gelu":
        return nn.GELU()
    if name == "elu":
        return nn.ELU()
    raise ValueError(f"Unsupported activation function: {activation_name}")


class DeepAutoencoder(nn.Module):
    """Deep Autoencoder neural network with a bottleneck latent representation.

    Architecture (Default):
        Input (76) -> 64 -> 32 -> 16 -> Latent (8) -> 16 -> 32 -> 64 -> Reconstructed (76)
    """

    def __init__(self, config: AutoencoderArchitectureConfig | None = None) -> None:
        super().__init__()
        self.config = config or AutoencoderArchitectureConfig()

        # Deterministic weight initialization
        torch.manual_seed(self.config.random_seed)

        # Build Encoder
        encoder_layers: list[nn.Module] = []
        prev_dim = self.config.input_dim
        for dim in self.config.encoder_dims:
            encoder_layers.append(nn.Linear(prev_dim, dim))
            if self.config.use_batch_norm:
                encoder_layers.append(nn.BatchNorm1d(dim))
            encoder_layers.append(_get_activation_module(self.config.activation))
            if self.config.dropout_rate > 0.0:
                encoder_layers.append(nn.Dropout(p=self.config.dropout_rate))
            prev_dim = dim
        # Latent bottleneck projection
        encoder_layers.append(nn.Linear(prev_dim, self.config.latent_dim))
        self.encoder = nn.Sequential(*encoder_layers)

        # Build Decoder
        decoder_layers: list[nn.Module] = []
        prev_dim = self.config.latent_dim
        for dim in self.config.decoder_dims:
            decoder_layers.append(nn.Linear(prev_dim, dim))
            if self.config.use_batch_norm:
                decoder_layers.append(nn.BatchNorm1d(dim))
            decoder_layers.append(_get_activation_module(self.config.activation))
            if self.config.dropout_rate > 0.0:
                decoder_layers.append(nn.Dropout(p=self.config.dropout_rate))
            prev_dim = dim
        # Output reconstruction layer (linear for continuous normalized features)
        decoder_layers.append(nn.Linear(prev_dim, self.config.input_dim))
        self.decoder = nn.Sequential(*decoder_layers)

        # Initialize linear layers
        self._initialize_weights()

    def _initialize_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Project input features into the low-dimensional latent space."""
        return cast(torch.Tensor, self.encoder(x))

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Reconstruct continuous feature vector from latent code."""
        return cast(torch.Tensor, self.decoder(z))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Full forward reconstruction pass."""
        z = self.encode(x)
        return self.decode(z)

    def reconstruct(self, x: torch.Tensor) -> torch.Tensor:
        """Alias for forward reconstruction."""
        return self.forward(x)

    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        """Compute per-sample Mean Squared Error (MSE) reconstruction error.

        Score Orientation:
            MSE(x, x_hat) = mean((x - x_hat)^2, dim=-1)
            Higher reconstruction error = greater anomaly.

        Returns:
            1D float32 Tensor of shape [batch_size].
        """
        x_hat = self.forward(x)
        return torch.mean((x - x_hat) ** 2, dim=-1)

    @property
    def parameter_count(self) -> int:
        """Total trainable parameters in the model."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class AutoencoderDetector:
    """Production and evaluation wrapper for DeepAutoencoder.

    Adheres strictly to the NETDEFY anomaly score orientation:
        **HIGHER ANOMALY SCORE = MORE SUSPICIOUS / ANOMALOUS**
    """

    def __init__(
        self,
        model: DeepAutoencoder | None = None,
        config: AutoencoderArchitectureConfig | None = None,
        device: torch.device | str = "cpu",
    ) -> None:
        self.config = config or AutoencoderArchitectureConfig()
        self.device = torch.device(device) if isinstance(device, str) else device
        self.model = model or DeepAutoencoder(self.config)
        self.model.to(self.device)
        self.feature_names: list[str] = []
        self.is_fitted: bool = False
        self.train_duration_seconds: float = 0.0
        self.train_sample_count: int = 0

    def score_samples(
        self,
        X: pd.DataFrame | np.ndarray,
        batch_size: int = 1024,
    ) -> np.ndarray:
        """Compute reconstruction error anomaly scores for input samples.

        Returns:
            1D numpy array of float32 anomaly scores where HIGHER values
            indicate greater deviation from normal training behaviour.
        """
        if not self.is_fitted:
            raise RuntimeError("Cannot score samples: AutoencoderDetector is not fitted!")

        if isinstance(X, pd.DataFrame):
            if self.feature_names:
                X_arr = X[self.feature_names].to_numpy(dtype=np.float32)
            else:
                X_arr = X.to_numpy(dtype=np.float32)
        else:
            X_arr = np.asarray(X, dtype=np.float32)

        if np.isnan(X_arr).any() or np.isinf(X_arr).any():
            raise ValueError("Input feature matrix contains NaN or Inf values!")

        self.model.eval()
        scores_list: list[np.ndarray] = []
        n_samples = len(X_arr)

        with torch.no_grad():
            for i in range(0, n_samples, batch_size):
                batch_arr = X_arr[i : i + batch_size]
                batch_tensor = torch.tensor(batch_arr, dtype=torch.float32, device=self.device)
                batch_errors = self.model.reconstruction_error(batch_tensor)
                scores_list.append(batch_errors.cpu().numpy().astype(np.float32))

        return np.concatenate(scores_list, axis=0) if scores_list else np.empty(0, dtype=np.float32)

    def predict(
        self,
        X: pd.DataFrame | np.ndarray,
        threshold: float,
        batch_size: int = 1024,
    ) -> np.ndarray:
        """Predict binary anomaly labels given a calibrated decision threshold.

        Scores >= threshold are flagged as anomalous (1).

        Returns:
            Binary numpy array of int32 (1 = Anomaly, 0 = Normal).
        """
        scores = self.score_samples(X, batch_size=batch_size)
        return (scores >= threshold).astype(np.int32)

    def save(self, filepath: Path | str) -> str:
        """Serialize trained model weights and metadata, returning SHA-256."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted model!")

        save_path = Path(filepath).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)

        bundle: dict[str, Any] = {
            "state_dict": self.model.state_dict(),
            "config": self.config.to_dict(),
            "feature_names": self.feature_names,
            "train_duration_seconds": self.train_duration_seconds,
            "train_sample_count": self.train_sample_count,
            "parameter_count": self.model.parameter_count,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        torch.save(bundle, save_path)

        # Compute file checksum
        hasher = hashlib.sha256()
        with open(save_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(
        cls,
        filepath: Path | str,
        device: torch.device | str = "cpu",
    ) -> AutoencoderDetector:
        """Load serialized model bundle."""
        load_path = Path(filepath).resolve()
        if not load_path.exists():
            raise FileNotFoundError(f"Model file not found: {load_path}")

        target_device = torch.device(device) if isinstance(device, str) else device
        bundle = torch.load(load_path, map_location=target_device, weights_only=False)

        config = AutoencoderArchitectureConfig.from_dict(bundle["config"])
        model = DeepAutoencoder(config=config)
        model.load_state_dict(bundle["state_dict"])

        detector = cls(model=model, config=config, device=target_device)
        detector.feature_names = bundle["feature_names"]
        detector.train_duration_seconds = bundle.get("train_duration_seconds", 0.0)
        detector.train_sample_count = bundle.get("train_sample_count", 0)
        detector.is_fitted = True
        return detector
