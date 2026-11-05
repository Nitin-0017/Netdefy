import React from 'react';
import { Cpu } from 'lucide-react';

export const HybridDecisionView: React.FC = () => {
  const triageStats = [
    {
      category: 'NORMAL',
      count: 45901,
      percentage: '91.80%',
      color: 'border-slate-700 bg-slate-900/60 text-slate-300',
      description: 'Fused anomaly score < p99.0 threshold (0.9821). Conforms to learned benign baseline.',
    },
    {
      category: 'REVIEW_REQUIRED',
      count: 2523,
      percentage: '5.05%',
      color: 'border-purple-500/30 bg-purple-500/10 text-purple-300',
      description: 'Model conflict (e.g. XGBoost predicts attack with >85% confidence, but anomaly score is normal) or severe detector divergence (|s_IF - s_AE| > 0.5).',
    },
    {
      category: 'SUSPICIOUS_KNOWN',
      count: 988,
      percentage: '1.98%',
      color: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
      description: 'High fused anomaly score (>= 0.9821) + High-confidence known attack attribution (DoS, Patator, Heartbleed).',
    },
    {
      category: 'SUSPICIOUS_UNKNOWN',
      count: 588,
      percentage: '1.18%',
      color: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
      description: 'High fused anomaly score (>= 0.9821) but classifier attribution is rejected or claims BENIGN. Zero-Day candidate.',
    },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Overview Header */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="flex items-center space-x-2">
          <span className="px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-400 text-xs font-mono font-bold uppercase tracking-wider border border-cyan-500/20">
            Phase 4D Decision Engine
          </span>
          <span className="text-xs text-slate-400 font-mono">Calibrated Multi-Model Triage</span>
        </div>
        <h2 className="text-xl font-bold text-white mt-2">
          Hybrid Fusion Policy & Conflict-Resilient Decision Architecture
        </h2>
        <p className="text-sm text-slate-300 mt-1 max-w-3xl leading-relaxed">
          The NETDEFY Hybrid Decision Engine fuses unsupervised percentile scores from the Deep Autoencoder and Isolation Forest
          with supervised attack classification, confidence margins, and entropy rejection into a 4-tier triage verdict.
        </p>
      </div>

      {/* Decision Matrix State Diagram Card */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
        <h3 className="text-base font-bold text-white mb-4 flex items-center space-x-2">
          <Cpu className="w-5 h-5 text-cyan-400" />
          <span>Fused Anomaly Score & Classifier Conflict Matrix</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          {/* Anomaly Normal */}
          <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-emerald-400 uppercase">Fused Score &lt; 0.9821 (Normal Anomaly)</span>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 text-[10px]">Baseline</span>
            </div>
            <div className="space-y-2 text-slate-400">
              <div className="p-2.5 rounded bg-slate-900 border border-slate-800/80 flex items-center justify-between">
                <span>Classifier = BENIGN (or low conf attack):</span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-200 font-bold">NORMAL</span>
              </div>
              <div className="p-2.5 rounded bg-slate-900 border border-purple-500/20 flex items-center justify-between">
                <span>Classifier = Known Attack (conf &gt;= 0.85):</span>
                <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-bold">REVIEW_REQUIRED</span>
              </div>
            </div>
            <p className="text-[11px] text-slate-500 leading-snug">
              When supervised model indicates a specific threat but unsupervised reconstruction loss is normal,
              NETDEFY routes to REVIEW_REQUIRED rather than blindly accepting or suppressing.
            </p>
          </div>

          {/* Anomaly Elevated */}
          <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="font-bold text-rose-400 uppercase">Fused Score &gt;= 0.9821 (Anomalous)</span>
              <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 text-[10px]">Alert Tier</span>
            </div>
            <div className="space-y-2 text-slate-400">
              <div className="p-2.5 rounded bg-slate-900 border border-rose-500/20 flex items-center justify-between">
                <span>Classifier = High-Conf Known Attack:</span>
                <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold">SUSPICIOUS_KNOWN</span>
              </div>
              <div className="p-2.5 rounded bg-slate-900 border border-amber-500/20 flex items-center justify-between">
                <span>Classifier = Rejected / Low Conf / BENIGN:</span>
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold">SUSPICIOUS_UNKNOWN</span>
              </div>
            </div>
            <p className="text-[11px] text-slate-500 leading-snug">
              Unsupervised anomaly alerts with no confident match in the 8 trained classes are flagged as Zero-Day candidates (SUSPICIOUS_UNKNOWN).
            </p>
          </div>
        </div>
      </div>

      {/* Decision Distribution Breakdown across 50,000 holdout flows */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
        <h3 className="text-base font-bold text-white mb-2">
          Empirical Decision Triage Distribution on 50,000 Holdout Test Flows
        </h3>
        <p className="text-xs text-slate-400 mb-6">
          Real decisions emitted during full holdout evaluation on data/benchmark/v1/test.parquet.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {triageStats.map((stat) => (
            <div
              key={stat.category}
              className={`p-5 rounded-xl border ${stat.color} flex flex-col justify-between`}
            >
              <div>
                <div className="flex items-center justify-between font-mono text-xs mb-2">
                  <span className="font-bold">{stat.category}</span>
                  <span className="text-[11px] opacity-80">{stat.percentage}</span>
                </div>
                <div className="text-2xl font-bold font-mono text-white mb-2">
                  {stat.count.toLocaleString()}
                </div>
              </div>
              <p className="text-[11px] leading-relaxed opacity-90">{stat.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
