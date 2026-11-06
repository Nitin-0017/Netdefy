import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import {
  DetectionSessionSummary,
  DetectionSessionDetail,
} from '../types/detection';
import {
  Clock,
  Trash2,
  Download,
  Eye,
  X,
  Filter,
  ChevronDown,
  ChevronRight,
  Info,
} from 'lucide-react';

export const DetectionHistory: React.FC = () => {
  const [sessions, setSessions] = useState<DetectionSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected session for inspection
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<DetectionSessionDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [flowFilter, setFlowFilter] = useState<string>('ALL');
  const [expandedFlowId, setExpandedFlowId] = useState<string | number | null>(null);

  const fetchHistory = () => {
    setLoading(true);
    setError(null);
    apiService
      .getDetectionHistory()
      .then((data) => {
        setSessions(data.sessions);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleOpenSession = async (sessionId: string) => {
    setSelectedSessionId(sessionId);
    setLoadingDetail(true);
    try {
      const data = await apiService.getDetectionSession(sessionId);
      setSessionDetail(data);
    } catch (err: any) {
      setError(`Failed to load session details: ${err.message}`);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleClearHistory = async () => {
    if (window.confirm('Are you sure you want to clear all detection history?')) {
      try {
        await apiService.clearDetectionHistory();
        setSessions([]);
        setSelectedSessionId(null);
        setSessionDetail(null);
      } catch (err: any) {
        setError(`Failed to clear history: ${err.message}`);
      }
    }
  };

  const handleDownloadSessionCsv = (session: DetectionSessionDetail) => {
    const header = [
      'Flow ID',
      'Operational Decision',
      'Predicted Class',
      'Confidence',
      'Fused Score',
      'Autoencoder Error',
      'Isolation Forest Score',
      'Ground Truth Label',
      'Top Contributing Feature 1',
      'Top Contributing Feature 2',
    ];
    const rows = session.predictions.map((p) => [
      p.flow_id ?? '',
      p.decision,
      p.classifier.predicted_class,
      p.classifier.top_probability.toFixed(4),
      p.anomaly.fused_score.toFixed(4),
      p.anomaly.autoencoder_raw_error.toFixed(4),
      p.anomaly.isolation_forest_raw_score.toFixed(4),
      p.ground_truth_label ?? 'N/A',
      p.explanation.top_contributing_features[0]?.feature_name ?? '',
      p.explanation.top_contributing_features[1]?.feature_name ?? '',
    ]);
    const csvContent = [header, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `netdefy_session_${session.id}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-cyan-400"></div>
      </div>
    );
  }

  // Filter flows in active session modal
  const filteredFlows = sessionDetail?.predictions.filter((p) => {
    if (flowFilter === 'ALL') return true;
    return p.decision === flowFilter;
  }) || [];

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1 rounded-md">
              Audit & Forensic History
            </span>
          </div>
          <h1 className="text-xl font-bold text-white">Detection Analysis Log</h1>
          <p className="text-xs text-slate-400 max-w-xl">
            Persistent archive of network flow assessments, batch evaluations, and tri-model anomaly scores.
          </p>
        </div>

        {sessions.length > 0 && (
          <button
            onClick={handleClearHistory}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-xs font-mono border border-rose-500/30 transition-all"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear History</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono">
          {error}
        </div>
      )}

      {/* Sessions Table */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center space-x-2">
            <Clock className="w-4 h-4 text-cyan-400" />
            <span>Recorded Analysis Runs ({sessions.length})</span>
          </h2>
        </div>

        {sessions.length > 0 ? (
          <div className="overflow-x-auto border border-slate-800 rounded-xl">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950 text-slate-400 uppercase text-[11px]">
                  <th className="py-3 px-4">Session ID</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Source / Origin</th>
                  <th className="py-3 px-4">Total Flows</th>
                  <th className="py-3 px-4 text-emerald-400">Normal</th>
                  <th className="py-3 px-4 text-rose-400">Suspicious</th>
                  <th className="py-3 px-4 text-amber-400">Review</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                {sessions.map((sess) => {
                  const susp = sess.suspicious_known_count + sess.suspicious_unknown_count;
                  return (
                    <tr key={sess.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 text-cyan-400 font-bold">{sess.id}</td>
                      <td className="py-3 px-4 text-slate-400">
                        {new Date(sess.timestamp).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-white font-sans truncate max-w-xs">{sess.source}</td>
                      <td className="py-3 px-4 text-slate-200 font-bold">{sess.flow_count}</td>
                      <td className="py-3 px-4 text-emerald-400">{sess.normal_count}</td>
                      <td className="py-3 px-4 text-rose-400">{susp}</td>
                      <td className="py-3 px-4 text-amber-400">{sess.review_required_count}</td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleOpenSession(sess.id)}
                          className="inline-flex items-center space-x-1 px-3 py-1 rounded bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 text-xs font-mono border border-cyan-500/30 transition-colors"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Inspect</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-12 text-center text-xs text-slate-500 font-mono space-y-2">
            <div>No analysis history recorded yet.</div>
            <p className="text-[11px] text-slate-600 max-w-md mx-auto">
              Run an analysis in the Analyze Traffic tab (either CSV batch or manual flow) to view records here.
            </p>
          </div>
        )}
      </div>

      {/* Honest Provenance Note */}
      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 text-xs text-slate-400 font-mono flex items-start space-x-2.5">
        <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <p>
          <strong className="text-slate-300">Data Integrity Notice:</strong> Statistical benchmark flow records do not
          include raw Ethernet payload frames, IP address headers, or source hostnames. All analysis timestamps reflect
          the actual moment of inference execution against the NETDEFY backend.
        </p>
      </div>

      {/* Session Details Modal / Drawer */}
      {selectedSessionId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fadeIn">
          <div className="w-full max-w-5xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-bold text-cyan-400">{selectedSessionId}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Archived Run
                  </span>
                </div>
                <h3 className="text-lg font-bold text-white mt-1">
                  {sessionDetail ? sessionDetail.source : 'Loading Session...'}
                </h3>
              </div>

              <div className="flex items-center space-x-3">
                {sessionDetail && (
                  <button
                    onClick={() => handleDownloadSessionCsv(sessionDetail)}
                    className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-mono border border-cyan-500/30 transition-all"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download CSV</span>
                  </button>
                )}

                <button
                  onClick={() => {
                    setSelectedSessionId(null);
                    setSessionDetail(null);
                  }}
                  className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 flex-1 overflow-y-auto space-y-6">
              {loadingDetail ? (
                <div className="flex items-center justify-center py-16">
                  <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan-400"></div>
                </div>
              ) : sessionDetail ? (
                <>
                  {/* Summary Metric Strip */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-[10px] font-mono uppercase text-slate-400 block">Total Flows:</span>
                      <span className="text-xl font-bold font-mono text-white">{sessionDetail.flow_count}</span>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-[10px] font-mono uppercase text-emerald-400 block">Normal:</span>
                      <span className="text-xl font-bold font-mono text-emerald-400">{sessionDetail.normal_count}</span>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-[10px] font-mono uppercase text-rose-400 block">Suspicious:</span>
                      <span className="text-xl font-bold font-mono text-rose-400">
                        {sessionDetail.suspicious_known_count + sessionDetail.suspicious_unknown_count}
                      </span>
                    </div>
                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                      <span className="text-[10px] font-mono uppercase text-amber-400 block">Review Required:</span>
                      <span className="text-xl font-bold font-mono text-amber-400">
                        {sessionDetail.review_required_count}
                      </span>
                    </div>
                  </div>

                  {/* Filter Strip */}
                  <div className="flex items-center justify-between flex-wrap gap-2 pt-2">
                    <div className="flex items-center space-x-1.5 text-xs font-mono">
                      <span className="text-slate-400 mr-2 flex items-center space-x-1">
                        <Filter className="w-3 h-3" />
                        <span>Filter:</span>
                      </span>
                      {['ALL', 'NORMAL', 'SUSPICIOUS_KNOWN', 'REVIEW_REQUIRED', 'SUSPICIOUS_UNKNOWN'].map((st) => (
                        <button
                          key={st}
                          onClick={() => setFlowFilter(st)}
                          className={`px-2.5 py-1 rounded text-xs transition-all ${
                            flowFilter === st
                              ? 'bg-cyan-500 text-slate-950 font-bold'
                              : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                          }`}
                        >
                          {st}
                        </button>
                      ))}
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      Showing {filteredFlows.length} flows
                    </span>
                  </div>

                  {/* Flows List */}
                  <div className="overflow-x-auto border border-slate-800 rounded-xl">
                    <table className="w-full text-left text-xs font-mono">
                      <thead>
                        <tr className="border-b border-slate-800 bg-slate-950 text-slate-400 uppercase text-[11px]">
                          <th className="py-2.5 px-3 w-8"></th>
                          <th className="py-2.5 px-4">Flow ID</th>
                          <th className="py-2.5 px-4">Decision</th>
                          <th className="py-2.5 px-4">Class</th>
                          <th className="py-2.5 px-4">Confidence</th>
                          <th className="py-2.5 px-4">Fused Anomaly</th>
                          <th className="py-2.5 px-4">Autoencoder Error</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-900/40">
                        {filteredFlows.map((flow, fIdx) => {
                          const isExp = expandedFlowId === flow.flow_id;
                          return (
                            <React.Fragment key={flow.flow_id || fIdx}>
                              <tr
                                onClick={() => setExpandedFlowId(isExp ? null : flow.flow_id)}
                                className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                              >
                                <td className="py-2.5 px-3 text-slate-500">
                                  {isExp ? (
                                    <ChevronDown className="w-3.5 h-3.5 text-cyan-400" />
                                  ) : (
                                    <ChevronRight className="w-3.5 h-3.5" />
                                  )}
                                </td>
                                <td className="py-2.5 px-4 text-white font-bold">{flow.flow_id}</td>
                                <td className="py-2.5 px-4">
                                  <span
                                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                      flow.decision === 'NORMAL'
                                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                                        : flow.decision === 'SUSPICIOUS_KNOWN'
                                        ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                                        : flow.decision === 'REVIEW_REQUIRED'
                                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                                        : 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                                    }`}
                                  >
                                    {flow.decision}
                                  </span>
                                </td>
                                <td className="py-2.5 px-4 text-slate-200">{flow.classifier.predicted_class}</td>
                                <td className="py-2.5 px-4 text-slate-300">
                                  {(flow.classifier.top_probability * 100).toFixed(1)}%
                                </td>
                                <td className="py-2.5 px-4 text-slate-300 font-bold">
                                  {flow.anomaly.fused_score.toFixed(4)}
                                </td>
                                <td className="py-2.5 px-4 text-slate-400">
                                  {flow.anomaly.autoencoder_raw_error.toFixed(4)}
                                </td>
                              </tr>

                              {isExp && (
                                <tr className="bg-slate-950/80">
                                  <td colSpan={7} className="p-4 space-y-2 text-xs">
                                    <div className="text-slate-300 font-sans">
                                      <strong className="text-cyan-400">Rationale:</strong> {flow.decision_reason}
                                    </div>
                                    <div className="grid grid-cols-2 gap-3 pt-1">
                                      <div>
                                        <div className="text-[10px] uppercase text-slate-400 font-bold">
                                          Top Residual Features:
                                        </div>
                                        <div className="space-y-1 mt-1">
                                          {flow.explanation.top_contributing_features.slice(0, 3).map((feat, i) => (
                                            <div key={i} className="flex justify-between text-[11px] font-mono text-slate-300">
                                              <span>{feat.feature_name}</span>
                                              <span className="text-amber-400">{feat.reconstruction_error.toFixed(4)}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                      <div>
                                        <div className="text-[10px] uppercase text-slate-400 font-bold">
                                          Class Probabilities:
                                        </div>
                                        <div className="space-y-1 mt-1">
                                          {Object.entries(flow.classifier.class_probabilities)
                                            .sort((a, b) => b[1] - a[1])
                                            .slice(0, 3)
                                            .map(([cls, prob]) => (
                                              <div key={cls} className="flex justify-between text-[11px] font-mono text-slate-300">
                                                <span>{cls}</span>
                                                <span className="text-cyan-400">{(prob * 100).toFixed(1)}%</span>
                                              </div>
                                            ))}
                                        </div>
                                      </div>
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
