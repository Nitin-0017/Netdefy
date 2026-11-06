import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { DetectionStats } from '../types/detection';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  FileSearch,
  UploadCloud,
  CheckCircle2,
  Clock,
  ArrowRight,
  Cpu,
  Layers,
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from 'recharts';

interface ConsoleOverviewProps {
  onNavigateToAnalyze: () => void;
  onNavigateToHistory: () => void;
}

export const ConsoleOverview: React.FC<ConsoleOverviewProps> = ({
  onNavigateToAnalyze,
  onNavigateToHistory,
}) => {
  const [stats, setStats] = useState<DetectionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiService
      .getDetectionStats()
      .then((data) => {
        setStats(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-cyan-400"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono">
        Error loading console metrics: {error}
      </div>
    );
  }

  const totalFlows = stats?.total_flows_analyzed || 0;
  const normalFlows = stats?.normal_flows || 0;
  const suspiciousFlows = stats?.suspicious_flows || 0;
  const reviewFlows = stats?.review_required_flows || 0;

  const chartData = [
    { name: 'Normal Traffic', value: normalFlows, color: '#10b981' },
    { name: 'Suspicious Threats', value: suspiciousFlows, color: '#f43f5e' },
    { name: 'Review Required', value: reviewFlows, color: '#f59e0b' },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Hero Operational Banner */}
      <div className="relative overflow-hidden p-6 sm:p-8 rounded-2xl bg-gradient-to-r from-slate-900 via-[#0d1627] to-slate-950 border border-slate-800 shadow-2xl">
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1 rounded-md">
                Production Threat Detection
              </span>
              <span className="text-xs font-mono text-emerald-400 flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Operational</span>
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Network Threat Detection Console
            </h1>
            <p className="text-sm text-slate-300 leading-relaxed">
              Analyze incoming network flows against NETDEFY&apos;s frozen multi-model engine. Detect
              unsupervised statistical outliers, classify known cyberattack signatures, and triage
              ambiguous telemetry in real-time.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
            <button
              onClick={onNavigateToAnalyze}
              className="flex items-center justify-center space-x-2 px-5 py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-sm shadow-lg shadow-cyan-500/25 transition-all w-full sm:w-auto"
            >
              <FileSearch className="w-4 h-4" />
              <span>Analyze Traffic Now</span>
            </button>
            <button
              onClick={onNavigateToHistory}
              className="flex items-center justify-center space-x-2 px-4 py-3 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-200 font-medium text-sm border border-slate-700 transition-all w-full sm:w-auto"
            >
              <Clock className="w-4 h-4 text-slate-400" />
              <span>Detection History</span>
            </button>
          </div>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Analyzed */}
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Total Flows</span>
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
              <Layers className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-extrabold text-white font-mono">
              {totalFlows.toLocaleString()}
            </div>
            <p className="text-xs text-slate-400 mt-1">Evaluated across all sessions</p>
          </div>
        </div>

        {/* Normal Flows */}
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Normal Flows</span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-extrabold text-emerald-400 font-mono">
              {normalFlows.toLocaleString()}
            </div>
            <p className="text-xs text-slate-400 mt-1">Conforming to benign baseline</p>
          </div>
        </div>

        {/* Suspicious Threats */}
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Suspicious Flows</span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-extrabold text-rose-400 font-mono">
              {suspiciousFlows.toLocaleString()}
            </div>
            <p className="text-xs text-slate-400 mt-1">Known attacks & high anomaly</p>
          </div>
        </div>

        {/* Review Required */}
        <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-wider text-slate-400">Review Required</span>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-extrabold text-amber-400 font-mono">
              {reviewFlows.toLocaleString()}
            </div>
            <p className="text-xs text-slate-400 mt-1">Model conflict or border cases</p>
          </div>
        </div>
      </div>

      {/* Main Grid: Chart & Model Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Traffic Breakdown Chart */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-xl flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
            <div>
              <h2 className="text-base font-bold text-white">Detection Triage Distribution</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Proportion of analyzed network telemetry categorized by the 4-state operational engine
              </p>
            </div>
            <span className="text-xs font-mono text-slate-400">
              {totalFlows > 0 ? `${totalFlows} flows` : 'No data'}
            </span>
          </div>

          <div className="py-2 flex items-center justify-center">
            {totalFlows > 0 && chartData.length > 0 ? (
              <div className="w-full h-[260px]">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={chartData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={85}
                      innerRadius={50}
                      paddingAngle={4}
                      isAnimationActive={false}
                    >
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="#0f172a" strokeWidth={2} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        borderColor: '#334155',
                        borderRadius: '0.75rem',
                        fontSize: '12px',
                      }}
                      itemStyle={{ color: '#f8fafc' }}
                    />
                    <Legend
                      verticalAlign="bottom"
                      height={36}
                      formatter={(val) => <span className="text-xs text-slate-300 font-mono">{val}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="text-center py-12 space-y-3">
                <div className="p-3 rounded-full bg-slate-800/60 w-12 h-12 mx-auto flex items-center justify-center text-slate-500">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div className="text-sm font-semibold text-slate-300">No Traffic Analyzed Yet</div>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  Submit a network CSV or manual flow vector in the Analyze Traffic tab to start real-time threat detection.
                </p>
                <button
                  onClick={onNavigateToAnalyze}
                  className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 text-xs font-mono font-medium border border-cyan-500/30"
                >
                  <span>Start Analysis</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Model Provenance & Status */}
        <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-xl space-y-5">
          <div className="border-b border-slate-800/80 pb-3">
            <h2 className="text-base font-bold text-white flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span>Active Inference Models</span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">Certified models loaded into backend memory</p>
          </div>

          <div className="space-y-3">
            {/* Autoencoder */}
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-white">Deep PyTorch Autoencoder</div>
                <div className="text-[11px] text-slate-400">Latent 16-D Reconstruction Engine</div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Loaded (v1)
              </span>
            </div>

            {/* Isolation Forest */}
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-white">Isolation Forest</div>
                <div className="text-[11px] text-slate-400">100 Trees Outlier Detection</div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Loaded (v1)
              </span>
            </div>

            {/* XGBoost */}
            <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-white">XGBoost Classifier</div>
                <div className="text-[11px] text-slate-400">8 Attack Classes (Depth 6, lr 0.1)</div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Loaded (v1)
              </span>
            </div>

            {/* Hybrid Engine */}
            <div className="p-3 rounded-xl bg-slate-950/80 border border-cyan-500/20 bg-cyan-950/10 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-cyan-300">Tri-Model Hybrid Engine</div>
                <div className="text-[11px] text-slate-400">Score Fusion & 4-State Triage</div>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                Operational
              </span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 text-[11px] text-slate-400 space-y-1">
            <div className="font-semibold text-slate-300 flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>Zero-Leakage Invariants Enforced</span>
            </div>
            <p>Thresholds calibrated exclusively on pure benign validation data (p99 = 0.9821).</p>
          </div>
        </div>
      </div>

      {/* Recent Analysis Sessions */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white">Recent Threat Analysis Sessions</h2>
            <p className="text-xs text-slate-400 mt-0.5">Latest network traffic assessments executed by the engine</p>
          </div>
          {stats && stats.recent_sessions.length > 0 && (
            <button
              onClick={onNavigateToHistory}
              className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
            >
              <span>View All History</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>

        {stats && stats.recent_sessions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase">
                  <th className="py-3 px-4">Session ID</th>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Source / Origin</th>
                  <th className="py-3 px-4">Flows</th>
                  <th className="py-3 px-4">Normal</th>
                  <th className="py-3 px-4">Suspicious</th>
                  <th className="py-3 px-4">Review</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {stats.recent_sessions.map((sess) => (
                  <tr key={sess.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 text-cyan-400 font-bold">{sess.id}</td>
                    <td className="py-3 px-4 text-slate-400">
                      {new Date(sess.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-white font-sans truncate max-w-xs">{sess.source}</td>
                    <td className="py-3 px-4 text-slate-200 font-bold">{sess.flow_count}</td>
                    <td className="py-3 px-4 text-emerald-400">{sess.normal_count}</td>
                    <td className="py-3 px-4 text-rose-400">{sess.suspicious_count}</td>
                    <td className="py-3 px-4 text-amber-400">{sess.review_required_count}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={onNavigateToHistory}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] transition-colors"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-slate-500 font-mono">
            No historical sessions recorded. Run an analysis in the Analyze Traffic tab to populate history.
          </div>
        )}
      </div>
    </div>
  );
};
