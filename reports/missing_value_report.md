# NETDEFY Missing & Infinite Value Imputation Report

## 1. Methodology & Leakage Prevention

- **Infinities Conversion:** Positive and negative infinities (arising from zero duration division in
  `Flow Bytes/s` and `Flow Packets/s`) are converted to `NaN` prior to imputation.
- **Imputation Strategy:** `Median` imputation.
- **Training-Only Fit Provenance:** Imputation parameters were fitted exclusively on the Monday training
  partition. Validation and test sets are imputed using these stored parameters with zero leakage.

## 2. Partition Cleaning Summary

| Partition | Infinities Converted to NaN | Missing Values Imputed |
| :--- | :--- | :--- |
| `train` | 810 | 874 |
| `validation` | 1,913 | 3,122 |
| `test` | 1,653 | 1,738 |

## 3. Fitted Training Imputation Parameters (Sample Features)

| Feature | Training Median Value | Constant in Training? |
| :--- | :--- | :--- |
| `Flow Duration` | `50913.000000` | No |
| `Total Fwd Packets` | `2.000000` | No |
| `Total Backward Packets` | `2.000000` | No |
| `Total Length of Fwd Packets` | `74.000000` | No |
| `Total Length of Bwd Packets` | `176.000000` | No |
| `Fwd Packet Length Max` | `44.000000` | No |
| `Fwd Packet Length Min` | `6.000000` | No |
| `Fwd Packet Length Mean` | `41.000000` | No |
| `Fwd Packet Length Std` | `0.000000` | No |
| `Bwd Packet Length Max` | `107.000000` | No |
| `Bwd Packet Length Min` | `6.000000` | No |
| `Bwd Packet Length Mean` | `96.000000` | No |
| `Bwd Packet Length Std` | `0.000000` | No |
| `Flow Bytes/s` | `4514.529154` | No |
| `Flow Packets/s` | `73.938520` | No |
| `Flow IAT Mean` | `19825.409341` | No |
| `Flow IAT Std` | `12390.362630` | No |
| `Flow IAT Max` | `39173.000000` | No |
| `Flow IAT Min` | `4.000000` | No |
| `Fwd IAT Total` | `48.000000` | No |
| `Fwd IAT Mean` | `48.000000` | No |
| `Fwd IAT Std` | `0.000000` | No |
| `Fwd IAT Max` | `48.000000` | No |
| `Fwd IAT Min` | `3.000000` | No |
| `Bwd IAT Total` | `3.000000` | No |

### Constant Features in Monday Training (10 Features)
These features have zero variance in Monday benign traffic:
- `Bwd PSH Flags`
- `Fwd URG Flags`
- `Bwd URG Flags`
- `CWE Flag Count`
- `Fwd Avg Bytes/Bulk`
- `Fwd Avg Packets/Bulk`
- `Fwd Avg Bulk Rate`
- `Bwd Avg Bytes/Bulk`
- `Bwd Avg Packets/Bulk`
- `Bwd Avg Bulk Rate`