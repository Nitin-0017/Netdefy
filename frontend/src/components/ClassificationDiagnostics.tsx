import React, { useEffect, useState } from 'react';
import { ConfusionMatrixResponse } from '../types/research';
import { apiService } from '../services/api';
import { Binary, AlertTriangle, Sparkles } from 'lucide-react';

export const ClassificationDiagnostics: React.FC = () => {
  const [data, setData] = useState<ConfusionMatrixResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'validation' | 'open_set'>('validation');

  useEffect(() => {
    apiService
      .getConfusionMatrices()
      .then((res) => {
        setData(res);
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

  if (error || !data) {
    return (
      <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400">
        Failed to load confusion matrices: {error}
      </div>
    );
  }

  const { validation_closed_set, test_open_set } = data;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner & Switcher */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2.5 py-1 rounded-md">
            Classification Forensics
          </span>
          <h2 className="text-xl font-bold text-white mt-2">
            Supervised XGBoost Diagnostics & Open-Set Error Analysis
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-2xl">
            Compare verified closed-set performance (8 trained classes on validation split) against open-set holdout evaluation (14 classes on test split, revealing closed-set blindness on unseen attacks).
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('validation')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
              activeTab === 'validation'
                ? 'bg-cyan-500 text-black font-bold shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Validation Closed Set (8x8)
          </button>
          <button
            onClick={() => setActiveTab('open_set')}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
              activeTab === 'open_set'
                ? 'bg-cyan-500 text-black font-bold shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Holdout Open Set (14x8)
          </button>
        </div>
      </div>

      {activeTab === 'validation' ? (
        /* Validation Closed Set (8x8) View */
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center space-x-2">
                  <Binary className="w-5 h-5 text-emerald-400" />
                  <span>Validation Confusion Matrix (Closed-Set, 8 Classes)</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Evaluated on 20,000 validation flows across exactly the 8 classes seen during training. Overall Accuracy: 99.67%, Macro F1: 97.59%.
                </p>
              </div>
            </div>

            {/* Matrix Heatmap Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-center text-xs font-mono border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[10px]">
                    <th className="p-2 text-left bg-slate-950">True \ Predicted</th>
                    {validation_closed_set.labels.map((lbl) => (
                      <th key={lbl} className="p-2 max-w-[90px] truncate bg-slate-950 text-slate-300" title={lbl}>
                        {lbl}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {validation_closed_set.matrix.map((row, rIdx) => {
                    const rowLabel = validation_closed_set.labels[rIdx];
                    const rowTotal = row.reduce((a, b) => a + b, 0);
                    return (
                      <tr key={rowLabel} className="hover:bg-slate-800/30">
                        <td className="p-2 text-left font-bold text-slate-200 bg-slate-950/70 border-r border-slate-800 whitespace-nowrap">
                          {rowLabel}
                        </td>
                        {row.map((cell, cIdx) => {
                          const isDiagonal = rIdx === cIdx;
                          const cellRatio = rowTotal > 0 ? cell / rowTotal : 0;
                          let bg = 'bg-slate-900/40';
                          if (cell > 0) {
                            if (isDiagonal) {
                              bg = cellRatio > 0.9 ? 'bg-emerald-500/25 text-emerald-300 font-bold' : 'bg-emerald-500/15 text-emerald-400';
                            } else {
                              bg = 'bg-rose-500/30 text-rose-300 font-bold';
                            }
                          }
                          return (
                            <td key={cIdx} className={`p-2 border border-slate-800/40 ${bg}`}>
                              {cell.toLocaleString()}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Per-Class Metrics Table */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg">
            <h3 className="text-base font-bold text-white mb-4">
              Closed-Set Per-Class Performance Breakdown
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                    <th className="py-2.5 px-4">Class Label</th>
                    <th className="py-2.5 px-4">Validation Support</th>
                    <th className="py-2.5 px-4">Precision</th>
                    <th className="py-2.5 px-4">Recall</th>
                    <th className="py-2.5 px-4">F1 Score</th>
                    <th className="py-2.5 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {Object.entries(validation_closed_set.per_class_metrics).map(([cls, metrics]) => (
                    <tr key={cls} className="hover:bg-slate-800/30">
                      <td className="py-3 px-4 font-bold text-white">{cls}</td>
                      <td className="py-3 px-4 text-slate-300">{metrics.support.toLocaleString()}</td>
                      <td className="py-3 px-4 text-cyan-300 font-semibold">{(metrics.precision * 100).toFixed(1)}%</td>
                      <td className="py-3 px-4 text-emerald-300 font-semibold">{(metrics.recall * 100).toFixed(1)}%</td>
                      <td className="py-3 px-4 text-purple-300 font-bold">{(metrics.f1 * 100).toFixed(1)}%</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px]">
                          Validated
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* Holdout Open Set (14x8) View */
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-amber-500/20 shadow-lg">
            <div className="flex items-start justify-between flex-wrap gap-4 mb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center space-x-2">
                  <AlertTriangle className="w-5 h-5 text-amber-400" />
                  <span>Open-Set Holdout Matrix: 14 Ground Truth Classes vs. 8 Supervised Classes</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1 max-w-2xl">
                  Illustrates the fatal flaw of relying solely on closed-set classifiers in real production networks:
                  when novel attacks (PortScan, DDoS, Bot, Infiltration) occur, a closed-set classifier cannot output "Unknown",
                  misclassifying 71.72% of them as benign.
                </p>
              </div>
              <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-mono">
                71.72% Unseen Attack Misclassification Rate
              </div>
            </div>

            {/* 14x8 Matrix */}
            <div className="overflow-x-auto">
              <table className="w-full text-center text-xs font-mono border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[10px]">
                    <th className="p-2 text-left bg-slate-950">Ground Truth (Test Set)</th>
                    {test_open_set.predicted_labels.map((lbl) => (
                      <th key={lbl} className="p-2 bg-slate-950 text-slate-300 max-w-[90px] truncate" title={lbl}>
                        {lbl}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {test_open_set.true_labels.map((rowLabel, rIdx) => {
                    const row = test_open_set.matrix[rIdx];
                    if (!row) return null;
                    const isUnseenAttack = ![
                      'BENIGN',
                      'DoS GoldenEye',
                      'DoS Hulk',
                      'DoS Slowhttptest',
                      'DoS slowloris',
                      'FTP-Patator',
                      'Heartbleed',
                      'SSH-Patator',
                    ].includes(rowLabel);

                    return (
                      <tr key={rowLabel} className="hover:bg-slate-800/30">
                        <td className="p-2 text-left font-bold bg-slate-950/70 border-r border-slate-800 whitespace-nowrap">
                          <span className={isUnseenAttack ? 'text-amber-400 flex items-center space-x-1.5' : 'text-slate-200'}>
                            {isUnseenAttack && <AlertTriangle className="w-3 h-3 text-amber-400 inline" />}
                            <span>{rowLabel}</span>
                          </span>
                        </td>
                        {row.slice(0, 8).map((cell, cIdx) => {
                          const isMisclassifiedAsBenign = cIdx === 0 && isUnseenAttack && cell > 0;
                          let bg = 'bg-slate-900/40 text-slate-400';
                          if (cell > 0) {
                            if (isMisclassifiedAsBenign) {
                              bg = 'bg-rose-500/30 text-rose-300 font-bold';
                            } else {
                              bg = 'bg-slate-800 text-slate-200 font-semibold';
                            }
                          }
                          return (
                            <td key={cIdx} className={`p-2 border border-slate-800/40 ${bg}`}>
                              {cell.toLocaleString()}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Research Insight Card */}
          <div className="p-5 rounded-xl bg-slate-900 border border-cyan-500/20 text-xs text-slate-300 space-y-2">
            <h4 className="font-mono font-bold text-cyan-400 uppercase tracking-wider flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span>How the NETDEFY Hybrid Engine Resolves Open-Set Blindness</span>
            </h4>
            <p className="leading-relaxed text-slate-400">
              When PortScan or DDoS flows arrive at inference time, XGBoost misclassifies them as BENIGN with false certainty.
              However, the <strong>PyTorch Autoencoder</strong> and <strong>Isolation Forest</strong> detect severe feature reconstruction
              deviations, producing high anomaly percentiles (&gt;0.9821). The <strong>Hybrid Decision Engine</strong> detects this divergence
              and escalates the flow to <strong className="text-amber-300 font-mono">SUSPICIOUS_UNKNOWN</strong> or <strong className="text-purple-300 font-mono">REVIEW_REQUIRED</strong>,
              preventing silent security breaches without fabricating attack labels.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
