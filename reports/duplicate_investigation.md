# NETDEFY Duplicate Record & Data Leakage Forensic Investigation

## 1. Executive Summary

- **Total Records Inspected:** 2,830,743
- **Exact Intra-File Duplicates:** 256,479 (9.06%)
- **Exact Inter-File Duplicates:** 51,902

## 2. Root Cause Analysis in Network Telemetry

Duplicate network flows occur primarily due to:
1. **Packet Capture Tap Placement:** Dual-homed monitoring taps and switched port analyzers (SPAN)
   duplicate bidirectional flow headers when packets cross multiple network interfaces.
2. **TCP Retransmission & Keep-Alives:** Long-lived connection sessions generate identical flow
   feature summaries across window timeouts.
3. **FlowMeter Timeout Chunking:** Fixed active/idle timeout boundaries artificially shard
   continuous network flows into identical statistical representations.

## 3. Data Leakage Implications

- **Train/Test Contamination:** If duplicate flows exist across partitions, random splitting
   artificially inflates evaluation metrics because the model memorizes exact flow vectors.
- **Temporal Splitting Remedy:** Chronological partitioning combined with deduplication
   eliminates cross-partition identical flow memorization.
- **Preservation Policy:** Raw files remain completely untouched in `data/raw/`; deduplication
   will be executed strictly downstream in `src/netdefy/preprocessing/` for Phase 3.