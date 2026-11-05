# NETDEFY — PHASE 5.1: SPLIT METHODOLOGY & LEAKAGE PREVENTION
**Chronological Partitioning, Causal Boundaries, and Zero-Leakage Guarantees**

---

## 1. Rationale: Why Random Splitting is Invalid for Sequential Intelligence

In traditional tabular machine learning benchmarks, stratified random splitting ($k$-fold cross-validation or random $80/20$ splits) is commonly employed. However, in temporal and behavioural intrusion detection:
1. **Temporal Information Leakage:** Randomly assigning individual flows to train and test mixes future observations into the historical training context, artificially inflating model accuracy through time-travel leakage.
2. **Sequential Dependency Violation:** Network scans, brute-force campaigns, and Infiltration attacks unfold across minutes or hours. Randomly splitting interleaved flows causes the model to evaluate flows whose preceding probes were already seen during training, invalidating real-world sequential evaluation.
3. **Session Contamination:** Background benign traffic exhibits diurnal pacing and operational bursts. Random splitting destroys the burstiness and inter-arrival distributions required for streaming window analysis.

To uphold the highest standard of scientific integrity, Phase 5.1 mandates **Strict Chronological Generalization Splitting**.

---

## 2. Chronological Splitting Architecture

The continuous 12-hour traffic capture from CSE-CIC-IDS2018 (`Thursday-01-03-2018`, spanning 01:00:00 to 12:59:59) was partitioned along strict wall-clock time boundaries:

```
01:00:00               03:00:00                           07:00:00                    12:59:59
   +-----------------------+----------------------------------+---------------------------+
   |   CALIBRATION SPLIT   |         VALIDATION SPLIT         |    FINAL HOLDOUT TEST     |
   |     (Initial 2h)      |           (Next 4h)              |        (Final 6h)         |
   |      80,423 flows     |          84,935 flows            |       165,742 flows       |
   +-----------------------+----------------------------------+---------------------------+
               ^                                  ^
               |                                  |
        Boundary T_split1                  Boundary T_split2
       (2018-03-01 03:00)                 (2018-03-01 07:00)
```

### 2.1 Partition Definitions & Functional Roles

1. **Calibration Partition (`calibration.parquet`, $N = 80,423$):**
   - **Time Interval:** `2018-03-01 01:00:00` to `2018-03-01 02:59:59` ($2.0$ hours).
   - **Composition:** $46,549$ Benign flows ($57.9\%$), $33,874$ Infiltration flows ($42.1\%$).
   - **Role:** Used exclusively for warm-up state initialization, EWMA connection rate baseline estimation, and historical background profiling.
2. **Validation Partition (`validation.parquet`, $N = 84,935$):**
   - **Time Interval:** `2018-03-01 03:00:00` to `2018-03-01 05:45:28` ($2.75$ hours active traffic).
   - **Composition:** $64,498$ Benign flows ($75.9\%$), $20,437$ Infiltration flows ($24.1\%$).
   - **Role:** Reserved for threshold tuning, sliding window parameter sweeps ($\Delta t \in \{1\text{s}, 5\text{s}, 30\text{s}, 60\text{s}\}$), and minimum connection count calibration.
3. **Final Holdout Test Partition (`test.parquet`, $N = 165,742$):**
   - **Time Interval:** `2018-03-01 08:16:28` to `2018-03-01 12:59:59` ($4.75$ hours active traffic).
   - **Composition:** $126,990$ Benign flows ($76.6\%$), $38,752$ Infiltration flows ($23.4\%$).
   - **Role:** **Strictly frozen holdout**. Evaluated only after all thresholds and pipeline logic are locked.

---

## 3. Mathematical Proof of Zero Temporal Leakage

Let $\mathcal{T}(P) = \{\tau(e) \mid e \in P\}$ denote the set of epoch timestamps in partition $P$:

$$\max(\mathcal{T}(\text{Calibration})) = 1519873199 \le \min(\mathcal{T}(\text{Validation})) = 1519873200$$
$$\max(\mathcal{T}(\text{Validation})) = 1519883128 \le \min(\mathcal{T}(\text{Test})) = 1519892188$$

- **Calibration $\to$ Validation Separation:** Exactly $1$ second boundary gap ($02:59:59 \to 03:00:00$).
- **Validation $\to$ Test Separation:** Exactly $9,060$ seconds ($2.52$ hours) natural silence gap between early morning and late morning active testing sessions ($05:45:28 \to 08:16:28$).
- **Overlapping Timestamps:** **$0$ flows ($0.00\%$)**.

---

## 4. Leakage Safeguards in Feature Generation

1. **State Isolation:** The sliding window `WindowAggregator` is strictly cleared at the start of each partition evaluation. Historical states from validation do not bleed into the test holdout.
2. **Causal Time Enforcement:** For any event $e_t$ arriving at time $t$, only events where $\tau \le t$ can influence the active sliding window $\mathcal{W}(t, \Delta t)$.
3. **No Target Leakage:** Neither ground-truth `Label` nor downstream supervised predictions are accessible during feature computation.
