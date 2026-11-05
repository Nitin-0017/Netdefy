# NETDEFY — PHASE 6 ARCHITECTURAL AUDIT
## Backend Architecture, Reusability, Service Boundaries & Stream Processing Blueprint

---

### Executive Summary

NETDEFY has achieved validated research milestones across Phases 1 through 5.1:
- **Phase 4D:** Unified hybrid inference engine fusing Isolation Forest, Deep Autoencoder, and XGBoost with percentile calibration and confidence rejection.
- **Phase 5 & 5.1:** Two-tiered behavioural network intelligence engine combining Tier A intra-flow dynamics and Tier B streaming multi-flow context, validated on out-of-distribution traffic from CSE-CIC-IDS2018.

**Phase 6 Transition:** Moves NETDEFY from an offline experimental evaluation harness into a real-time-capable network intelligence platform. This audit reviews existing components, documents reusable modules, analyzes resource and reliability constraints, evaluates broker architectures (Redis Streams vs. Apache Kafka), and specifies service boundaries for the production SOC engine.

---

### 1. Reusable Modules & Source Assets

| Layer / Phase | Existing Module | Reusability Assessment | Action in Phase 6 |
|---|---|---|---|
| **Phase 1: Config & Utils** | `netdefy.config.settings`, `netdefy.utils.logging`, `device` | **100% Reusable**. Centralized Pydantic settings and deterministic logging. | Extend settings with streaming, broker, and storage parameters. |
| **Phase 3: Preprocessing** | `netdefy.preprocessing.scaler`, `pipeline`, `schema` | **100% Reusable**. Pre-fitted standard scaler (`standard_scaler.joblib`) and 76-feature canonical schema. | Use for zero-copy flow vector normalization prior to inference. |
| **Phase 4A/B/C: Models** | `netdefy.models.isolation_forest`, `autoencoder`, `xgboost_classifier` | **100% Reusable**. Frozen production model checkpoints with verified SHA-256 hashes. | Loaded read-only into inference pipeline. |
| **Phase 4D: Hybrid Engine** | `netdefy.hybrid.inference_pipeline`, `decision_engine`, `score_fusion`, `score_calibration` | **100% Reusable**. Encapsulates tri-model scoring, calibration, and explainability. | Serves as the core flow-scoring engine within the stream consumer. |
| **Phase 5: Behavioural Engine**| `netdefy.behaviour.pipeline_adapter`, `window_aggregator`, `destination_diversity`, `burst_detection` | **100% Reusable**. Stateful sliding-window aggregator and connection pattern analyzers. | Consumes validated streaming events; updates bounded rolling deques. |
| **Evaluation & Data** | `netdefy.data.*`, `netdefy.evaluation.*` | **Reusable for verification**. | Used by benchmark scripts and unit test harnesses. |

---

### 2. Existing API Capabilities & Gaps

- **Current State:**
  - `fastapi` (0.162.0) and `uvicorn` (0.54.0) are declared in `pyproject.toml` and installed in the virtual environment.
  - No user-facing API application or routes currently exist in `src/netdefy/`.
  - Directory `src/netdefy/inference/` contains only an empty `__init__.py`.
- **Phase 6 Gap Analysis:**
  - Need a production FastAPI application with structured routers:
    - `/api/v1/events` (single-event ingestion)
    - `/api/v1/events/batch` (high-throughput batch ingestion)
    - `/api/v1/alerts` (SOC alert query, pagination, severity filtering)
    - `/api/v1/alerts/{alert_id}` (detailed alert inspection and workflow transitions)
    - `/api/v1/metrics` (Prometheus-compatible ingestion and model latency metrics)
    - `/api/v1/health`, `/api/v1/ready` (liveness and readiness probes)
    - `/api/v1/models` (model registry manifest, loaded weights, and checksums)
    - `/api/v1/stream/status` (consumer group lag, queue depth, backpressure status)

---

### 3. Existing Event Schemas & Ingestion Needs

- **Current State:**
  - `netdefy.behaviour.schema.NetworkEvent` is a simple dataclass holding basic flow attributes (`flow_id`, `timestamp`, `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`, `packet_count`, `byte_count`, `features`).
- **Phase 6 Requirements:**
  - Need an enterprise-grade, versioned Pydantic V2 schema (`NetworkFlowEvent`) supporting:
    - Unique deterministic or UUIDv5 event identifiers.
    - Explicit separation of `event_timestamp` (event generation time on the sensor) and `ingestion_timestamp` (arrival time at the ingestion gateway).
    - Structured sensor metadata (`sensor_id`, capture interface).
    - Strict numeric boundary validation (e.g., ports $\in [0, 65535]$, duration $\ge 0$, packets/bytes $\ge 0$).
    - Validation of the 76 continuous features required by Phase 4D, with immediate rejection of non-finite ($NaN$, $\pm\infty$) inputs.
    - Graceful handling of masked IP identifiers (`null` support with explicit `context_status = "REDUCED_CONTEXT"`).

---

### 4. Model Loading & Inference Requirements

- **Model Bundle Checksums:**
  - Isolation Forest: `artifacts/models/isolation_forest/v1/model.joblib`
  - Deep Autoencoder: `artifacts/models/autoencoder/v1/best_model.pt`
  - XGBoost Classifier: `artifacts/models/xgboost_classifier/v1/model.json`
  - Scaler: `artifacts/preprocessing/standard_scaler.joblib`
  - Calibrators: `artifacts/models/hybrid/v1/calibrator_if.json`, `calibrator_ae.json`
- **Inference Lifecycle:**
  - Load models **once** during service startup / consumer initialization.
  - Set PyTorch to evaluation mode (`torch.set_grad_enabled(False)`, `eval()`).
  - Batching: Support micro-batching ($N = 32\text{ to } 256$) to amortize tensor conversion and forward-pass overhead.
  - Device: Default to CPU-first execution (ensuring deterministic cross-platform execution on macOS arm64 and Linux x86_64).

---

### 5. Behavioural State Requirements

- **State Management:**
  - Stateful components (`WindowAggregator`, `DestinationDiversityAnalyzer`, `HostProfileManager`) track multi-flow context across sliding temporal windows.
- **Memory Bounding:**
  - Enforce strict LRU capacity limits on host profiles ($M \le 10,000$ hosts) to guarantee $O(1)$ updates and prevent memory exhaustion under spoofed address flooding.
  - Cap sliding window event deques to max $10,000$ events per window.
  - Automatically evict expired events beyond $\Delta t = 60\text{ seconds}$.

---

### 6. Storage Architecture: Relational vs. Document

- **Audit Findings:**
  - No database exists in the project; offline benchmarks stored splits in Parquet files.
  - Requirements for SOC alerts:
    - Relational integrity: Alerts link to events, analyst notes, audit trails, and baseline snapshots.
    - Transactional guarantees: Atomically persist alerts and commit consumer message offsets to prevent alert loss or duplicate alert explosions.
    - Search & Filtering: Filter alerts by timestamp, severity, status, decision, and destination port.
- **Architectural Decision:**
  - Use **SQLAlchemy (Core + ORM)** with a connection-abstracted repository pattern.
  - **Development / Local / CI:** SQLite with Write-Ahead Logging (`WAL` mode), synchronous pragma `NORMAL`, and foreign key enforcement.
  - **Production:** PostgreSQL (via same SQLAlchemy models with connection string swap).

---

### 7. Hardware & Resource Constraints

- **Host Environment:** Apple Silicon M3, 8 GB unified memory, Python 3.12.13.
- **Target Memory Footprint:** Process RSS must remain strictly $< 150\text{ MB}$ under sustained load.
- **Target CPU Budget:** Single worker must not exceed 80% CPU under normal load ($2,000\text{ flows/sec}$ ingestion).
- **Latency Budget:**
  - Event ingestion to broker: $< 2.0\text{ ms}$ (p95).
  - Stream consumer end-to-end processing: $< 10.0\text{ ms}$ (p95).

---

### 8. Message Broker Selection: Redis Streams vs. Apache Kafka

| Dimension | Redis Streams | Apache Kafka | Architectural Decision |
|---|---|---|---|
| **Memory Footprint** | Extremely low ($\sim 15\text{ MB}$ base RSS) | High ($\ge 500\text{ MB}$ JVM + ZooKeeper/KRaft) | **Redis Streams** selected for NETDEFY core deployment. |
| **Operational Complexity** | Single binary or lightweight container; zero JVM tuning | Complex broker cluster, partition management, JVM garbage collection | **Redis Streams** enables immediate local & CI testing. |
| **Delivery & Groups** | Native consumer groups (`XREADGROUP`), PEL (`XPENDING`), `XACK`, `XCLAIM` | Native consumer groups, partition rebalancing, offset commits | Both satisfy at-least-once requirements. |
| **Throughput on Dev Host**| $50,000+$ ops/sec in-memory | $100,000+$ ops/sec partitioned | Redis Streams exceeds single-node requirement. |
| **CI Compatibility** | Runs natively or via lightweight in-memory broker adapter | Heavy; requires external docker daemon in CI | **Redis Streams + InMemoryBroker** selected. |

**Decision:**
Implement a decoupled `BrokerInterface`. Provide `RedisStreamsBroker` as the production message broker adapter, and `InMemoryStreamBroker` as the high-fidelity embedded test/CI adapter implementing identical consumer groups, pending entry lists (PEL), acknowledgements, and dead-letter queue behavior.

---

### 9. Service Boundaries

```
 +-------------------------------------------------------------------------+
 |                          INGESTION BOUNDARY                             |
 |                                                                         |
 |  [ Network Sensors / PCAP Exporters / SOC Ingestion Agents ]            |
 |                                |                                        |
 |                                v                                        |
 |                    FastAPI Ingestion Gateway                            |
 |           (/api/v1/events, /api/v1/events/batch)                        |
 |                                |                                        |
 |                                v                                        |
 |                    Pydantic Schema Validation                           |
 |                                |                                        |
 |                                v                                        |
 |                     Event Deduplicator (LRU)                            |
 |                                |                                        |
 |                                v                                        |
 |                     Backpressure Controller                             |
 +--------------------------------+----------------------------------------+
                                  |
                                  v
 +--------------------------------+----------------------------------------+
 |                       BUFFERING BOUNDARY                                |
 |                                                                         |
 |          Message Broker: Redis Streams (`netdefy:events:stream`)        |
 |                 (Consumer Group: `netdefy-engine-cg`)                   |
 +--------------------------------+----------------------------------------+
                                  |
                                  v
 +--------------------------------+----------------------------------------+
 |                      PROCESSING BOUNDARY                                |
 |                                                                         |
 |                     Stream Consumer Worker                              |
 |                                |                                        |
 |                                v                                        |
 |                   Micro-Batch Aggregator                                |
 |                                |                                        |
 |       +------------------------+-------------------------+              |
 |       |                                                  |              |
 |       v                                                  v              |
 |  Phase 5 Behavioural Context                Phase 3 Preprocessing       |
 |  (WindowAggregator, Diversity, Burst)       (StandardScaler)            |
 |       |                                                  |              |
 |       +------------------------+-------------------------+              |
 |                                |                                        |
 |                                v                                        |
 |                Phase 4D Hybrid Intelligence Engine                      |
 |         (Isolation Forest + Deep Autoencoder + XGBoost)                 |
 |                                |                                        |
 |                                v                                        |
 |               Phase 5 Integrated Decision Synthesizer                   |
 |                                |                                        |
 |                                v                                        |
 |                      Alert Decision Engine                              |
 |              (Deduplication, Correlation, Severity)                     |
 +--------------------------------+----------------------------------------+
                                  |
                                  v
 +--------------------------------+----------------------------------------+
 |                       STORAGE BOUNDARY                                  |
 |                                                                         |
 |            Persistent Alert Repository (SQLAlchemy ORM)                 |
 |               [Alerts, Event Context, Audit Logs]                       |
 |                                |                                        |
 |                                v                                        |
 |                    Broker Offset ACK (`XACK`)                           |
 |                     (At-Least-Once Delivery)                            |
 +--------------------------------+----------------------------------------+
                                  |
                                  v
 +--------------------------------+----------------------------------------+
 |                      INTEGRATION BOUNDARY                               |
 |                                                                         |
 |             SOC REST API (/api/v1/alerts, workflow patch)               |
 |                                |                                        |
 |             SIEM Exporters: CEF (ArcSight) | STIX 2.1 | TAXII           |
 +-------------------------------------------------------------------------+
```

---

### 10. Key Reliability Risks & Mitigation Strategies

1. **Catastrophic Backpressure Explosion:**
   - *Risk:* Upstream event rate exceeding downstream model inference throughput fills broker memory until OOM.
   - *Mitigation:* Implement proactive backpressure monitoring queue depth; reject new events with HTTP 429 (`Too Many Requests`) or apply producer backoff when queue exceeds high-water mark ($L > 50,000$).
2. **Poison Pill Messages:**
   - *Risk:* Malformed or NaN-bearing feature records crash consumer loop repeatedly.
   - *Mitigation:* Isolate schema validation at consumer ingress; route unparseable messages immediately to Dead-Letter Queue (`netdefy:dlq:stream`) with structured error reasons; commit ACK to allow queue progress.
3. **Consumer Crash Before ACK:**
   - *Risk:* Consumer terminates midway through processing a batch, leaving messages unacknowledged.
   - *Mitigation:* Restarting consumer queries pending entry list (`XPENDING` / `XCLAIM`) with minimum idle time threshold ($T_{\text{idle}} \ge 30\text{s}$) to reclaim abandoned messages.
4. **Duplicate Alert Flooding:**
   - *Risk:* Replayed messages create duplicate alerts in SOC database.
   - *Mitigation:* Enforce deterministic alert ID generation (`SHA-256(event_id + model_bundle_hash)`) with a unique database index, making alert persistence idempotent.
5. **Adaptive Baseline Poisoning:**
   - *Risk:* Attacker injects stealthy anomaly traffic to slowly skew baseline statistics.
   - *Mitigation:* Implement strict gatekeeper policy: only high-confidence BENIGN flows (anomaly score $< p50$, zero classifier doubt, zero behavioral triggers) are eligible for baseline adaptation.

