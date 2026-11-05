import React, { useEffect, useState } from 'react';
import { ExplainabilitySpec as SpecType, FeatureImportanceItem } from '../types/research';
import { apiService } from '../services/api';
import { AlertCircle, Zap } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export const ExplainabilitySpec: React.FC = () => {
  const [spec, setSpec] = useState<SpecType | null>(null);
  const [featureImportance, setFeatureImportance] = useState<FeatureImportanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([apiService.getExplainabilitySpec(), apiService.getFeatureImportance()])
      .then(([specRes, featRes]) => {
        setSpec(specRes);
        setFeatureImportance(featRes.xgboost_feature_importance_gain.slice(0, 15));
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

  if (error || !spec) {
    return (
      <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
        Failed to load explainability specification: {error}
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Header */}
      <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl">
        <div className="flex items-center space-x-2">
          <span className="px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-400 text-xs font-mono font-bold uppercase tracking-wider border border-cyan-500/20">
            Explainable AI (XAI)
          </span>
          <span className="text-xs text-slate-400 font-mono">Model-Specific Attribution</span>
        </div>
        <h2 className="text-xl font-bold text-white mt-2">
          Grounded Explainability & Low-Latency Feature Attribution
        </h2>
        <p className="text-sm text-slate-300 mt-1 max-w-3xl leading-relaxed">
          In high-throughput network threat detection, explainability methods must be computationally sub-millisecond,
          architecturally grounded in verified model mathematics, and transparent about limitations.
        </p>
      </div>

      {/* Model-Specific Methodology Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {spec.methods.map((m) => (
          <div
            key={m.model}
            className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between text-xs font-mono mb-2">
                <span className="font-bold text-cyan-400 uppercase">{m.model}</span>
                <span className="text-slate-400 font-semibold">{m.computational_complexity.split(' ')[0]}</span>
              </div>
              <h3 className="text-base font-bold text-white mb-2">{m.method_name}</h3>
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 font-mono text-xs text-cyan-300 mb-3 text-center">
                {m.mathematical_formulation}
              </div>
              <p className="text-xs text-slate-300 leading-relaxed mb-4">{m.rationale}</p>
            </div>

            <div className="space-y-2 border-t border-slate-800 pt-3 text-[11px] font-mono">
              <div className="text-slate-400">
                <strong className="text-slate-300">Cost: </strong>
                {m.computational_complexity}
              </div>
              <div className="text-slate-500">
                <strong className="text-amber-400">Limitation: </strong>
                {m.limitations}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Global XGBoost Feature Importance Bar Chart */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base font-bold text-white flex items-center space-x-2">
              <Zap className="w-5 h-5 text-amber-400" />
              <span>Top 15 XGBoost Features by Gain (Reduction in Multi-Class Loss)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Features with the highest discriminative power for separating DoS and Patator attacks from benign traffic.
            </p>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={featureImportance}
              layout="vertical"
              margin={{ top: 10, right: 30, left: 140, bottom: 20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="feature"
                stroke="#64748b"
                tick={{ fill: '#e2e8f0', fontSize: 11 }}
                width={130}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                }}
              />
              <Bar dataKey="gain" fill="#f59e0b" radius={[0, 4, 4, 0]} name="Average Gain" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Why NOT Brute-Force KernelSHAP Section */}
      <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-rose-950/20 border border-rose-500/20 shadow-lg">
        <div className="flex items-center space-x-2 text-rose-400 mb-2">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <h3 className="text-base font-bold text-white font-mono uppercase tracking-wider">
            {spec.why_not_bruteforce_kernel_shap.title}
          </h3>
        </div>
        <p className="text-xs text-slate-400 mb-4 max-w-3xl">
          A common pitfall in machine learning demonstrations is forcing black-box KernelSHAP onto all models.
          In operational cybersecurity systems, this introduces prohibitive computational latency and ungrounded approximations:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
          {spec.why_not_bruteforce_kernel_shap.reasons.map((reason, idx) => (
            <div
              key={idx}
              className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/80 text-slate-300 leading-relaxed"
            >
              <span className="text-rose-400 font-bold mr-1">#{idx + 1}:</span>
              {reason}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
