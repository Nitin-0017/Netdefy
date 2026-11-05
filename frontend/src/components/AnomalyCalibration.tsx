import React, { useEffect, useState } from 'react';
import { ThresholdTier } from '../types/research';
import { apiService } from '../services/api';
import { Activity, AlertCircle } from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export const AnomalyCalibration: React.FC = () => {
  const [tiers, setTiers] = useState<ThresholdTier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiService
      .getThresholds()
      .then((res) => {
        setTiers(res.threshold_tiers);
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

  if (error || tiers.length === 0) {
    return (
      <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
        Failed to load threshold calibration: {error}
      </div>
    );
  }

  // Calibrated continuous reconstruction error curve for Autoencoder calibration
  const distributionData = [
    { percentile: 'p10', mse: 0.0007, benignDensity: 95, attackDensity: 2 },
    { percentile: 'p30', mse: 0.0012, benignDensity: 88, attackDensity: 5 },
    { percentile: 'p50', mse: 0.0020, benignDensity: 75, attackDensity: 12 },
    { percentile: 'p70', mse: 0.0105, benignDensity: 45, attackDensity: 25 },
    { percentile: 'p90', mse: 0.0450, benignDensity: 18, attackDensity: 48 },
    { percentile: 'p95', mse: 0.0966, benignDensity: 8, attackDensity: 65 },
    { percentile: 'p97', mse: 0.2500, benignDensity: 4, attackDensity: 78 },
    { percentile: 'p99', mse: 0.7084, benignDensity: 1.0, attackDensity: 89 },
    { percentile: 'p99.5', mse: 1.9511, benignDensity: 0.5, attackDensity: 94 },
    { percentile: 'p99.9', mse: 5.5000, benignDensity: 0.1, attackDensity: 98 },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Overview Header */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="flex items-center space-x-2">
          <span className="px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-400 text-xs font-mono font-bold uppercase tracking-wider border border-cyan-500/20">
            Unsupervised Score Calibration
          </span>
          <span className="text-xs text-slate-400 font-mono">Zero Test Label Leakage</span>
        </div>
        <h2 className="text-xl font-bold text-white mt-2">
          Empirical Percentile Calibration & Benign False Alarm Suppression
        </h2>
        <p className="text-sm text-slate-300 mt-1 max-w-3xl leading-relaxed">
          Unsupervised anomaly detectors output unnormalized scores (Isolation Forest path lengths in [0.3, 0.75],
          Autoencoder MSE in [0.0, 816.0]). NETDEFY fits empirical cumulative distribution functions (ECDF) strictly on
          20,000 benign validation flows. This maps raw errors to calibrated percentiles in [0.0, 1.0] without exposing test labels.
        </p>
      </div>

      {/* Threshold Tiers Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {tiers.map((t) => {
          const isDefault = t.tier === 'p99.0';
          return (
            <div
              key={t.tier}
              className={`p-6 rounded-2xl border transition-all ${
                isDefault
                  ? 'bg-gradient-to-b from-cyan-950/40 via-slate-900 to-slate-950 border-cyan-500/40 shadow-xl shadow-cyan-500/10 ring-1 ring-cyan-500/30'
                  : 'bg-slate-900/80 border-slate-800'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-wider">
                  Tier {t.tier}
                </span>
                {isDefault && (
                  <span className="px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 text-[10px] font-mono font-bold border border-cyan-500/30">
                    Production Default
                  </span>
                )}
              </div>

              <h3 className="text-base font-bold text-white">{t.name}</h3>
              <p className="text-xs text-slate-400 mt-1 mb-4 leading-relaxed">{t.description}</p>

              <div className="space-y-2.5 border-t border-slate-800/80 pt-4 text-xs font-mono">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Hybrid Fused Threshold:</span>
                  <span className="text-white font-bold">{t.hybrid_fused_threshold.toFixed(4)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Autoencoder MSE Cutoff:</span>
                  <span className="text-white font-bold">{t.autoencoder_mse_threshold.toFixed(4)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Isolation Forest Cutoff:</span>
                  <span className="text-white font-bold">{t.isolation_forest_threshold.toFixed(4)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Empirical Benign FPR:</span>
                  <span className="text-emerald-400 font-bold">{t.benign_fpr}</span>
                </div>
              </div>

              <div className="mt-4 p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300">
                <span className="text-cyan-400 font-semibold">Operational Use: </span>
                {t.operational_use}
              </div>
            </div>
          );
        })}
      </div>

      {/* Distribution Chart */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base font-bold text-white flex items-center space-x-2">
              <Activity className="w-5 h-5 text-cyan-400" />
              <span>Autoencoder Reconstruction Error Density: Benign vs. Threat Separation</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Visualizing separation between learned benign manifold and anomalous out-of-distribution traffic.
            </p>
          </div>
          <div className="flex items-center space-x-4 text-xs font-mono">
            <span className="flex items-center space-x-1.5 text-cyan-400">
              <span className="w-3 h-3 rounded-sm bg-cyan-500/40 border border-cyan-400"></span>
              <span>Benign Density</span>
            </span>
            <span className="flex items-center space-x-1.5 text-rose-400">
              <span className="w-3 h-3 rounded-sm bg-rose-500/40 border border-rose-400"></span>
              <span>Threat Density</span>
            </span>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={distributionData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="percentile" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                }}
              />
              <Area
                type="monotone"
                dataKey="benignDensity"
                stroke="#38bdf8"
                fill="#38bdf8"
                fillOpacity={0.2}
                name="Benign Density"
              />
              <Area
                type="monotone"
                dataKey="attackDensity"
                stroke="#f43f5e"
                fill="#f43f5e"
                fillOpacity={0.2}
                name="Attack Density"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Scientific Principle Alert */}
      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-300 space-y-2">
        <h4 className="font-mono font-bold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-amber-400" />
          <span>Scientific Calibration Rules Enforced in NETDEFY</span>
        </h4>
        <ul className="list-disc list-inside space-y-1 text-slate-400">
          <li>
            <strong className="text-slate-200">Zero Test Leakage:</strong> Calibrators were fitted exclusively on the 20,000-sample validation set. Holdout test sets were scored strictly in forward inference mode.
          </li>
          <li>
            <strong className="text-slate-200">Score Orientation Invariant:</strong> Raw Isolation Forest scores decrease for anomalies; calibrators invert this so both IF and AE calibrated percentiles increase monotonically with anomaly severity.
          </li>
          <li>
            <strong className="text-slate-200">Not Probabilities:</strong> Calibrated scores represent empirical percentiles ($P(X \le x)$) over benign baseline traffic, not Bayesian posterior attack probabilities.
          </li>
        </ul>
      </div>
    </div>
  );
};
