# NETDEFY Feature Selection & Schema Reconciliation Report

## 1. Feature Count Reconciliation

- **Total Raw Columns in CSV:** 79 columns.
- **Ground-Truth Label:** 1 column (`Label`) isolated as evaluation target (never an input feature).
- **Candidate Input Columns:** 78 columns.
- **Duplicate Column Removed:** 1 column (`Fwd Header Length.1` at column index 55 is an exact
  duplicate of `Fwd Header Length` at column index 34 produced by CICFlowMeter).
- **Candidate Unique Features:** 77 unique features.
- **Service Discretization:** `Destination Port` preserved in audit data and mapped to `Service_Category`.
- **Final Service-Independent Continuous Feature Set:** **76 features**.

## 2. Excluded Features & Technical Justifications

| Column Name | Action | Engineering & Scientific Rationale |
| :--- | :--- | :--- |
| `Label` | **Excluded** | Ground truth target; isolated for evaluation to prevent fatal data leakage. |
| `Fwd Header Length (duplicate instance)` | **Excluded** | Exact redundant column produced by CICFlowMeter tapping bugs; causes multicollinearity. |

## 3. Retained Features List (76 Features)

| Feature Index | Feature Name | Preprocessed Dtype | Scaler Treatment |
| :--- | :--- | :--- | :--- |
| 1 | `Flow Duration` | `float32` | Standardized (mean=0, std=1) |
| 2 | `Total Fwd Packets` | `float32` | Standardized (mean=0, std=1) |
| 3 | `Total Backward Packets` | `float32` | Standardized (mean=0, std=1) |
| 4 | `Total Length of Fwd Packets` | `float32` | Standardized (mean=0, std=1) |
| 5 | `Total Length of Bwd Packets` | `float32` | Standardized (mean=0, std=1) |
| 6 | `Fwd Packet Length Max` | `float32` | Standardized (mean=0, std=1) |
| 7 | `Fwd Packet Length Min` | `float32` | Standardized (mean=0, std=1) |
| 8 | `Fwd Packet Length Mean` | `float32` | Standardized (mean=0, std=1) |
| 9 | `Fwd Packet Length Std` | `float32` | Standardized (mean=0, std=1) |
| 10 | `Bwd Packet Length Max` | `float32` | Standardized (mean=0, std=1) |
| 11 | `Bwd Packet Length Min` | `float32` | Standardized (mean=0, std=1) |
| 12 | `Bwd Packet Length Mean` | `float32` | Standardized (mean=0, std=1) |
| 13 | `Bwd Packet Length Std` | `float32` | Standardized (mean=0, std=1) |
| 14 | `Flow Bytes/s` | `float32` | Standardized (mean=0, std=1) |
| 15 | `Flow Packets/s` | `float32` | Standardized (mean=0, std=1) |
| 16 | `Flow IAT Mean` | `float32` | Standardized (mean=0, std=1) |
| 17 | `Flow IAT Std` | `float32` | Standardized (mean=0, std=1) |
| 18 | `Flow IAT Max` | `float32` | Standardized (mean=0, std=1) |
| 19 | `Flow IAT Min` | `float32` | Standardized (mean=0, std=1) |
| 20 | `Fwd IAT Total` | `float32` | Standardized (mean=0, std=1) |
| 21 | `Fwd IAT Mean` | `float32` | Standardized (mean=0, std=1) |
| 22 | `Fwd IAT Std` | `float32` | Standardized (mean=0, std=1) |
| 23 | `Fwd IAT Max` | `float32` | Standardized (mean=0, std=1) |
| 24 | `Fwd IAT Min` | `float32` | Standardized (mean=0, std=1) |
| 25 | `Bwd IAT Total` | `float32` | Standardized (mean=0, std=1) |
| 26 | `Bwd IAT Mean` | `float32` | Standardized (mean=0, std=1) |
| 27 | `Bwd IAT Std` | `float32` | Standardized (mean=0, std=1) |
| 28 | `Bwd IAT Max` | `float32` | Standardized (mean=0, std=1) |
| 29 | `Bwd IAT Min` | `float32` | Standardized (mean=0, std=1) |
| 30 | `Fwd PSH Flags` | `float32` | Standardized (mean=0, std=1) |
| 31 | `Bwd PSH Flags` | `float32` | Standardized (mean=0, std=1) |
| 32 | `Fwd URG Flags` | `float32` | Standardized (mean=0, std=1) |
| 33 | `Bwd URG Flags` | `float32` | Standardized (mean=0, std=1) |
| 34 | `Fwd Header Length` | `float32` | Standardized (mean=0, std=1) |
| 35 | `Bwd Header Length` | `float32` | Standardized (mean=0, std=1) |
| 36 | `Fwd Packets/s` | `float32` | Standardized (mean=0, std=1) |
| 37 | `Bwd Packets/s` | `float32` | Standardized (mean=0, std=1) |
| 38 | `Min Packet Length` | `float32` | Standardized (mean=0, std=1) |
| 39 | `Max Packet Length` | `float32` | Standardized (mean=0, std=1) |
| 40 | `Packet Length Mean` | `float32` | Standardized (mean=0, std=1) |
| 41 | `Packet Length Std` | `float32` | Standardized (mean=0, std=1) |
| 42 | `Packet Length Variance` | `float32` | Standardized (mean=0, std=1) |
| 43 | `FIN Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 44 | `SYN Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 45 | `RST Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 46 | `PSH Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 47 | `ACK Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 48 | `URG Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 49 | `CWE Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 50 | `ECE Flag Count` | `float32` | Standardized (mean=0, std=1) |
| 51 | `Down/Up Ratio` | `float32` | Standardized (mean=0, std=1) |
| 52 | `Average Packet Size` | `float32` | Standardized (mean=0, std=1) |
| 53 | `Avg Fwd Segment Size` | `float32` | Standardized (mean=0, std=1) |
| 54 | `Avg Bwd Segment Size` | `float32` | Standardized (mean=0, std=1) |
| 55 | `Fwd Avg Bytes/Bulk` | `float32` | Standardized (mean=0, std=1) |
| 56 | `Fwd Avg Packets/Bulk` | `float32` | Standardized (mean=0, std=1) |
| 57 | `Fwd Avg Bulk Rate` | `float32` | Standardized (mean=0, std=1) |
| 58 | `Bwd Avg Bytes/Bulk` | `float32` | Standardized (mean=0, std=1) |
| 59 | `Bwd Avg Packets/Bulk` | `float32` | Standardized (mean=0, std=1) |
| 60 | `Bwd Avg Bulk Rate` | `float32` | Standardized (mean=0, std=1) |
| 61 | `Subflow Fwd Packets` | `float32` | Standardized (mean=0, std=1) |
| 62 | `Subflow Fwd Bytes` | `float32` | Standardized (mean=0, std=1) |
| 63 | `Subflow Bwd Packets` | `float32` | Standardized (mean=0, std=1) |
| 64 | `Subflow Bwd Bytes` | `float32` | Standardized (mean=0, std=1) |
| 65 | `Init_Win_bytes_forward` | `float32` | Standardized (mean=0, std=1) |
| 66 | `Init_Win_bytes_backward` | `float32` | Standardized (mean=0, std=1) |
| 67 | `act_data_pkt_fwd` | `float32` | Standardized (mean=0, std=1) |
| 68 | `min_seg_size_forward` | `float32` | Standardized (mean=0, std=1) |
| 69 | `Active Mean` | `float32` | Standardized (mean=0, std=1) |
| 70 | `Active Std` | `float32` | Standardized (mean=0, std=1) |
| 71 | `Active Max` | `float32` | Standardized (mean=0, std=1) |
| 72 | `Active Min` | `float32` | Standardized (mean=0, std=1) |
| 73 | `Idle Mean` | `float32` | Standardized (mean=0, std=1) |
| 74 | `Idle Std` | `float32` | Standardized (mean=0, std=1) |
| 75 | `Idle Max` | `float32` | Standardized (mean=0, std=1) |
| 76 | `Idle Min` | `float32` | Standardized (mean=0, std=1) |