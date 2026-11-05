# NETDEFY — PHASE 6 EVENT SCHEMA & INGESTION CONTRACT
## Real-Time Network Telemetry Specification, Validation Invariants & Context Attribution

---

### 1. Overview & Architectural Role

The Event Ingestion Layer serves as the front-line gatekeeper of the NETDEFY real-time stream processor. It enforces strict structural, temporal, and numeric invariants on incoming network flow telemetry, guaranteeing that corrupt, malformed, or out-of-bounds events are rejected before entering the message broker and downstream neural-hybrid inference pipelines.

---

### 2. Versioned Canonical Schema (`v1.0`)

The primary data contract is implemented via Pydantic V2 in [`src/netdefy/streaming/event_schema.py`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/streaming/event_schema.py).

#### Structural Representation
```json
{
  "event_id": "8a3f9104b2c174e50821903fa6438910",
  "schema_version": "1.0",
  "event_timestamp": "2026-11-05T10:00:00Z",
  "ingestion_timestamp": "2026-11-05T10:00:00.125000Z",
  "source": {
    "sensor_id": "sensor-perimeter-01",
    "source_ip": "192.168.1.105",
    "destination_ip": "10.0.0.50",
    "source_port": 51520,
    "destination_port": 443,
    "protocol": "TCP"
  },
  "flow": {
    "duration": 1.2504,
    "forward_packets": 6,
    "backward_packets": 4,
    "forward_bytes": 482,
    "backward_bytes": 1284
  },
  "features": {
    "Flow Duration": 1250400.0,
    "Total Fwd Packets": 6.0,
    "Total Backward Packets": 4.0,
    "Fwd Packet Length Max": 240.0
  },
  "metadata": {
    "vlan_id": 100,
    "interface": "eth0"
  },
  "context_status": "FULL_CONTEXT"
}
```

---

### 3. Field Invariants & Constraints

| Field | Type | Required | Constraints / Invariant Rules |
|---|---|---|---|
| `event_id` | String | Auto | Deterministic SHA-256 fingerprint generated from sensor, timestamp, destination port, duration, packets, and bytes if not explicitly provided. |
| `schema_version`| String | Yes | Fixed to `"1.0"`. Unsupported versions are rejected. |
| `event_timestamp`| ISO-8601 UTC | Yes | Flow termination time. Must not exceed $+10.0\text{s}$ into the future (NTP skew allowance). In production, flows older than $365$ days are rejected unless `allow_historical=True`. |
| `ingestion_timestamp`| ISO-8601 UTC | Auto | System clock timestamp when the event reached the gateway. Distinguishes event latency from ingestion latency. |
| `source.sensor_id` | String | Yes | Unique sensor / probe / Zeek / Suricata agent identifier. |
| `source.source_ip` | String / null | No | Optional. Never fabricated. If `null`, marks `context_status = "REDUCED_CONTEXT"`. |
| `source.destination_ip` | String / null | No | Optional. Never fabricated. If `null`, marks `context_status = "REDUCED_CONTEXT"`. |
| `source.destination_port`| Integer | Yes | Range $[0, 65535]$. Rejects negative or out-of-range values. |
| `source.protocol` | String | Yes | Transport protocol (e.g. `"TCP"`, `"UDP"`, `"6"`, `"17"`). |
| `flow.duration` | Float | Yes | Must be $\ge 0.0\text{ seconds}$. |
| `flow.forward_packets` | Integer | Yes | Count $\ge 0$. |
| `flow.backward_packets`| Integer | Yes | Count $\ge 0$. |
| `features` | Dict[str, float] | No | Up to 76 model features. **Strict finite requirement**: Any $NaN$, $+\infty$, or $-\infty$ results in immediate rejection. |
| `context_status` | Enum | Auto | `"FULL_CONTEXT"` when both IP endpoints are available; `"REDUCED_CONTEXT"` when either endpoint is absent or masked. |

---

### 4. Validation & Error Handling Specification

When an event violates validation criteria, [`EventValidator`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/streaming/event_validator.py) generates a structured [`IngestionErrorDetail`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/streaming/event_schema.py) with standardized error codes:

| Error Code | Description | Ingestion Action |
|---|---|---|
| `INVALID_SCHEMA` | Missing mandatory fields or malformed JSON structure | Rejected with HTTP 422 |
| `FUTURE_TIMESTAMP` | Event timestamp is $> 10\text{s}$ ahead of gateway clock | Rejected with HTTP 422 |
| `STALE_TIMESTAMP` | Event timestamp exceeds maximum retention horizon | Rejected with HTTP 422 |
| `INVALID_PORT` | Destination port $< 0$ or $> 65535$ | Rejected with HTTP 422 |
| `INVALID_DURATION` | Flow duration $< 0.0$ | Rejected with HTTP 422 |
| `INVALID_FEATURE_VALUES` | Feature map contains $NaN$ or $\pm\infty$ values | Rejected with HTTP 422 |
| `MISSING_FEATURES` | Required 76 features missing when strict mode enabled | Rejected with HTTP 422 |
| `DUPLICATE_EVENT` | Event ID already observed in deduplication window | Rejected with HTTP 409 / Suppressed |

---

### 5. Reduced Context Handling (Zero Fabrication Policy)

In accordance with NETDEFY’s research ethics guidelines established in Phase 5.1:
1. **No IP Fabrication:** Under no circumstances does the pipeline synthesize dummy IP addresses (e.g., `127.0.0.1` or sequential integers) for datasets or sensors where host identities are masked.
2. **Context Adaptation:** When `context_status == "REDUCED_CONTEXT"`, Tier B Multi-Flow context tracks traffic using available metadata (destination ports, sensor IDs, and arrival timing) while explicitly recording `context_status = "REDUCED_CONTEXT"` in the downstream alert record.

