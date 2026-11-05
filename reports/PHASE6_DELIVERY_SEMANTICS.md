# NETDEFY — PHASE 6 DELIVERY SEMANTICS & CRASH RECOVERY
## Formal Delivery Guarantees, Idempotency & Fault-Tolerance Verification

---

### 1. Delivery Guarantees

In distributed stream processing, claiming "exactly-once" delivery without end-to-end two-phase distributed transactions across message brokers, neural runtimes, and databases is mathematically inaccurate. 

**NETDEFY implements At-Least-Once Delivery with Idempotent Downstream Handling:**
1. **Message Broker Layer:** At-least-once delivery via Redis Streams Consumer Groups.
2. **Inference & Decision Layer:** Stateless, deterministic scoring for identical feature inputs.
3. **Storage & SOC Alert Layer:** Idempotent alert creation using deterministic cryptographic alert IDs and unique database constraints.

---

### 2. Idempotency Invariants

To guarantee that replaying an unacknowledged message does not duplicate SOC alerts:
1. **Deterministic Alert ID:**
   $$\text{Alert\_ID} = \text{SHA-256}(\text{event\_id} \mathbin{\Vert} \text{decision} \mathbin{\Vert} \text{threat\_category} \mathbin{\Vert} \text{severity})[:32]$$
2. **Unique Database Constraint:**
   The `soc_alerts` table enforces a primary key on `alert_id`.
3. **Idempotent Insertion:**
   When `AlertRepository.create_alert()` receives an alert whose `alert_id` already exists, it detects the existing record, suppresses secondary alert creation, logs no duplicate action, and returns `is_created = False`.
4. **Broker Offset Acknowledgment Rule:**
   The consumer issues `XACK` **only after** the alert has been safely written to disk or database. If the process crashes before `XACK`, the message remains in the Pending Entry List (PEL).

---

### 3. Failure Mode & Crash Scenario Analysis

| Crash Scenario | System State at Failure | Recovery Behavior on Restart |
|---|---|---|
| **1. Crash Before Inference** | Message in consumer PEL; no inference run; no alert written. | On consumer restart, `CheckpointManager.reclaim_stale_pending()` reads message from PEL, re-runs inference, and completes processing. |
| **2. Crash After Inference, Before Alert Persistence** | Inference finished in RAM; no alert in database; message still in PEL. | On restart, message is claimed from PEL, re-inferred, persisted, and safely ACKed. Zero alert loss. |
| **3. Crash After Persistence, Before Broker ACK** | Alert persisted in database; message still in PEL; ACK not sent. | Replayed message generates identical `alert_id`. `AlertRepository` recognizes duplicate, suppresses second alert, and issues `XACK`. **Zero duplicate alerts.** |
| **4. Broker Temporary Disconnect** | Stream cannot receive new events or deliver batches. | Producer buffers up to high-watermark or returns HTTP 503/429; consumer pauses loop with exponential backoff; automatically reconnects on recovery. |
| **5. Database Temporary Disconnect** | Hybrid inference completes; alert cannot be written to DB. | RetryPolicy attempts 3 retries with jitter; if DB remains down, consumer does **not** ACK the message, leaving it safe in the broker for subsequent reprocessing. |
| **6. Poison Pill Message (Malformed JSON / NaN features)** | Invalid payload enters broker stream. | Ingestion or consumer schema validation catches error; routes message to Dead-Letter Queue (`netdefy:dlq:stream`); emits `XACK` so queue processing advances. |

