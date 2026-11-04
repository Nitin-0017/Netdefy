# NETDEFY Temporal Partitioning Report

## 1. Partition Breakdown

| Partition | Calendar Day(s) | Files Included | Raw Rows (View A) | Dedup Rows (View B) | Benign (View B) | Attacks (View B) | Attack % (View B) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TRAIN** | Mon, July 3 | 1 file (Monday) | 529,918 | 459,112 | 459,112 | 0 | 0.00% |
| **VALIDATION** | Tue & Wed (July 4–5) | 2 files (Tue, Wed) | 1,138,612 | 963,879 | 760,061 | 203,818 | 21.15% |
| **TEST** | Thu & Fri (July 6–7) | 5 files (Thu/Fri) | 1,162,213 | 845,403 | 711,935 | 133,468 | 15.79% |
| **TOTAL** | All 5 Days | 8 files | 2,830,743 | 2,268,394 | — | — | — |

## 2. Attack Breakdown in Final Test Period (Untouched Benchmark)

- `DDoS`: 128,013 flows
- `PortScan`: 1,852 flows
- `Web Attack � Brute Force`: 1,470 flows
- `Bot`: 1,424 flows
- `Web Attack � XSS`: 652 flows
- `Infiltration`: 36 flows
- `Web Attack � Sql Injection`: 21 flows