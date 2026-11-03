# NETDEFY Temporal Distribution & Chronological Sequencing

## 1. Verified Forensic Findings on Dataset Telemetry

Forensic inspection of all eight CSV files from the official UNB `MachineLearningCSV.zip` revealed a critical empirical fact:
- **No Per-Flow Timestamp Column:** In this official Machine Learning CSV release (`MachineLearningCVE`), individual rows do not contain a `Timestamp`, `Source IP`, or `Destination IP` column. These columns were deliberately omitted by the UNB dataset creators to prevent algorithms from memorizing specific host IP addresses and scheduled attack times.
- **File-Level Temporal Ground Truth:** The chronological progression of the dataset is preserved directly in the file partition boundaries, which map to specific days and operational hours:

| Partition File | Calendar Date | Operational Window | Recorded Traffic Profile | Row Count |
| :--- | :--- | :--- | :--- | :--- |
| `Monday-WorkingHours.pcap_ISCX.csv` | Mon, July 3, 2017 | 08:55 – 17:00 | **100% Benign Baseline Traffic** | 529,918 |
| `Tuesday-WorkingHours.pcap_ISCX.csv` | Tue, July 4, 2017 | 08:55 – 17:00 | Benign (432,074) + FTP-Patator (7,938) + SSH-Patator (5,897) | 445,909 |
| `Wednesday-workingHours.pcap_ISCX.csv` | Wed, July 5, 2017 | 08:55 – 17:00 | Benign (440,031) + DoS Hulk, GoldenEye, Slowloris, Slowhttptest, Heartbleed | 692,703 |
| `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` | Thu, July 6, 2017 | 08:55 – 12:00 | Benign (168,186) + Web Attacks (Brute Force, XSS, Sql Injection) | 170,366 |
| `Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv` | Thu, July 6, 2017 | 12:00 – 17:00 | Benign (288,566) + Infiltration (36) | 288,602 |
| `Friday-WorkingHours-Morning.pcap_ISCX.csv` | Fri, July 7, 2017 | 08:55 – 12:00 | Benign (189,067) + Botnet ARES (1,966) | 191,033 |
| `Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv` | Fri, July 7, 2017 | 12:00 – 15:30 | Benign (127,537) + PortScan (158,930) | 286,467 |
| `Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv` | Fri, July 7, 2017 | 15:30 – 17:00 | Benign (97,718) + DDoS (128,027) | 225,745 |

---

## 2. Assessment of Proposed Tuesday Split

> [!WARNING]
> **Conclusion:** **Tuesday cannot and should not be divided into training and validation windows.**

1. **Absence of Row-Level Timestamps:** Because `Tuesday-WorkingHours.pcap_ISCX.csv` contains no timestamp column, splitting halfway through the file cannot guarantee a chronological boundary.
2. **Early Attack Contamination:** In the UNB testbed schedule, FTP-Patator was launched at 09:20 AM (within 20 minutes of startup). Any arbitrary slice risks contaminating the training partition with brute-force flows.
3. **Pristine Monday Alternative:** Monday provides 529,918 completely uncontaminated benign flows. Using Monday exclusively as the training partition guarantees a 100% clean baseline without heuristic slicing.

---

## 3. Evidence-Based Chronological Partition Protocol

```
+-----------------------------------------------------------------------------------------+
|                                    CICIDS2017 TIMELINE                                  |
+-----------------------------------------------------------------------------------------+
| Monday (Jul 3)   | Tuesday (Jul 4)  | Wednesday (Jul 5) | Thursday (Jul 6) | Friday (Jul 7) |
| Benign Baseline  | Brute Force      | DoS / DDoS        | Web Attacks      | Botnet, Port   |
+------------------+------------------+-------------------+------------------+----------------+
        \                 /                    |                    \                /
         \               /                     |                     \              /
   [ Phase 3 Training Partition ]     [ Validation Partition ]      [ Final Test Partition ]
   - 100% Benign (529,918 flows)      - Tuesday & Wednesday         - Thursday & Friday
   - Train Autoencoder baseline       - Calibrate threshold (tau)   - Untouched until final eval
   - Scalers fit strictly on Monday   - Freeze threshold (tau)      - Evaluates temporal decay
```

- **Training Partition (Day 1 - Monday):** 529,918 benign flows.
- **Validation / Calibration Partition (Days 2 & 3 - Tuesday & Wednesday):** 1,138,612 flows (872,105 Benign, 266,507 Attacks).
- **Final Test Partition (Days 4 & 5 - Thursday & Friday):** 1,162,213 flows (871,074 Benign, 291,139 Attacks).
