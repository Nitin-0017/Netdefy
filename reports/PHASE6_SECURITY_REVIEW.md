# NETDEFY — PHASE 6 SECURITY REVIEW & THREAT MODEL
## Defensive Hardening, Attack Surface Analysis & Threat Mitigations

---

### 1. Security Architecture Overview

NETDEFY is strictly a defensive network monitoring and intelligence platform. It does not perform active network penetration, packet crafting, or offensive exploitation. However, because it ingests untrusted network telemetry from distributed sensors, its ingestion, stream processing, and alert storage boundaries must be hardened against adversarial attacks.

---

### 2. Comprehensive Threat Model & Mitigations

| Threat Vector | Attack Scenario | Architectural Countermeasure & Hardening |
|---|---|---|
| **1. Malformed Payloads** | Attacker injects malformed JSON, truncated headers, or nested arrays. | Pydantic V2 schema validation strictly enforces structural types and extra-field boundaries before admission. |
| **2. Non-Finite Flooding ($NaN$ / $\pm\infty$)** | Attacker crafts zero-duration or divide-by-zero flows containing $NaN$ or $\pm\infty$ to crash PyTorch/XGBoost matrix routines. | `event_validator.py` inspects all 76 continuous features; any non-finite value immediately triggers an `INVALID_FEATURE_VALUES` rejection. |
| **3. Event Flooding / DoS** | Attacker transmits high-rate telemetry to overwhelm API gateway memory. | `BackpressureController` monitors queue depth. When depth exceeds `high_watermark` ($20,000$), producer backoff is enforced; at `max_depth` ($50,000$), requests are rejected with HTTP 429. |
| **4. Duplicate Replay Attacks** | Attacker replays historical flow captures to inflate SOC alert counters. | `EventDeduplicator` enforces a bounded LRU cache ($50,000$ entries, $3,600\text{s}$ TTL), rejecting duplicate event IDs with HTTP 409 / error code `DUPLICATE_EVENT`. |
| **5. Timestamp Manipulation** | Attacker sets timestamps years in the past or future to corrupt chronological sliding windows. | `event_validator.py` enforces temporal boundaries: flows $> 10\text{s}$ in the future (NTP skew allowance) or $> 365\text{ days}$ in the past are rejected. |
| **6. Adaptive Baseline Poisoning** | Attacker injects subtle anomalies over time to shift normal distribution boundaries. | `AdaptiveBaselinePolicy` implements a strict 4-condition gate: only verified `NORMAL`, `BENIGN`, non-behavioral flows with anomaly scores $< p95$ can update the baseline. Active baseline is bounded within $\pm 25\%$ of frozen reference. |
| **7. Unauthorized Alert Tampering** | Malicious insider modifies alert status to hide an ongoing infiltration. | Analyst patch endpoint (`PATCH /api/v1/alerts/{id}`) requires API Key authentication (`X-API-Key`). Every state change appends an immutable `AnalystActionRecord` audit log. |
| **8. SQL Injection** | Attacker crafts malicious strings in sensor IDs or threat labels. | Storage layer uses SQLAlchemy ORM with parameterized SQL statements; raw string concatenation is prohibited. |
| **9. Broker / Worker Disconnect** | Stream consumer or broker process crashes midway through a batch. | At-least-once delivery with Pending Entry List (PEL). Replayed events are deduplicated via unique primary keys on `soc_alerts.alert_id`. |
| **10. Poison Pill Loop** | A message crashes downstream inference on every retry. | `DeadLetterQueue` quarantines permanently failing messages to `netdefy:dlq:stream` after max retry attempts, issuing an `XACK` on the main stream to prevent deadlocks. |
