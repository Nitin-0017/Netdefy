"""NETDEFY — Network Defense Intelligence.

AI-Powered Network Anomaly Detection Platform.
"""

import contextlib
from typing import Final

# Preload xgboost before torch to prevent OpenMP runtime collision on macOS ARM
with contextlib.suppress(ImportError):
    import xgboost  # noqa: F401

__version__: Final[str] = "0.1.0"
__app_name__: Final[str] = "NETDEFY"
__all__ = ["__version__", "__app_name__"]
