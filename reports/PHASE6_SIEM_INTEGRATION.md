# NETDEFY — PHASE 6 SIEM & SOAR INTEGRATION SPECIFICATION
## ArcSight CEF, OASIS STIX 2.1, TAXII Interface & Export Pipelines

---

### 1. Executive Summary & SIEM Integration Architecture

NETDEFY transitions from an isolated analysis engine into an enterprise-integrated threat monitoring platform by supporting standard security operations protocols:
1. **ArcSight Common Event Format (CEF):** High-throughput, newline-delimited syslog stream for Splunk, Micro Focus ArcSight, and IBM QRadar.
2. **OASIS STIX 2.1:** Structured threat intelligence JSON bundles (Observed-Data, Sightings, Indicators).
3. **OASIS TAXII 2.1 Interface:** Channel contract for automated threat sharing.

All serializers are implemented under [`src/netdefy/integrations/`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/integrations/).

---

### 2. Priority 1: ArcSight CEF Implementation & Escaping Rules

Implemented in [`src/netdefy/integrations/cef.py`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/integrations/cef.py).

#### Header Specification
```
CEF:0|NETDEFY|Network Defense Intelligence|0.1.0|DeviceEventClassID|Name|Severity|Extension
```

#### Escaping Invariants
- **Header:** Any pipe (`|`) or backslash (`\`) is escaped as `\|` or `\\`.
- **Extension Key-Value Pairs:** Any equals sign (`=`), backslash (`\`), or newline (`\n`) is escaped as `\=`, `\\`, or literal `\n`.

#### Field Mapping Table
| CEF Field | Source NETDEFY Attribute | Purpose / Type |
|---|---|---|
| `externalId` | `alert.alert_id` | Stable unique alert hash |
| `dvc` | `alert.source_sensor` | Capturing sensor / probe identifier |
| `src` | `alert.source_ip` | Source IP (omitted if masked) |
| `dst` | `alert.destination_ip` | Destination IP (omitted if masked) |
| `dpt` | `alert.destination_port` | Target transport port |
| `proto` | `alert.protocol` | Transport protocol (TCP/UDP) |
| `cat` | `alert.threat_category` | XGBoost/Behavioral attack class |
| `act` | `alert.status` | SOC status (OPEN, INVESTIGATING) |
| `cn1Label=AnomalyScore cn1`| `alert.anomaly_score` | Fused percentile anomaly score |
| `cs1Label=ContextStatus cs1`| `alert.context_status` | FULL_CONTEXT vs REDUCED_CONTEXT |
| `msg` | `alert.decision_reason` | Explainable attribution rationale |

#### Sample Generated CEF Syslog Line
```text
CEF:0|NETDEFY|Network Defense Intelligence|0.1.0|SUSPICIOUS_KNOWN|Netdefy Alert: PortScan (SUSPICIOUS_KNOWN)|8|externalId=9f1a23c4d5e6 dvc=sensor-01 dpt=443 proto=TCP act=OPEN cat=PortScan cs1Label=ContextStatus cs1=REDUCED_CONTEXT cn1Label=AnomalyScore cn1=0.9854 msg=Confirmed PortScan: Intra-flow RST signature corroborated by multi-flow port diversity
```

---

### 3. Priority 2: OASIS STIX 2.1 Object Graph

Implemented in [`src/netdefy/integrations/stix.py`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/integrations/stix.py).

NETDEFY produces compliant STIX 2.1 Bundles adhering to the following relationship model:

```
 +----------------------------------------------------------------+
 |                      STIX 2.1 Bundle                           |
 |                                                                |
 |   [Identity] (NETDEFY Platform)                                |
 |        ^                                                       |
 |        | (created_by_ref)                                      |
 |        +---------------------+-------------------+             |
 |        |                     |                   |             |
 |   [Observed-Data]       [Indicator]         [Sighting]         |
 |        |                     |                   |             |
 |        v (object_refs)       +-------------------+             |
 |   [SCO: Network-Traffic]       (sighting_of_ref)               |
 +----------------------------------------------------------------+
```

#### Ethical Indicator Generation Policy
- **No Indiscriminate Indicators:** Anomalous traffic with an `UNKNOWN` threat category generates **Observed-Data only**—never malicious indicators.
- **Evidence-Based Indicators:** An `Indicator` object is instantiated *only* when supervised classification or structural behavioral evidence confirms a recognized attack pattern (e.g., `PortScan`, `Bot`, `Infiltration`).

---

### 4. Priority 3: OASIS TAXII 2.1 Status & Interface

Implemented in [`src/netdefy/integrations/taxii.py`](file:///Users/nitinkumar/Documents/Netdefy/src/netdefy/integrations/taxii.py).

- **Implementation Level:** The full TAXII 2.1 client envelope protocol, discovery resource generator, and collection submission boundary have been designed and tested against mock responses.
- **Honest Operational Status:** Live over-the-network TAXII synchronization requires an external running TAXII 2.1 server instance (e.g. Medallion or EclecticIQ). In local and CI environments, bundle validity is verified internally via the `TAXIIClientInterface` envelope serializer.

