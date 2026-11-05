# NETDEFY — PHASE 6 STREAM PROCESSOR ARCHITECTURE & DESIGN
## Micro-Batch Stream Ingestion, Multi-Model Pipeline Fusing & Fault-Tolerant Processing

---

### 1. Architectural Overview

The NETDEFY Stream Processor transitions the platform from offline batch dataset evaluation to a high-throughput, real-time threat detection system. It connects external network probes and sensor gateways to the tri-model Phase 4D inference engine and Phase 5 behavioural context tracking via an asynchronous, decoupled message broker.

```
 +-------------------------------------------------------------------------+
 |                               EVENT PRODUCER                            |
 |                                                                         |
 |  [ Raw JSON / Dict Telemetry ] ---> [ Pydantic Schema Validator ]       |
 |                                               |                         |
 |                                               v                         |
 |                                    [ Event Deduplicator ] (LRU)         |
 |                                               |                         |
 |                                               v                         |
 |                                    [ Backpressure Controller ]          |
 +-----------------------------------------------+-------------------------+
                                                 |
                                                 v
 +-----------------------------------------------+-------------------------+
 |                            STREAM BROKER                                |
 |                                                                         |
 |        Stream: `netdefy:events:stream`                                  |
 |        Consumer Group: `netdefy-engine-cg`                              |
 +-----------------------------------------------+-------------------------+
                                                 |
                                                 v
 +-----------------------------------------------+-------------------------+
 |                            STREAM CONSUMER                              |
 |                                                                         |
 |   [ XREADGROUP Batch ] ---> [ Micro-Batch Aggregator ]                  |
 |                                     |                                   |
 |         +---------------------------+---------------------------+       |
 |         |                                                       |       |
 |         v                                                       v       |
 |  [ Phase 5 Behavioural Engine ]                        [ Phase 3 Scaler ]|
 |  - WindowAggregator                                    - StandardScaler |
 |  - DestinationDiversity                                         |       |
 |  - BurstDetector                                                v       |
 |         |                                       [ Phase 4D Hybrid Engine]|
 |         |                                       - Isolation Forest       |
 |         |                                       - Deep Autoencoder      |
 |         |                                       - XGBoost Classifier     |
 |         |                                                       |       |
 |         +---------------------------+---------------------------+       |
 |                                     |                                   |
 |                                     v                                   |
 |                     [ Decision & Alert Synthesizer ]                    |
 |                                     |                                   |
 |         +---------------------------+---------------------------+       |
 |         |                                                       |       |
 |         v                                                       v       |
 |  [ Alert Engine ]                                    [ Adaptive Baseline]|
 |  - Severity Classifier                               - Anti-Poison Gate |
 |  - Deduplication & Correlation                       - Bounded EMA      |
 |  - SQLite / PostgreSQL Persistence                   - Drift Detector   |
 |  - SIEM Exporters (CEF / STIX)                                          |
 |                                                                         |
 |  ---> [ XACK Offset Commit ]                                            |
 +-------------------------------------------------------------------------+
```

---

### 2. Core Subsystems

#### 2.1 Ingestion Gateway & Event Producer (`producer.py`)
- **Pydantic Validation:** Verifies structural schema, ISO-8601 temporal boundaries, and numeric ranges.
- **LRU Deduplication:** Bounded $50,000$-entry LRU cache rejects identical event IDs submitted within the sliding window.
- **Backpressure Monitoring:** Measures stream depth against low ($5,000$), high ($20,000$), and maximum ($50,000$) watermarks, dynamically applying producer throttle delays or returning HTTP 429 rejections to prevent broker memory saturation.

#### 2.2 Stream Consumer & Inference Worker (`consumer.py`)
- **Group Consumption:** Consumes events in micro-batches ($N = 10\text{ to } 64$) from consumer group `netdefy-engine-cg`.
- **Hybrid Multi-Model Scoring:** Feeds 76-feature vectors into the frozen `BehavioralHybridPipeline`, producing percentile-calibrated scores across Isolation Forest, Deep Autoencoder, and XGBoost.
- **Behavioural Context Fusion:** Updates rolling host and destination port deques in `WindowAggregator` and `DestinationDiversityAnalyzer` to detect multi-flow scanning.

#### 2.3 Dead-Letter Queue & Quarantine (`dead_letter_queue.py`)
- Unparseable payloads, corrupt JSON, or malformed feature dictionaries are quarantined to `netdefy:dlq:stream`.
- Poison pills are quarantined and immediately acknowledged in the primary stream, guaranteeing that one corrupt event cannot block the consumer group.

---

### 3. Performance & Resource Bounding

1. **Memory Ceiling:** Sliding windows in `WindowAggregator` are hard-bounded to $10,000$ events with automatic eviction of entries older than $\Delta t = 60\text{s}$.
2. **LRU Host Capacity:** Tracking host profiles is restricted to $M = 10,000$ active endpoints with $O(1)$ eviction.
3. **Throughput Scaling:** The decoupled producer/broker/consumer architecture allows independent scaling of consumers without modifying the ingestion API.

