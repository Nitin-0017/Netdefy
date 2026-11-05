# NETDEFY — PHASE 6 ALERT MANAGEMENT & SOC WORKFLOWS
## Deterministic Severity Policy, Correlation Key Formulation & Analyst Audit Lifecycle

---

### 1. Alert Lifecycle & State Machine

NETDEFY provides a formal state machine for SOC alert management, guaranteeing that alert progress is trackable, persistent, and auditable.

```
       +--------------------+
       |   Alert Created    |
       |     (Status: OPEN) |
       +---------+----------+
                 |
                 +-----------------------+
                 |                       |
                 v                       v
       +--------------------+  +--------------------+
       |    ACKNOWLEDGED    |  |   FALSE_POSITIVE   |
       +---------+----------+  +--------------------+
                 |
                 v
       +--------------------+
       |   INVESTIGATING    |
       +---------+----------+
                 |
                 v
       +--------------------+
       |      RESOLVED      |
       +--------------------+
```

All state transitions require an authenticated `analyst_id` and generate an immutable `AnalystActionRecord` containing the timestamp, old status, new status, and analyst commentary.

---

### 2. Deterministic Severity Classification Policy

To prevent arbitrary, non-reproducible alert rankings, alert severity is assigned through a deterministic multi-variable policy implemented in [`src/netdefy/alerts/alert_engine.py`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/alerts/alert_engine.py):

| Severity Level | Trigger Criteria | Operational Urgency |
|---|---|---|
| **CRITICAL** | (Decision = `SUSPICIOUS_KNOWN` $\land$ Anomaly Score $\ge p99.0$) $\lor$ Known Bot/Infiltration threat $\lor$ (Behavioural Scan $\land$ Anomaly Score $\ge p99.0$) | Immediate page / P1 SOC containment |
| **HIGH** | Decision = `SUSPICIOUS_KNOWN` $\lor$ (Decision = `SUSPICIOUS_UNKNOWN` $\land$ Anomaly Score $\ge p99.0$) $\lor$ Active Behavioural Scan or Rate Burst | High priority SOC queue / Triage within 15 mins |
| **MEDIUM** | Decision = `SUSPICIOUS_UNKNOWN` $\lor$ Decision = `REVIEW_REQUIRED` $\lor$ Anomaly Score $\ge p95.0$ | Standard triage queue / Review within 2 hours |
| **LOW** | Low anomaly score ($< p95.0$) with minor classifier divergence | Informational telemetry / Correlation only |

---

### 3. Correlation Without Fabricated Identities

The [`AlertCorrelator`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/alerts/correlation.py) aggregates discrete flow alerts into incident clusters over a sliding $60\text{-second}$ window:
1. **Full Context:** When genuine source IPs are available, alerts are clustered by:
   $$\text{Key}_{\text{full}} = \text{Sensor\_ID} : \text{Source\_IP} : \text{Threat\_Category}$$
2. **Reduced Context (Masked IP Networks):** When IP identities are unavailable, the correlator clusters alerts using verified network coordinates:
   $$\text{Key}_{\text{reduced}} = \text{Sensor\_ID} : \text{Destination\_Port} : \text{Protocol} : \text{Threat\_Category}$$
   The incident record explicitly tags `context_status = "REDUCED_CONTEXT"` so analysts know that multiple clients targeting the same port may be grouped together.

