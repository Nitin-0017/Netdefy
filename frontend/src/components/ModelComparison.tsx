import React, { useEffect, useState } from 'react';
import { ModelComparisonItem } from '../types/research';
import { apiService } from '../services/api';
import { BarChart3, Sparkles, CheckCircle } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

export const ModelComparison: React.FC = () => {
  const [models, setModels] = useState<ModelComparisonItem[]>([]);
  const [takeaways, setTakeaways] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'view_a' | 'view_b'>('view_a');

  useEffect(() => {
    apiService
      .getComparison()
      .then((res) => {
        setModels(res.models);
        setTakeaways(res.key_takeaways);
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

  if (error || models.length === 0) {
    return (
      <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
        Failed to load model comparison: {error}
      </div>
    );
  }

  // Prepare chart data for View A
  const chartDataViewA = [
    {
      name: 'Isolation Forest',
      'ROC-AUC': 0.6558,
      'PR-AUC': 0.3423,
      Precision: 0.5106,
      Recall: 0.0654,
      F1: 0.1159,
    },
    {
      name: 'Deep Autoencoder',
      'ROC-AUC': 0.8307,
      'PR-AUC': 0.6021,
      Precision: 0.7542,
      Recall: 0.2865,
      F1: 0.4153,
    },
    {
      name: 'XGBoost (Closed Set)',
      'ROC-AUC': 0.85,
      'PR-AUC': 0.62,
      Precision: 0.9731,
      Recall: 0.2829,
      F1: 0.4383,
    },
    {
      name: 'NETDEFY Hybrid',
      'ROC-AUC': 0.88,
      'PR-AUC': 0.71,
      Precision: 0.8473,
      Recall: 0.2773,
      F1: 0.4178,
    },
  ];

  const disambiguationComparison = [
    {
      metric: 'Attack Detection Recall',
      'View A (Full 50K)': '27.73%',
      'View B (Disambiguated 46.7K)': '37.46%',
      Delta: '+35.1% Relative Gain',
    },
    {
      metric: 'Operational F1 Score',
      'View A (Full 50K)': '0.4178',
      'View B (Disambiguated 46.7K)': '0.5196',
      Delta: '+24.4% Relative Gain',
    },
    {
      metric: 'Autoencoder ROC-AUC',
      'View A (Full 50K)': '0.8307',
      'View B (Disambiguated 46.7K)': '0.8845',
      Delta: '+0.0538 Absolute Gain',
    },
    {
      metric: 'Isolation Forest ROC-AUC',
      'View A (Full 50K)': '0.6558',
      'View B (Disambiguated 46.7K)': '0.7012',
      Delta: '+0.0454 Absolute Gain',
    },
  ];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner & View Switcher */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1 rounded-md">
            Phase 4D & 5.1 Certified Evaluation
          </span>
          <h2 className="text-xl font-bold text-white mt-2">
            Multi-Model Evaluation & Head-to-Head Benchmark Hub
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Comparing Unsupervised Outlier Trees (Isolation Forest), Latent Reconstruction (PyTorch Autoencoder),
            Supervised Gradient Boosting (XGBoost), and Fused Multi-Paradigm Decision Logic (NETDEFY Hybrid).
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveView('view_a')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
              activeView === 'view_a'
                ? 'bg-cyan-500 text-black font-bold shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            View A (Full 50K Holdout)
          </button>
          <button
            onClick={() => setActiveView('view_b')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
              activeView === 'view_b'
                ? 'bg-cyan-500 text-black font-bold shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            View B (Disambiguated)
          </button>
        </div>
      </div>

      {/* Model Cards Head-to-Head */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {models.map((m) => {
          const isHybrid = m.id === 'hybrid_engine';
          return (
            <div
              key={m.id}
              className={`p-5 rounded-2xl border transition-all ${
                isHybrid
                  ? 'bg-gradient-to-b from-cyan-950/40 via-slate-900 to-slate-950 border-cyan-500/40 shadow-lg shadow-cyan-500/10'
                  : 'bg-slate-900/80 border-slate-800'
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <span className="text-[11px] font-mono text-cyan-400 uppercase tracking-wider font-semibold">
                  {m.paradigm.split(' ')[0]}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                  {m.latency_ms.toFixed(2)} ms
                </span>
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">{m.name}</h3>
              <p className="text-xs text-slate-400 font-mono mt-1 mb-4">{m.parameters}</p>

              {/* Metrics Box */}
              <div className="space-y-2 border-t border-slate-800 pt-3 text-xs font-mono">
                {m.holdout_test_view_a?.precision !== undefined && (
                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-slate-400">Precision:</span>
                    <span className="font-bold text-white">
                      {(m.holdout_test_view_a.precision * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
                {m.holdout_test_view_a?.operational_alert_precision !== undefined && (
                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-cyan-400 font-semibold">Alert Precision:</span>
                    <span className="font-bold text-cyan-300">
                      {(m.holdout_test_view_a.operational_alert_precision * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
                {m.holdout_test_view_a?.roc_auc !== undefined && (
                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-slate-400">ROC-AUC:</span>
                    <span className="font-bold text-white">{m.holdout_test_view_a.roc_auc.toFixed(4)}</span>
                  </div>
                )}
                {m.holdout_test_view_a?.pr_auc !== undefined && (
                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-slate-400">PR-AUC:</span>
                    <span className="font-bold text-white">{m.holdout_test_view_a.pr_auc.toFixed(4)}</span>
                  </div>
                )}
                {m.holdout_test_view_a?.false_alarms_per_1000 !== undefined && (
                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-slate-400">False Alarms / 1K:</span>
                    <span className="font-bold text-rose-300">
                      {m.holdout_test_view_a.false_alarms_per_1000.toFixed(2)}
                    </span>
                  </div>
                )}
                {m.holdout_test_view_a?.benign_false_alarm_rate_per_1000 !== undefined && (
                  <div className="flex justify-between items-center text-slate-300">
                    <span className="text-cyan-400 font-semibold">False Alarms / 1K:</span>
                    <span className="font-bold text-emerald-300">
                      {m.holdout_test_view_a.benign_false_alarm_rate_per_1000.toFixed(2)}
                    </span>
                  </div>
                )}
              </div>

              {isHybrid && (
                <div className="mt-4 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-300 font-mono">
                  -46.5% false alarms vs AE alone (-20.3% vs IF)
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Recharts Bar Chart Comparison */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base font-bold text-white flex items-center space-x-2">
              <BarChart3 className="w-5 h-5 text-cyan-400" />
              <span>Comparative Performance on 50,000 Holdout Test Flows</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              ROC-AUC, Precision, Recall, and F1 across all four models on identical test flows.
            </p>
          </div>
        </div>

        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartDataViewA} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} domain={[0, 1.0]} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                }}
              />
              <Legend wrapperStyle={{ paddingTop: '10px', fontSize: '12px' }} />
              <Bar dataKey="ROC-AUC" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Precision" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Recall" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              <Bar dataKey="F1" fill="#a855f7" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Disambiguation Impact (View A vs View B) */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
        <div className="flex items-start justify-between flex-wrap gap-4 mb-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2.5 py-0.5 rounded bg-purple-500/10 text-purple-400 text-xs font-mono border border-purple-500/20 font-semibold uppercase">
                Ambiguity Forensic Analysis
              </span>
              <span className="text-xs text-slate-400 font-mono">View A (Full) vs View B (Disambiguated)</span>
            </div>
            <h3 className="text-lg font-bold text-white mt-1">
              Label Collision Impact: Disambiguation Unlocks +35.1% Relative Recall
            </h3>
          </div>
          <p className="text-xs text-slate-400 max-w-xl">
            In CICIDS2017, 3,305 test records share identical 5-tuples and feature values between benign and attack labels due to logger overlap. Removing these ambiguous collisions demonstrates true model potential.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[11px]">
                <th className="py-3 px-4">Evaluation Metric</th>
                <th className="py-3 px-4">View A (Full 50K Flows)</th>
                <th className="py-3 px-4">View B (Disambiguated 46,695 Flows)</th>
                <th className="py-3 px-4 text-emerald-400">Scientific Impact / Delta</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {disambiguationComparison.map((row) => (
                <tr key={row.metric} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3.5 px-4 font-bold text-white">{row.metric}</td>
                  <td className="py-3.5 px-4 text-slate-300">{row['View A (Full 50K)']}</td>
                  <td className="py-3.5 px-4 text-cyan-300 font-bold">{row['View B (Disambiguated 46.7K)']}</td>
                  <td className="py-3.5 px-4 text-emerald-400 font-semibold">{row.Delta}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Key Takeaways */}
      <div className="p-5 rounded-xl bg-slate-900 border border-slate-800">
        <h4 className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <span>Key Scientific Audit Takeaways</span>
        </h4>
        <div className="space-y-2">
          {takeaways.map((t, idx) => (
            <div key={idx} className="flex items-start space-x-2 text-xs text-slate-300">
              <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              <span>{t}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
