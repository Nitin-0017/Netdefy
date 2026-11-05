import React, { useEffect, useState } from 'react';
import { ResearchOverview as OverviewType } from '../types/research';
import { apiService } from '../services/api';
import { CheckCircle2, AlertTriangle, Database, Layers, ShieldCheck, Clock, FileText } from 'lucide-react';

export const ResearchOverview: React.FC = () => {
  const [data, setData] = useState<OverviewType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiService
      .getOverview()
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
        Failed to load research overview: {error}
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Hero Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-mono uppercase tracking-wider">Benchmark Records</span>
            <Database className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-extrabold text-white font-mono">
            {data.total_benchmark_records.toLocaleString()}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Sampled from {data.total_raw_dataset_records.toLocaleString()} raw CICIDS2017 flows
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-mono uppercase tracking-wider">Feature Vector Schema</span>
            <Layers className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-extrabold text-white font-mono">{data.feature_count} Float32</div>
          <div className="text-xs text-slate-400 mt-1">
            Service-independent continuous traffic metrics
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-mono uppercase tracking-wider">Trained Classifier Classes</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-extrabold text-emerald-400 font-mono">
            {data.class_architecture.classifier_trained_classes_count} of {data.class_architecture.cicids_total_classes}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Verified closed-set supervised scope
          </div>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-sm">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="font-mono uppercase tracking-wider">Zero-Leakage Invariants</span>
            <ShieldCheck className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-extrabold text-cyan-400 font-mono">
            {data.zero_leakage_invariants} / 20 Verified
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Deterministic seed 42 with temporal day splits
          </div>
        </div>
      </div>

      {/* Critical Scientific Verification: 8 Trained Classes vs 7 Absent/Unseen Classes */}
      <div className="p-6 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950 border border-cyan-500/20 shadow-xl">
        <div className="flex items-start justify-between flex-wrap gap-4 mb-5">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2.5 py-1 rounded-md bg-cyan-500/10 text-cyan-400 text-xs font-mono font-semibold uppercase tracking-wider border border-cyan-500/20">
                Scientific Class Architecture Verification
              </span>
              <span className="text-xs text-slate-400 font-mono">XGBoost v1 Provenance</span>
            </div>
            <h2 className="text-xl font-bold text-white mt-1">
              Classifier Scope: 8 Trained Classes vs. 7 Absent Open-Set Threat Categories
            </h2>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>Open-Set Evaluation: Never expose final test labels during classifier training</span>
          </div>
        </div>

        <p className="text-sm text-slate-300 leading-relaxed mb-6">
          {data.class_architecture.scientific_rationale}
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Supported Trained Classes */}
          <div className="p-5 rounded-xl bg-slate-950/60 border border-emerald-500/20">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold text-emerald-400 uppercase tracking-wider flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4" />
                <span>Supported Classifier Classes ({data.class_architecture.classifier_trained_classes_count})</span>
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 font-mono">
                Tue & Wed Training
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {data.class_architecture.classifier_trained_classes.map((cls, idx) => (
                <div
                  key={cls}
                  className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono text-slate-200 flex items-center justify-between"
                >
                  <span className="font-semibold text-white">{cls}</span>
                  <span className="text-slate-500 text-[10px]">Idx {idx}</span>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-400 mt-3 italic">
              Strictly supervised target domain. Evaluated with 99.67% closed-set accuracy on validation partition.
            </p>
          </div>

          {/* Absent / Unseen Attack Classes */}
          <div className="p-5 rounded-xl bg-slate-950/60 border border-amber-500/20">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4" />
                <span>Absent from Training / Zero-Day Holdout ({data.class_architecture.absent_unseen_classes_count})</span>
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 font-mono">
                Thu & Fri Holdout
              </span>
            </div>
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {data.class_architecture.absent_unseen_classes.map((item) => (
                <div
                  key={item.name}
                  className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs"
                >
                  <div className="flex items-center justify-between font-mono mb-1">
                    <span className="font-bold text-amber-300">{item.name}</span>
                    <span className="text-slate-400 text-[11px]">
                      {item.day} Split ({item.test_count.toLocaleString()} test flows)
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-snug">{item.reason}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Benchmark Partition Architecture */}
      <div className="p-6 rounded-2xl bg-slate-900/70 border border-slate-800 shadow-lg">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center space-x-2">
              <Clock className="w-5 h-5 text-cyan-400" />
              <span>Temporal Partitioning & Zero-Leakage Benchmark Architecture</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Total 200,000 flows split across training, validation, and holdout evaluation without cross-partition contamination.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">Partition Name</th>
                <th className="py-3 px-4">Flow Count</th>
                <th className="py-3 px-4">Source Day</th>
                <th className="py-3 px-4">Class Composition</th>
                <th className="py-3 px-4">Scientific Purpose</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {data.partitions.map((p) => (
                <tr key={p.name} className="hover:bg-slate-800/30 transition-colors">
                  <td className="py-3.5 px-4 font-bold text-white flex items-center space-x-2">
                    <FileText className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{p.name}.parquet</span>
                  </td>
                  <td className="py-3.5 px-4 text-cyan-300 font-bold">{p.records.toLocaleString()}</td>
                  <td className="py-3.5 px-4 text-slate-300">{p.source_day}</td>
                  <td className="py-3.5 px-4 max-w-xs truncate text-[11px] text-slate-400">
                    {Object.entries(p.class_distribution)
                      .slice(0, 3)
                      .map(([k, v]) => `${k} (${v})`)
                      .join(', ')}
                    {Object.keys(p.class_distribution).length > 3 ? '...' : ''}
                  </td>
                  <td className="py-3.5 px-4 text-slate-400 text-[11px] max-w-xs">{p.purpose}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
