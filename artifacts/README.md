# NETDEFY Model & Preprocessing Artifacts

This directory stores serialized models, preprocessing pipelines, threshold calibration metadata, and inference schemas:

- `scalers/`: Fitted feature transformers (e.g., `StandardScaler`, `RobustScaler`) fitted strictly on training data splits.
- `models/`: Trained model weights and configurations (PyTorch `.pt` checkpoints, Scikit-learn `.joblib` estimators).
- `thresholds/`: Calibrated anomaly score thresholds and validation metrics.
- `schemas/`: Exported JSON feature schemas for runtime inference validation.

All binary artifacts are excluded from Git version control via `.gitignore`.

