import React, { useEffect, useState } from 'react';
import { CuratedSample, PredictionResponse } from '../types/research';
import { apiService } from '../services/api';
import {
  Terminal,
  Play,
  RotateCcw,
  Sliders,
  AlertTriangle,
  Cpu,
  Layers,
  Sparkles,
  Info,
  ShieldCheck,
  ShieldAlert,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export const Playground: React.FC = () => {
  const [samples, setSamples] = useState<CuratedSample[]>([]);
  const [selectedSample, setSelectedSample] = useState<CuratedSample | null>(null);
  const [currentFeatures, setCurrentFeatures] = useState<Record<string, number>>({});
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loadingSamples, setLoadingSamples] = useState(true);
  const [inferring, setInferring] = useState(false);
  const [isModified, setIsModified] = useState(false);
  const [showSliders, setShowSliders] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load curated samples on mount
  useEffect(() => {
    apiService
      .getCuratedSamples()
      .then((res) => {
        setSamples(res.samples);
        if (res.samples.length > 0) {
          const first = res.samples[0];
          setSelectedSample(first);
          setCurrentFeatures({ ...first.features });
          // Automatically run initial prediction on the first sample
          runPrediction(first.features, first.id, false);
        }
        setLoadingSamples(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoadingSamples(false);
      });
  }, []);

  const handleSelectSample = (sample: CuratedSample) => {
    setSelectedSample(sample);
    setCurrentFeatures({ ...sample.features });
    setIsModified(false);
    runPrediction(sample.features, sample.id, false);
  };

  const runPrediction = async (
    featuresToScore: Record<string, number>,
    flowId?: string | number | null,
    synthetic: boolean = false
  ) => {
    setInferring(true);
    setError(null);
    try {
      const res = await apiService.predictFlow({
        features: featuresToScore,
        flow_id: flowId || (selectedSample ? selectedSample.id : 'custom_flow'),
        is_synthetic: synthetic,
      });
      setPrediction(res);
    } catch (err: any) {
      setError(err.message || 'Inference execution failed.');
    } finally {
      setInferring(false);
    }
  };

  const handleFeatureChange = (featureName: string, value: number) => {
    const updated = { ...currentFeatures, [featureName]: value };
    setCurrentFeatures(updated);
    setIsModified(true);
  };

  const handleResetFeatures = () => {
    if (selectedSample) {
      setCurrentFeatures({ ...selectedSample.features });
      setIsModified(false);
      runPrediction(selectedSample.features, selectedSample.id, false);
    }
  };

  if (loadingSamples) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-cyan-400"></div>
      </div>
    );
  }

  // Key editable features for sliders
  const editableFeatures = [
    { name: 'Flow Duration', label: 'Flow Duration (z-score)', min: -1.0, max: 5.0, step: 0.1 },
    { name: 'Total Fwd Packets', label: 'Total Fwd Packets (z-score)', min: -0.5, max: 10.0, step: 0.1 },
    { name: 'Total Backward Packets', label: 'Total Backward Packets (z-score)', min: -0.5, max: 10.0, step: 0.1 },
    { name: 'Fwd Packet Length Mean', label: 'Fwd Packet Length Mean', min: -1.0, max: 8.0, step: 0.1 },
    { name: 'Bwd Packet Length Mean', label: 'Bwd Packet Length Mean', min: -1.0, max: 8.0, step: 0.1 },
    { name: 'Flow IAT Mean', label: 'Flow IAT Mean (z-score)', min: -1.0, max: 6.0, step: 0.1 },
    { name: 'PSH Flag Count', label: 'PSH Flag Count', min: -1.0, max: 4.0, step: 0.1 },
    { name: 'Init_Win_bytes_forward', label: 'Init Win Bytes Fwd', min: -1.0, max: 5.0, step: 0.1 },
  ];

  // Prepare probability data for Recharts
  const classProbData = prediction
    ? Object.entries(prediction.classifier.class_probabilities).map(([name, prob]) => ({
        class: name,
        probability: Number((prob * 100).toFixed(2)),
      }))
    : [];

  // Decision style mapping
  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case 'NORMAL':
        return {
          bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
          icon: <ShieldCheck className="w-5 h-5 text-emerald-400" />,
          label: 'NORMAL TRAFFIC',
        };
      case 'SUSPICIOUS_KNOWN':
        return {
          bg: 'bg-rose-500/15 border-rose-500/40 text-rose-300',
          icon: <ShieldAlert className="w-5 h-5 text-rose-400" />,
          label: 'SUSPICIOUS KNOWN THREAT',
        };
      case 'SUSPICIOUS_UNKNOWN':
        return {
          bg: 'bg-amber-500/15 border-amber-500/40 text-amber-300',
          icon: <AlertTriangle className="w-5 h-5 text-amber-400" />,
          label: 'SUSPICIOUS UNKNOWN (ZERO-DAY CANDIDATE)',
        };
      case 'REVIEW_REQUIRED':
        return {
          bg: 'bg-purple-500/15 border-purple-500/40 text-purple-300',
          icon: <Cpu className="w-5 h-5 text-purple-400" />,
          label: 'REVIEW REQUIRED (MODEL CONFLICT)',
        };
      default:
        return {
          bg: 'bg-slate-800 border-slate-700 text-slate-300',
          icon: <Info className="w-5 h-5 text-slate-400" />,
          label: decision,
        };
    }
  };

  const decisionBadge = prediction ? getDecisionBadge(prediction.decision) : null;

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 shadow-xl">
        <div className="flex items-center space-x-2">
          <span className="px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-400 text-xs font-mono font-bold uppercase tracking-wider border border-cyan-500/20">
            Interactive ML Workbench
          </span>
          <span className="text-xs text-slate-400 font-mono">Real-Time Hybrid Scoring</span>
        </div>
        <h2 className="text-xl font-bold text-white mt-2">
          Multi-Model Inference & Feature Attribution Playground
        </h2>
        <p className="text-xs text-slate-400 mt-1 max-w-3xl leading-relaxed">
          Test real benchmark flow vectors against the live tri-model pipeline. Observe how unsupervised reconstruction errors,
          Isolation Forest path lengths, and supervised softmax margins fuse to formulate actionable threat triage verdicts.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-300 flex items-center space-x-2 font-mono">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Grid: Sample Selector & Controls (Left) | Live Prediction Results (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Samples & Sliders (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Sample Selector */}
          <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span>Curated Benchmark Flows ({samples.length})</span>
              </span>
              <span className="text-[10px] text-slate-500 font-mono">Real Captures</span>
            </div>

            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {samples.map((s) => {
                const isSelected = selectedSample?.id === s.id;
                let badgeColor = 'bg-slate-800 text-slate-400';
                if (s.category_type === 'BENIGN') badgeColor = 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
                if (s.category_type === 'KNOWN_ATTACK') badgeColor = 'bg-rose-500/10 text-rose-300 border border-rose-500/20';
                if (s.category_type === 'UNSEEN_ATTACK') badgeColor = 'bg-amber-500/10 text-amber-300 border border-amber-500/20';

                return (
                  <button
                    key={s.id}
                    onClick={() => handleSelectSample(s)}
                    className={`w-full text-left p-3 rounded-xl border text-xs transition-all ${
                      isSelected
                        ? 'bg-slate-800/90 border-cyan-500/50 shadow-md shadow-cyan-500/10'
                        : 'bg-slate-950/50 border-slate-800 hover:bg-slate-800/40 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-bold text-white font-mono">{s.name}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${badgeColor}`}>
                        {s.category_type}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                      <span>Label: {s.true_label}</span>
                      <span>{s.in_classifier_training ? 'In Classifier Training' : 'Unseen Zero-Day'}</span>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Selected Sample Context */}
            {selectedSample && (
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 text-xs text-slate-300 space-y-1.5 font-mono">
                <div className="text-[11px] text-cyan-400 font-bold uppercase tracking-wider">
                  Forensic Context: {selectedSample.true_label}
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed font-sans">{selectedSample.description}</p>
                <div className="text-[10px] text-slate-500 pt-1">
                  Source: {selectedSample.source_split}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center space-x-2 pt-2">
              <button
                onClick={() => runPrediction(currentFeatures, selectedSample?.id, isModified)}
                disabled={inferring}
                className="flex-1 py-2.5 px-4 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-black font-bold text-xs font-mono flex items-center justify-center space-x-2 shadow-lg shadow-cyan-500/20 transition-all disabled:opacity-50"
              >
                {inferring ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-black border-t-transparent" />
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-black" />
                    <span>Run Live Model Inference</span>
                  </>
                )}
              </button>

              <button
                onClick={() => setShowSliders(!showSliders)}
                className={`p-2.5 rounded-xl border text-xs font-mono transition-all ${
                  showSliders
                    ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400'
                    : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                }`}
                title="Toggle Feature Adjustment Sliders"
              >
                <Sliders className="w-4 h-4" />
              </button>

              {isModified && (
                <button
                  onClick={handleResetFeatures}
                  className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 hover:text-rose-400 transition-all"
                  title="Reset to Authentic Benchmark Values"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Feature Adjustment Sliders (Collapsible) */}
          {showSliders && (
            <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4 animate-fadeIn">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider flex items-center space-x-2">
                  <Sliders className="w-4 h-4" />
                  <span>Feature Adjustment Sliders</span>
                </span>
                {isModified && (
                  <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px] font-mono font-bold border border-amber-500/20">
                    Synthetic Values Active
                  </span>
                )}
              </div>

              {/* Scientific Warning Alert */}
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-200 flex items-start space-x-2 leading-relaxed">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>Scientific Advisory:</strong> Modifying individual sliders independently may create
                  physically non-realizable or protocol-inconsistent traffic states. Benchmark samples represent validated physical packet captures.
                </span>
              </div>

              <div className="space-y-3">
                {editableFeatures.map((f) => {
                  const val = currentFeatures[f.name] ?? 0.0;
                  return (
                    <div key={f.name} className="space-y-1">
                      <div className="flex justify-between text-xs font-mono">
                        <span className="text-slate-300">{f.label}</span>
                        <span className="text-cyan-400 font-bold">{val.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min={f.min}
                        max={f.max}
                        step={f.step}
                        value={val}
                        onChange={(e) => handleFeatureChange(f.name, parseFloat(e.target.value))}
                        className="w-full accent-cyan-400 bg-slate-800 h-1.5 rounded-lg appearance-none cursor-pointer"
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Live Results & Explainability (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          {prediction ? (
            <>
              {/* Decision Verdict Banner */}
              <div className={`p-6 rounded-2xl border shadow-xl ${decisionBadge?.bg}`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    {decisionBadge?.icon}
                    <span className="text-sm font-mono font-extrabold uppercase tracking-wider">
                      {decisionBadge?.label}
                    </span>
                  </div>
                  <span className="text-xs font-mono font-semibold opacity-80">
                    Flow ID: {prediction.flow_id}
                  </span>
                </div>
                <p className="text-xs text-white/90 leading-relaxed font-mono mt-1">
                  {prediction.decision_reason}
                </p>

                {prediction.scientific_note && (
                  <div className="mt-3 p-2.5 rounded-lg bg-black/30 border border-amber-500/30 text-[11px] text-amber-200 flex items-center space-x-2 font-mono">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>{prediction.scientific_note}</span>
                  </div>
                )}
              </div>

              {/* Component Anomaly Scores & Gauge */}
              <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                    <Cpu className="w-4 h-4 text-cyan-400" />
                    <span>Component Anomaly Scores vs. Calibrated p99 Threshold (0.9821)</span>
                  </h3>
                  <span className="text-xs font-mono text-cyan-400 font-bold">
                    Fused: {prediction.anomaly.fused_score.toFixed(4)}
                  </span>
                </div>

                {/* Score Progress Bar */}
                <div className="space-y-1">
                  <div className="h-3 w-full bg-slate-950 rounded-full overflow-hidden border border-slate-800 relative">
                    {/* Threshold Marker at 98.21% */}
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-rose-500 z-10"
                      style={{ left: `${(prediction.anomaly.threshold / 1.0) * 100}%` }}
                      title="p99 Operational Threshold"
                    />
                    <div
                      className={`h-full transition-all duration-500 rounded-full ${
                        prediction.anomaly.is_anomaly
                          ? 'bg-gradient-to-r from-amber-500 to-rose-500'
                          : 'bg-gradient-to-r from-cyan-500 to-emerald-500'
                      }`}
                      style={{ width: `${Math.min(prediction.anomaly.fused_score * 100, 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-slate-500">
                    <span>0.0 (Benign Baseline)</span>
                    <span className="text-rose-400 font-semibold">p99 Threshold (0.9821)</span>
                    <span>1.0 (Maximum Anomaly)</span>
                  </div>
                </div>

                {/* Score Breakdown Cards */}
                <div className="grid grid-cols-2 gap-3 pt-2 text-xs font-mono">
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-slate-400 text-[11px] mb-1">Isolation Forest</div>
                    <div className="text-base font-bold text-white">
                      Cal: {prediction.anomaly.isolation_forest_calibrated_score.toFixed(4)}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      Raw Depth Score: {prediction.anomaly.isolation_forest_raw_score.toFixed(4)}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-slate-400 text-[11px] mb-1">Deep Autoencoder</div>
                    <div className="text-base font-bold text-white">
                      Cal: {prediction.anomaly.autoencoder_calibrated_score.toFixed(4)}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      Raw MSE Loss: {prediction.anomaly.autoencoder_raw_error.toFixed(6)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Supervised XGBoost Probabilities & Rejection Status */}
              <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                      <Layers className="w-4 h-4 text-purple-400" />
                      <span>Supervised Classifier Attribution (8 Trained Classes)</span>
                    </h3>
                  </div>
                  <div className="flex items-center space-x-2 text-xs font-mono">
                    <span className="text-slate-400">Predicted:</span>
                    <span className="font-bold text-purple-300">{prediction.classifier.predicted_class}</span>
                    <span className="text-emerald-400 font-semibold">
                      ({(prediction.classifier.top_probability * 100).toFixed(1)}%)
                    </span>
                  </div>
                </div>

                {/* Rejection Diagnostics Strip */}
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="text-slate-400">Rejection Status: </span>
                    {prediction.classifier.rejected ? (
                      <span className="text-amber-400 font-bold">REJECTED ({prediction.classifier.rejection_reason})</span>
                    ) : (
                      <span className="text-emerald-400 font-bold">ACCEPTED (High Confidence Attribution)</span>
                    )}
                  </div>
                  <div className="flex items-center space-x-3 text-slate-400 text-[11px]">
                    <span>Entropy H: {prediction.classifier.entropy.toFixed(3)}</span>
                    <span>Margin Δp: {prediction.classifier.probability_margin.toFixed(3)}</span>
                  </div>
                </div>

                {/* Probability Bar Chart */}
                <div className="h-52 w-full pt-1">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={classProbData}
                      layout="vertical"
                      margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis
                        type="number"
                        stroke="#64748b"
                        tick={{ fill: '#94a3b8', fontSize: 10 }}
                        domain={[0, 100]}
                        unit="%"
                      />
                      <YAxis
                        type="category"
                        dataKey="class"
                        stroke="#64748b"
                        tick={{ fill: '#e2e8f0', fontSize: 10 }}
                        width={95}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          border: '1px solid #334155',
                          borderRadius: '8px',
                          fontFamily: 'monospace',
                          fontSize: '11px',
                        }}
                      />
                      <Bar dataKey="probability" fill="#a855f7" radius={[0, 4, 4, 0]} name="Confidence %" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Top 5 Feature-Level Reconstruction Deviations */}
              <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-lg space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    <span>Autoencoder Feature-Level Attribution: Top Reconstruction Errors (e_j = (x_j - x̂_j)²)</span>
                  </h3>
                </div>

                <div className="space-y-2">
                  {prediction.explanation.top_contributing_features.map((feat, idx) => (
                    <div
                      key={feat.feature_name}
                      className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 flex items-center justify-between text-xs font-mono"
                    >
                      <div className="space-y-0.5">
                        <div className="font-bold text-white flex items-center space-x-2">
                          <span className="text-cyan-400">#{idx + 1}</span>
                          <span>{feat.feature_name}</span>
                        </div>
                        <div className="text-[11px] text-slate-500">
                          Input: {feat.input_value.toFixed(3)} | Reconstructed: {feat.reconstructed_value.toFixed(3)}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-amber-400 font-bold">
                          Error: {feat.reconstruction_error.toFixed(4)}
                        </div>
                        <div className="text-[10px] text-slate-500">Squared Deviation</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 rounded-2xl bg-slate-900/40 border border-slate-800 text-center text-slate-500 text-xs font-mono">
              Select a benchmark sample or run live inference to view model predictions.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
