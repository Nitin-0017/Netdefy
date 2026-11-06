import React, { useEffect, useState, useRef } from 'react';
import { apiService } from '../services/api';
import {
  DetectionSchemaResponse,
  FlowPredictionItem,
  CsvUploadResponse,
} from '../types/detection';
import { CuratedSample } from '../types/research';
import {
  UploadCloud,
  Sliders,
  Play,
  RotateCcw,
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  ShieldAlert,
  Download,
  Filter,
  ChevronDown,
  ChevronRight,
  Info,
  Sparkles,
} from 'lucide-react';

export const AnalyzeTraffic: React.FC = () => {
  const [activeMode, setActiveMode] = useState<'csv' | 'manual'>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('mode') === 'manual' ? 'manual' : 'csv';
  });

  const handleModeSwitch = (mode: 'csv' | 'manual') => {
    setActiveMode(mode);
    const url = new URL(window.location.href);
    url.searchParams.set('mode', mode);
    window.history.replaceState({}, '', url.toString());
  };
  const [schema, setSchema] = useState<DetectionSchemaResponse | null>(null);
  const [curatedSamples, setCuratedSamples] = useState<CuratedSample[]>([]);
  const [loadingSchema, setLoadingSchema] = useState(true);

  // CSV Mode State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvMaxRows, setCsvMaxRows] = useState<number>(250);
  const [csvPreviewRows, setCsvPreviewRows] = useState<string[][]>([]);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [csvAnalyzing, setCsvAnalyzing] = useState(false);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [csvResult, setCsvResult] = useState<CsvUploadResponse | null>(null);
  const [csvFilter, setCsvFilter] = useState<string>('ALL');
  const [expandedFlowId, setExpandedFlowId] = useState<string | number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Manual Mode State
  const [manualFeatures, setManualFeatures] = useState<Record<string, number>>({});
  const [manualFlowId, setManualFlowId] = useState<string>('');
  const [manualAnalyzing, setManualAnalyzing] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualResult, setManualResult] = useState<FlowPredictionItem | null>(null);
  const [selectedSampleId, setSelectedSampleId] = useState<string>('');
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [isModified, setIsModified] = useState(false);

  useEffect(() => {
    Promise.all([
      apiService.getDetectionSchema(),
      apiService.getCuratedSamples(),
    ])
      .then(([schemaData, samplesData]) => {
        setSchema(schemaData);
        setCuratedSamples(samplesData.samples);
        if (samplesData.samples.length > 0) {
          const autoSample = new URLSearchParams(window.location.search).get('sample');
          const target = (autoSample && samplesData.samples.find((s) => s.id === autoSample)) || samplesData.samples[0];
          setSelectedSampleId(target.id);
          setManualFeatures({ ...target.features });
          setManualFlowId(target.id);

          if (new URLSearchParams(window.location.search).get('auto_analyze') === 'true') {
            apiService.analyzeFlow({
              features: target.features,
              flow_id: target.id,
              source: `Benchmark Sample: ${target.id}`,
              is_synthetic: false,
            }).then((res) => {
              setManualResult(res.prediction);
            }).catch(console.error);
          }
        }
        setLoadingSchema(false);
      })
      .catch((err) => {
        setCsvError(err.message);
        setLoadingSchema(false);
      });
  }, []);

  // ==========================================
  // CSV MODE HANDLERS
  // ==========================================
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      parseAndSetFile(file);
    }
  };

  const parseAndSetFile = (file: File) => {
    setSelectedFile(file);
    setCsvError(null);
    setCsvResult(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      if (!text) return;

      const lines = text.split('\n').filter((l) => l.trim().length > 0);
      if (lines.length > 0) {
        const headers = lines[0].split(',').map((h) => h.trim());
        setCsvHeaders(headers);

        const previewData = lines.slice(1, 6).map((line) => line.split(',').map((v) => v.trim()));
        setCsvPreviewRows(previewData);
      }
    };
    reader.readAsText(file.slice(0, 50000)); // read first 50KB for fast preview
  };

  const handleUploadAndAnalyze = async () => {
    if (!selectedFile) return;
    setCsvAnalyzing(true);
    setCsvError(null);
    try {
      const res = await apiService.uploadCsv(selectedFile, csvMaxRows);
      setCsvResult(res);
    } catch (err: any) {
      setCsvError(err.message || 'Failed to analyze uploaded CSV');
    } finally {
      setCsvAnalyzing(false);
    }
  };

  const handleLoadSampleCsv = async () => {
    try {
      setCsvError(null);
      const res = await fetch(apiService.getSampleCsvUrl());
      if (!res.ok) throw new Error('Sample CSV not available');
      const blob = await res.blob();
      const sampleFile = new File([blob], 'netdefy_sample_network_traffic.csv', { type: 'text/csv' });
      parseAndSetFile(sampleFile);
    } catch (err: any) {
      setCsvError(`Failed to load benchmark sample CSV: ${err.message}`);
    }
  };

  const handleDownloadReport = () => {
    if (!csvResult) return;
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
    const rows = csvResult.predictions.map((p) => [
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
    link.setAttribute('download', `netdefy_threat_report_${csvResult.session_id}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // ==========================================
  // MANUAL MODE HANDLERS
  // ==========================================
  const handleSelectSample = (sampleId: string) => {
    setSelectedSampleId(sampleId);
    const sample = curatedSamples.find((s) => s.id === sampleId);
    if (sample) {
      setManualFeatures({ ...sample.features });
      setManualFlowId(sample.id);
      setIsModified(false);
      setManualResult(null);
    }
  };

  const handleFeatureChange = (name: string, val: number) => {
    setManualFeatures((prev) => ({ ...prev, [name]: val }));
    setIsModified(true);
  };

  const handleResetManual = () => {
    const sample = curatedSamples.find((s) => s.id === selectedSampleId);
    if (sample) {
      setManualFeatures({ ...sample.features });
      setIsModified(false);
      setManualResult(null);
    }
  };

  const handleAnalyzeManual = async () => {
    setManualAnalyzing(true);
    setManualError(null);
    try {
      const res = await apiService.analyzeFlow({
        features: manualFeatures,
        flow_id: manualFlowId || 'custom_flow',
        source: isModified ? 'Manual Custom Flow' : `Benchmark Sample: ${selectedSampleId}`,
        is_synthetic: isModified,
      });
      setManualResult(res.prediction);
    } catch (err: any) {
      setManualError(err.message || 'Inference execution failed');
    } finally {
      setManualAnalyzing(false);
    }
  };

  if (loadingSchema) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-cyan-400"></div>
      </div>
    );
  }

  // Filter CSV predictions
  const filteredPredictions = csvResult?.predictions.filter((p) => {
    if (csvFilter === 'ALL') return true;
    return p.decision === csvFilter;
  }) || [];

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Top Header & Mode Switcher */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-1 rounded-md">
              Threat Intelligence Engine
            </span>
          </div>
          <h1 className="text-xl font-bold text-white">Network Traffic Threat Analysis</h1>
          <p className="text-xs text-slate-400 max-w-xl">
            Submit packet flow telemetry for real-time inference against the tri-model engine.
            Detect anomalous behavior, classify threat vectors, and obtain explainable attributions.
          </p>
        </div>

        {/* Input Mode Toggle */}
        <div className="flex items-center space-x-1.5 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => handleModeSwitch('csv')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-mono font-semibold transition-all ${
              activeMode === 'csv'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            <span>Upload Network CSV</span>
          </button>
          <button
            onClick={() => handleModeSwitch('manual')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-mono font-semibold transition-all ${
              activeMode === 'manual'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sliders className="w-4 h-4" />
            <span>Manual Flow Input</span>
          </button>
        </div>
      </div>

      {/* ============================================================== */}
      {/* MODE A: UPLOAD CSV FILE                                         */}
      {/* ============================================================== */}
      {activeMode === 'csv' && (
        <div className="space-y-6">
          {/* Upload Card */}
          <div className="p-6 sm:p-8 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-base font-bold text-white flex items-center space-x-2">
                  <UploadCloud className="w-5 h-5 text-cyan-400" />
                  <span>Batch Network Flow Ingestion</span>
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Upload network telemetry in CSV format. Validates against the 76 continuous model features.
                </p>
              </div>

              <button
                onClick={handleLoadSampleCsv}
                className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-mono border border-cyan-500/20 transition-all self-start sm:self-auto"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Load Benchmark Sample (28 Flows)</span>
              </button>
            </div>

            {/* Dropzone */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-slate-700 hover:border-cyan-500/50 rounded-2xl p-8 text-center cursor-pointer bg-slate-950/40 hover:bg-slate-950/60 transition-all space-y-3"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="hidden"
              />
              <div className="w-12 h-12 mx-auto rounded-full bg-cyan-500/10 text-cyan-400 flex items-center justify-center">
                <UploadCloud className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-slate-200">
                  {selectedFile ? (
                    <span className="text-cyan-400 font-mono">{selectedFile.name}</span>
                  ) : (
                    'Click to select or drag and drop a traffic CSV'
                  )}
                </p>
                <p className="text-xs text-slate-500">
                  Supports standard CICIDS2017 flow vectors. Required: 76 continuous numerical features.
                </p>
              </div>
            </div>

            {/* Error Message */}
            {csvError && (
              <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono flex items-start space-x-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold">Validation Error:</div>
                  <div>{csvError}</div>
                </div>
              </div>
            )}

            {/* File Preview & Evaluation Parameters */}
            {selectedFile && (
              <div className="space-y-4 pt-2">
                <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono">
                  <div className="space-y-1">
                    <div className="text-slate-400">File Selected:</div>
                    <div className="text-white font-bold">{selectedFile.name}</div>
                    <div className="text-[11px] text-slate-500">
                      {(selectedFile.size / 1024).toFixed(1)} KB | {csvHeaders.length} columns detected
                    </div>
                  </div>

                  <div className="flex items-center space-x-4">
                    <div className="space-y-1">
                      <label className="text-slate-400 text-[11px]">Rows to Evaluate:</label>
                      <select
                        value={csvMaxRows}
                        onChange={(e) => setCsvMaxRows(Number(e.target.value))}
                        className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1 text-xs"
                      >
                        <option value={28}>Sample (28 rows)</option>
                        <option value={50}>First 50 rows</option>
                        <option value={100}>First 100 rows</option>
                        <option value={250}>First 250 rows</option>
                        <option value={500}>First 500 rows</option>
                        <option value={1000}>First 1,000 rows</option>
                      </select>
                    </div>

                    <button
                      onClick={handleUploadAndAnalyze}
                      disabled={csvAnalyzing}
                      className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold transition-all shadow-md shadow-cyan-500/20"
                    >
                      {csvAnalyzing ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-slate-950 border-t-transparent" />
                          <span>Running Batch Inference...</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4" />
                          <span>Execute Batch Detection</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* CSV Header Verification Pill */}
                {schema && (
                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-xs font-mono">
                    <span className="text-slate-400">Schema Compatibility:</span>
                    {schema.features.every((f) => csvHeaders.includes(f.name)) ? (
                      <span className="text-emerald-400 flex items-center space-x-1.5 font-bold">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>All 76 Model Features Verified</span>
                      </span>
                    ) : (
                      <span className="text-amber-400 flex items-center space-x-1.5 font-bold">
                        <AlertTriangle className="w-4 h-4" />
                        <span>Some columns may be missing</span>
                      </span>
                    )}
                  </div>
                )}

                {/* CSV Data Preview */}
                {csvPreviewRows.length > 0 && (
                  <div className="p-3 rounded-xl bg-slate-950/40 border border-slate-800/80 space-y-2">
                    <div className="text-[11px] font-mono text-slate-400 font-semibold">
                      Data Sample Preview ({csvPreviewRows.length} rows loaded):
                    </div>
                    <div className="overflow-x-auto max-h-28 text-[10px] font-mono border border-slate-800/60 rounded-lg">
                      <table className="w-full text-left">
                        <thead className="bg-slate-900/90 text-slate-400 sticky top-0">
                          <tr>
                            {csvHeaders.slice(0, 6).map((h, i) => (
                              <th key={i} className="p-1.5 truncate max-w-[140px] font-semibold border-b border-slate-800">
                                {h}
                              </th>
                            ))}
                            {csvHeaders.length > 6 && (
                              <th className="p-1.5 font-semibold border-b border-slate-800 text-slate-500">
                                +{csvHeaders.length - 6} more
                              </th>
                            )}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-900/80 text-slate-300">
                          {csvPreviewRows.slice(0, 3).map((row, ri) => (
                            <tr key={ri} className="hover:bg-slate-900/40">
                              {row.slice(0, 6).map((val, ci) => (
                                <td key={ci} className="p-1.5 truncate max-w-[140px]">
                                  {val}
                                </td>
                              ))}
                              {row.length > 6 && <td className="p-1.5 text-slate-500">...</td>}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Batch Results View */}
          {csvResult && (
            <div className="p-6 sm:p-8 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-6 animate-fadeIn">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Analysis Complete
                    </span>
                    <span className="text-xs font-mono text-slate-500">Session ID: {csvResult.session_id}</span>
                  </div>
                  <h2 className="text-lg font-bold text-white mt-1">Batch Detection Results</h2>
                  <p className="text-xs text-slate-400">
                    Evaluated {csvResult.total_rows_evaluated} flows against Isolation Forest, Autoencoder, and XGBoost.
                  </p>
                </div>

                <button
                  onClick={handleDownloadReport}
                  className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-mono border border-cyan-500/30 transition-all"
                >
                  <Download className="w-4 h-4" />
                  <span>Download Analysis Report (CSV)</span>
                </button>
              </div>

              {/* Triage Count Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[11px] font-mono text-slate-400 uppercase">Normal Traffic</div>
                  <div className="text-2xl font-extrabold text-emerald-400 font-mono mt-1">
                    {csvResult.normal_count}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {((csvResult.normal_count / csvResult.total_rows_evaluated) * 100).toFixed(1)}% of total
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[11px] font-mono text-slate-400 uppercase">Suspicious Known</div>
                  <div className="text-2xl font-extrabold text-rose-400 font-mono mt-1">
                    {csvResult.suspicious_known_count}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    {((csvResult.suspicious_known_count / csvResult.total_rows_evaluated) * 100).toFixed(1)}% of total
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[11px] font-mono text-slate-400 uppercase">Suspicious Unknown</div>
                  <div className="text-2xl font-extrabold text-purple-400 font-mono mt-1">
                    {csvResult.suspicious_unknown_count}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Zero-day anomaly</div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-[11px] font-mono text-slate-400 uppercase">Review Required</div>
                  <div className="text-2xl font-extrabold text-amber-400 font-mono mt-1">
                    {csvResult.review_required_count}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Conflicting signals</div>
                </div>
              </div>

              {/* Filter Tabs */}
              <div className="flex items-center justify-between flex-wrap gap-3 pt-2">
                <div className="flex items-center space-x-1.5 text-xs font-mono">
                  <span className="text-slate-400 flex items-center space-x-1 mr-2">
                    <Filter className="w-3.5 h-3.5" />
                    <span>Filter:</span>
                  </span>
                  {['ALL', 'NORMAL', 'SUSPICIOUS_KNOWN', 'REVIEW_REQUIRED', 'SUSPICIOUS_UNKNOWN'].map((state) => (
                    <button
                      key={state}
                      onClick={() => setCsvFilter(state)}
                      className={`px-3 py-1 rounded-lg transition-all ${
                        csvFilter === state
                          ? 'bg-cyan-500 text-slate-950 font-bold'
                          : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                      }`}
                    >
                      {state}
                    </button>
                  ))}
                </div>

                <span className="text-xs font-mono text-slate-400">
                  Showing {filteredPredictions.length} of {csvResult.total_rows_evaluated} flows
                </span>
              </div>

              {/* Predictions Table */}
              <div className="overflow-x-auto border border-slate-800 rounded-xl">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950 text-slate-400 uppercase text-[11px]">
                      <th className="py-3 px-3 w-8"></th>
                      <th className="py-3 px-4">Flow ID</th>
                      <th className="py-3 px-4">Decision</th>
                      <th className="py-3 px-4">Attributed Class</th>
                      <th className="py-3 px-4">Confidence</th>
                      <th className="py-3 px-4">Fused Anomaly</th>
                      <th className="py-3 px-4">Autoencoder Error</th>
                      {csvResult.has_ground_truth_labels && (
                        <th className="py-3 px-4 text-purple-400">Ground Truth (Ref)</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-slate-900/50">
                    {filteredPredictions.map((flow, idx) => {
                      const isExpanded = expandedFlowId === flow.flow_id;
                      const isNormal = flow.decision === 'NORMAL';
                      const isReview = flow.decision === 'REVIEW_REQUIRED';
                      const isKnown = flow.decision === 'SUSPICIOUS_KNOWN';

                      return (
                        <React.Fragment key={flow.flow_id || idx}>
                          <tr
                            onClick={() => setExpandedFlowId(isExpanded ? null : flow.flow_id)}
                            className="hover:bg-slate-800/40 cursor-pointer transition-colors"
                          >
                            <td className="py-3 px-3 text-slate-500">
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4 text-cyan-400" />
                              ) : (
                                <ChevronRight className="w-4 h-4" />
                              )}
                            </td>
                            <td className="py-3 px-4 font-bold text-white">{flow.flow_id}</td>
                            <td className="py-3 px-4">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                  isNormal
                                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                                    : isKnown
                                    ? 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                                    : isReview
                                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                                    : 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                                }`}
                              >
                                {flow.decision}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-slate-200">
                              {flow.classifier.predicted_class}
                            </td>
                            <td className="py-3 px-4 text-slate-300">
                              {(flow.classifier.top_probability * 100).toFixed(1)}%
                            </td>
                            <td className="py-3 px-4 text-slate-300 font-bold">
                              {flow.anomaly.fused_score.toFixed(4)}
                            </td>
                            <td className="py-3 px-4 text-slate-400">
                              {flow.anomaly.autoencoder_raw_error.toFixed(4)}
                            </td>
                            {csvResult.has_ground_truth_labels && (
                              <td className="py-3 px-4 text-purple-300">
                                {flow.ground_truth_label || 'Unlabeled'}
                              </td>
                            )}
                          </tr>

                          {/* Expanded Flow Diagnostics */}
                          {isExpanded && (
                            <tr className="bg-slate-950/80">
                              <td colSpan={csvResult.has_ground_truth_labels ? 8 : 7} className="p-4 space-y-3">
                                <div className="text-xs text-slate-300 font-sans">
                                  <span className="font-bold text-cyan-400">Decision Rationale:</span>{' '}
                                  {flow.decision_reason}
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                                  {/* Top Contributing Features */}
                                  <div className="space-y-2">
                                    <div className="text-[11px] font-bold uppercase text-slate-400">
                                      Top Autoencoder Reconstruction Residuals:
                                    </div>
                                    <div className="space-y-1">
                                      {flow.explanation.top_contributing_features.slice(0, 3).map((feat, fIdx) => (
                                        <div
                                          key={fIdx}
                                          className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800 text-[11px]"
                                        >
                                          <span className="text-white font-medium">{feat.feature_name}</span>
                                          <span className="text-amber-400 font-mono">
                                            Res: {feat.reconstruction_error.toFixed(4)}
                                          </span>
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  {/* Classifier Probability Breakdown */}
                                  <div className="space-y-2">
                                    <div className="text-[11px] font-bold uppercase text-slate-400">
                                      Class Attribution Probabilities:
                                    </div>
                                    <div className="space-y-1">
                                      {Object.entries(flow.classifier.class_probabilities)
                                        .sort((a, b) => b[1] - a[1])
                                        .slice(0, 3)
                                        .map(([cls, prob], pIdx) => (
                                          <div
                                            key={pIdx}
                                            className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800 text-[11px]"
                                          >
                                            <span className="text-slate-300">{cls}</span>
                                            <span className="text-cyan-400 font-mono font-bold">
                                              {(prob * 100).toFixed(1)}%
                                            </span>
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
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* MODE B: MANUAL FLOW INPUT                                      */}
      {/* ============================================================== */}
      {activeMode === 'manual' && schema && (
        <div className="space-y-6">
          <div className="p-6 sm:p-8 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-base font-bold text-white flex items-center space-x-2">
                  <Sliders className="w-5 h-5 text-cyan-400" />
                  <span>Manual Flow Vector Formulation</span>
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Input 76 continuous features or load genuine physical benchmark packet captures.
                </p>
              </div>

              {/* Curated Sample Dropdown */}
              <div className="flex items-center space-x-2">
                <span className="text-xs text-slate-400 font-mono">Curated Sample:</span>
                <select
                  value={selectedSampleId}
                  onChange={(e) => handleSelectSample(e.target.value)}
                  className="bg-slate-950 border border-slate-700 text-cyan-400 font-mono text-xs rounded-lg px-3 py-1.5 focus:border-cyan-500 focus:outline-none"
                >
                  {curatedSamples.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.true_label})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center space-x-2 overflow-x-auto pb-2 no-scrollbar text-xs font-mono">
              <button
                onClick={() => setActiveCategory('all')}
                className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${
                  activeCategory === 'all'
                    ? 'bg-cyan-500 text-slate-950 font-bold'
                    : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                All 76 Features
              </button>
              {schema.categories.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${
                    activeCategory === cat.id
                      ? 'bg-cyan-500 text-slate-950 font-bold'
                      : 'bg-slate-950 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  {cat.title} ({cat.feature_count})
                </button>
              ))}
            </div>

            {/* Features Input Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[460px] overflow-y-auto p-2 border border-slate-800/80 rounded-xl bg-slate-950/40">
              {schema.features
                .filter((f) => activeCategory === 'all' || f.category === activeCategory)
                .map((f) => {
                  const val = manualFeatures[f.name] ?? 0;
                  return (
                    <div
                      key={f.name}
                      className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5 focus-within:border-cyan-500/50 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-semibold text-slate-200 truncate max-w-[200px]" title={f.name}>
                          {f.name}
                        </label>
                        <span className="text-[10px] text-slate-500 font-mono">{f.unit}</span>
                      </div>
                      <input
                        type="number"
                        step="any"
                        value={val}
                        onChange={(e) => handleFeatureChange(f.name, parseFloat(e.target.value) || 0)}
                        className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs text-white font-mono focus:border-cyan-400 focus:outline-none"
                      />
                    </div>
                  );
                })}
            </div>

            {/* Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-800">
              <div className="flex items-center space-x-2 text-xs font-mono text-slate-400">
                <span>Flow ID:</span>
                <input
                  type="text"
                  value={manualFlowId}
                  onChange={(e) => setManualFlowId(e.target.value)}
                  placeholder="flow_identifier"
                  className="bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-xs text-white"
                />
                {isModified && (
                  <span className="text-amber-400 text-[11px] bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                    Modified Feature Values
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={handleResetManual}
                  className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset Values</span>
                </button>

                <button
                  onClick={handleAnalyzeManual}
                  disabled={manualAnalyzing}
                  className="flex items-center space-x-2 px-6 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold text-xs transition-all shadow-md shadow-cyan-500/20"
                >
                  {manualAnalyzing ? (
                    <>
                      <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-slate-950 border-t-transparent" />
                      <span>Executing Inference...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5" />
                      <span>Analyze Flow</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {manualError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-mono">
                {manualError}
              </div>
            )}
          </div>

          {/* Single Flow Results Card */}
          {manualResult && (
            <div className="p-6 sm:p-8 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl space-y-6 animate-fadeIn">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                      Single-Flow Inference Output
                    </span>
                    <span className="text-xs font-mono text-slate-500">{manualResult.flow_id}</span>
                  </div>
                  <h2 className="text-xl font-bold text-white">Detection Assessment & Attribution</h2>
                </div>

                {/* Big Decision Badge */}
                <div
                  className={`px-4 py-2 rounded-xl border flex items-center space-x-2 font-mono font-bold text-sm ${
                    manualResult.decision === 'NORMAL'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 shadow-lg shadow-emerald-500/10'
                      : manualResult.decision === 'SUSPICIOUS_KNOWN'
                      ? 'bg-rose-500/10 text-rose-400 border-rose-500/30 shadow-lg shadow-rose-500/10'
                      : manualResult.decision === 'REVIEW_REQUIRED'
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/30 shadow-lg shadow-amber-500/10'
                      : 'bg-purple-500/10 text-purple-400 border-purple-500/30 shadow-lg shadow-purple-500/10'
                  }`}
                >
                  {manualResult.decision === 'NORMAL' ? (
                    <ShieldCheck className="w-5 h-5" />
                  ) : (
                    <ShieldAlert className="w-5 h-5" />
                  )}
                  <span>{manualResult.decision}</span>
                </div>
              </div>

              {/* Plain-English Explanation Banner */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider font-mono">
                  Operational Assessment:
                </div>
                <p className="text-sm text-slate-200 leading-relaxed font-sans">
                  {manualResult.decision_reason}
                </p>
                {manualResult.explanation.evidence_summary.length > 0 && (
                  <ul className="text-xs text-slate-400 list-disc list-inside space-y-0.5 pt-1 font-mono">
                    {manualResult.explanation.evidence_summary.map((ev, eIdx) => (
                      <li key={eIdx}>{ev}</li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Two Column Grid: Classifier & Anomaly */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Classifier Attribution */}
                <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <span className="text-xs font-bold text-white font-mono uppercase">
                      Supervised Attack Attribution
                    </span>
                    <span className="text-xs font-mono text-cyan-400 font-bold">
                      {manualResult.classifier.predicted_class}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-400 block text-[10px]">Top Confidence:</span>
                      <span className="text-lg font-bold text-white">
                        {(manualResult.classifier.top_probability * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-400 block text-[10px]">Decision Margin:</span>
                      <span className="text-lg font-bold text-white">
                        {manualResult.classifier.probability_margin.toFixed(3)}
                      </span>
                    </div>
                  </div>

                  {/* Top Class Probabilities Bar Chart */}
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[11px] font-mono text-slate-400 uppercase">Class Probabilities:</span>
                    <div className="space-y-1 text-xs font-mono">
                      {Object.entries(manualResult.classifier.class_probabilities)
                        .sort((a, b) => b[1] - a[1])
                        .slice(0, 4)
                        .map(([cls, prob]) => (
                          <div key={cls} className="space-y-0.5">
                            <div className="flex justify-between text-[11px]">
                              <span className="text-slate-300">{cls}</span>
                              <span className="text-slate-400">{(prob * 100).toFixed(1)}%</span>
                            </div>
                            <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                              <div
                                className="bg-cyan-500 h-full rounded-full"
                                style={{ width: `${Math.max(prob * 100, 2)}%` }}
                              />
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                </div>

                {/* Anomaly Detection Metrics */}
                <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
                    <span className="text-xs font-bold text-white font-mono uppercase">
                      Unsupervised Outlier Calibration
                    </span>
                    <span className="text-xs font-mono text-purple-400 font-bold">
                      Threshold p99: {manualResult.anomaly.threshold.toFixed(4)}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-400 block text-[10px]">Fused Anomaly Score:</span>
                      <span
                        className={`text-lg font-bold ${
                          manualResult.anomaly.is_anomaly ? 'text-rose-400' : 'text-emerald-400'
                        }`}
                      >
                        {manualResult.anomaly.fused_score.toFixed(4)}
                      </span>
                    </div>
                    <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                      <span className="text-slate-400 block text-[10px]">Autoencoder MSE:</span>
                      <span className="text-lg font-bold text-white">
                        {manualResult.anomaly.autoencoder_raw_error.toFixed(4)}
                      </span>
                    </div>
                  </div>

                  {/* Top Contributing Features */}
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[11px] font-mono text-slate-400 uppercase">
                      Top Diagnostic Feature Residuals:
                    </span>
                    <div className="space-y-1.5">
                      {manualResult.explanation.top_contributing_features.slice(0, 3).map((feat, fIdx) => (
                        <div
                          key={fIdx}
                          className="p-2 rounded bg-slate-900 border border-slate-800 flex items-center justify-between text-xs font-mono"
                        >
                          <div>
                            <span className="text-white font-medium">{feat.feature_name}</span>
                            <div className="text-[10px] text-slate-500">
                              Input: {feat.input_value.toFixed(2)} | Reconstructed: {feat.reconstructed_value.toFixed(2)}
                            </div>
                          </div>
                          <span className="text-amber-400 font-bold">
                            e²: {feat.reconstruction_error.toFixed(4)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Scientific Advisory Note */}
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 text-xs text-slate-400 font-mono flex items-start space-x-2.5">
                <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <p>
                  <strong className="text-slate-300">Operational Disclaimer:</strong> Statistical model predictions
                  indicate deviation from normal traffic patterns, not a legally binding attribution. Single-flow
                  vectors do not detect multi-flow scans or stealthy C2 beaconing.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
