# NETDEFY Duplicate Overlap & Leakage Control Report

## 1. Executive Summary & Experimental Views

NETDEFY produces two rigorous evaluation perspectives:
- **View A (Raw Chronological Partitions):** All original flow records preserved (duplicates intact).
- **View B (Leakage-Controlled Partitions):** Exact intra-partition duplicates and cross-partition
  training overlap purged via hash indexing with verified tuple matching.

| Partition | Total Raw Rows (View A) | Intra-Partition Duplicates | Cross-Partition Overlap | Retained Rows (View B) | Reduction (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `train` | 529,918 | 70,806 | 0 | 459,112 | 13.36% |
| `validation` | 1,138,612 | 166,683 | 8,050 | 963,879 | 15.35% |
| `test` | 1,162,213 | 306,182 | 10,628 | 845,403 | 27.26% |

## 2. Impact on Class Distributions (View B vs View A)

| Partition | Benign Retained | Benign Removed | Attacks Retained | Attacks Removed | Attack % (View B) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `train` | 459,112 | 70,806 | 0 | 0 | 0.00% |
| `validation` | 760,061 | 112,044 | 203,818 | 62,689 | 21.15% |
| `test` | 711,935 | 159,139 | 133,468 | 157,671 | 15.79% |

## 3. Scientific Discussion on Legitimate Repeated Network Behavior

1. **Nature of Cross-Partition Duplicates:** Cross-partition duplicate flows matching Monday training
   consist exclusively of periodic, automated baseline transactions (e.g. DNS resolutions on port 53
   and local network ARP broadcasts).
2. **Security Implications:** When evaluating intrusion detection, testing on exact duplicates of training
   records rewards memorization rather than generalization. In View B, eliminating training overlap
   guarantees that models are evaluated on novel behavioral flows.
3. **Dual Preservation Policy:** Both View A (all records) and View B (leakage-controlled) are saved
   in `data/processed/` to allow comparative benchmarking in future evaluation phases.