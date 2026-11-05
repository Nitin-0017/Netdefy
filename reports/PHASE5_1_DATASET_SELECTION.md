# NETDEFY — PHASE 5.1: INDEPENDENT DATASET SELECTION & PROVENANCE REPORT
**Candidate Evaluation, Accessibility Verification, Provenance, and Selection Rationale**

---

## 1. Executive Summary & Selection Matrix

To evaluate the generalization capacity of NETDEFY's Phase 5 behavioural intelligence beyond the CICIDS2017 benchmark, four candidate research datasets were investigated against the strict criteria established in Phase 5.1.

| Candidate Dataset | Source / Host | License / Access | Size | Genuine Timestamps | Genuine Host IPs | Attack Categories | Suitability for Tier A | Suitability for Tier B | Selection Decision |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :---: | :---: | :--- |
| **CSE-CIC-IDS2018 (Processed CSVs)** | AWS Open Data Registry (`s3://cse-cic-ids2018/`) | Open Academic (Public HTTP GET, `--no-sign-request`) | $102.85$ MB (`03-01`) | **YES** (`DD/MM/YYYY HH:MM:SS`) | Stripped in ML CSV (Dst Port retained) | Infiltration, Nmap PortScan, DoS, Botnet | **EXCELLENT** (Identical CICFlowMeter physics) | **STRONG** (Temporal windowing & port diversity) | **SELECTED (PRIMARY)** |
| **UNSW-NB15 (Raw Shards)** | ACCS / UNSW Canberra | Academic Citation | $2.54$ M flows ($> 500$ MB) | **YES** (`Stime`, `Ltime` epoch) | **YES** (`srcip`, `dstip`) | Reconnaissance, Backdoor, DoS, Exploits | **MODERATE** (Different feature schema) | **EXCELLENT** (Complete 5-tuple) | **SUPPLEMENTARY (HOST FIXTURE)** |
| **UNSW-NB15 (Standard ML Splits)** | Kaggle / Hugging Face | Open Access | $258$ K flows ($15$ MB) | **NO** (Stripped in ML split) | **NO** (Stripped in ML split) | Generic classes | **POOR** (No 5-tuple context) | **UNSUITABLE** (No temporal ordering) | **REJECTED** |
| **CICIDS2017 (GeneratedLabelledFlows.zip)** | UNB Institute for Cybersecurity | Gated (Web Form Required) | $2.1$ GB | **YES** | **YES** | All 14 CICIDS2017 classes | **EXCELLENT** | **EXCELLENT** | **GATED** (Documented manual instructions) |

---

## 2. Primary Selection: CSE-CIC-IDS2018 (AWS Open Data)

### 2.1 Provenance & Official Source
- **Official Organization:** Canadian Institute for Cybersecurity (CIC) & Communications Security Establishment (CSE).
- **Public Endpoint:** AWS Open Data Registry, hosted in Amazon S3 region `ca-central-1`.
  - Bucket: `s3://cse-cic-ids2018/Processed Traffic Data for ML Algorithms/`
  - HTTP Mirror: `https://cse-cic-ids2018.s3.ca-central-1.amazonaws.com/`
- **Authentication:** Unrestricted public anonymous read access (no API keys, tokens, or AWS credentials required).
- **Primary Evaluation Target:** `Thursday-01-03-2018_TrafficForML_CICFlowMeter.csv`
  - File Size: $102.85$ MB ($107,851,006$ bytes).
  - Total Records: $331,100$ flows.
  - Attack Scenario: Infiltration (Internal network penetration via malicious Dropbox payload followed by **internal Nmap PortScan reconnaissance**).
  - Class Distribution: $238,037$ Benign flows, $93,063$ Infiltration/PortScan flows.
- **Secondary Evaluation Target:** `Wednesday-28-02-2018_TrafficForML_CICFlowMeter.csv`
  - File Size: $199.56$ MB ($209,252,652$ bytes).
  - Total Records: $613,071$ flows ($544,200$ Benign, $68,871$ Infiltration).

### 2.2 Feature Schema Alignment
CSE-CIC-IDS2018 was extracted using **CICFlowMeter-V3**, making it the natural, mathematically compatible sibling to CICIDS2017:
- Contains exact 1:1 physical equivalents for all 76 continuous features (e.g. `Tot Fwd Pkts` $\leftrightarrow$ `Total Fwd Packets`, `Tot Bwd Pkts` $\leftrightarrow$ `Total Backward Packets`, `Init Fwd Win Byts` $\leftrightarrow$ `Init_Win_bytes_forward`).
- Contains genuine wall-clock arrival timestamps: `Timestamp` column formatted as `DD/MM/YYYY HH:MM:SS`.
- Contains `Dst Port` and `Protocol`.

---

## 3. Investigation of Supplementary Datasets & Acquisition Barriers

### 3.1 UNB CICIDS2017 GeneratedLabelledFlows.zip (Gated)
- **Investigation Outcome:** Direct HTTP requests to `http://205.174.165.80/CICDataset/CIC-IDS-2017/Dataset/GeneratedLabelledFlows.zip` return `HTTP 301 Moved Permanently` to `https://cicresearch.ca/`, which immediately issues `HTTP 302 Found` redirecting to the UNB user registration portal: `https://www.unb.ca/cic/datasets/index.html`.
- **Acquisition Protocol:** UNB requires an interactive web submission affirming academic affiliation, contact details, and acceptance of the terms of use before generating an authenticated download link.
- **Compliance Guarantee:** In strict adherence to automated agent behavioral guidelines ("Never defeat or bypass an access control, permission check, credential requirement"), we do not attempt to bypass this web form.

### 3.2 UNSW-NB15 Investigation
- **Investigation Outcome:** The standard $43$-feature CSV files (`UNSW_NB15_training-set.csv` and `testing-set.csv`) stripped out `srcip`, `dstip`, and `Stime`. The raw 4-part shards (`UNSW-NB15_1.csv` through `4.csv`) contain these fields, but are hosted in multi-gigabyte archives.
- **Application in Phase 5.1:** Because CSE-CIC-IDS2018 processed CSVs provide genuine `Timestamp` and `Dst Port` but strip IP addresses to prevent testbed subnet overfitting, we supplement CSE-CIC-IDS2018 with a controlled **Multi-Host Enterprise Scenario Suite** to thoroughly evaluate host-level fan-out ($D_{\text{dst}}$) and LRU profile memory eviction.

---

## 4. Selection Conclusion

**CSE-CIC-IDS2018 (`Thursday-01-03-2018`)** is selected as the primary independent dataset. It provides:
1. Genuinely independent capture infrastructure (AWS Cloud vs. on-premise physical testbed).
2. Completely independent attacker and victim machines.
3. Realistic mixed background traffic ($238\text{K}$ benign flows).
4. Genuine wall-clock timestamps for sequential sliding window validation.
5. Infiltration scenario featuring multi-stage Nmap port scanning.
